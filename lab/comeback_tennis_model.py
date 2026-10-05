"""Tennis comeback probabilities from an exact point-by-point Markov model (iid points on serve).
P(leader loses) from in-play states. Players of equal strength (conservative: if the leader is the
better player, comebacks are rarer). pA = leader's serve-point win rate, pB = trailer's.
Output: lab/results/2026-10-05-comeback-tennis-model.json"""
import json
from functools import lru_cache


def make(pA, pB, best_of=3, final_tb=True, tb_final_to=7):
    """Returns f(sets_a, sets_b, games_a, games_b, a_serving) -> P(A wins match), at start of a game."""

    @lru_cache(None)
    def game(p, a, b):  # P(server wins game) from points a-b
        if a >= 4 and a - b >= 2: return 1.0
        if b >= 4 and b - a >= 2: return 0.0
        if a >= 3 and b >= 3 and a == b:
            return p * p / (p * p + (1 - p) * (1 - p))
        return p * game(p, a + 1, b) + (1 - p) * game(p, a, b + 1)

    @lru_cache(None)
    def tb(a, b, a_serving_first, to):  # P(A wins tiebreak) from points a-b; serve rotates 1,2,2,...
        if a >= to and a - b >= 2: return 1.0
        if b >= to and b - a >= 2: return 0.0
        if a >= to - 1 and b >= to - 1 and a == b and a > 12:
            # approx deuce-like closed form
            q = pA * (1 - pB); r = (1 - pA) * pB
            return q / (q + r)
        n = a + b
        first = a_serving_first if ((n + 1) // 2) % 2 == 0 else not a_serving_first
        p = pA if first else 1 - pB
        return p * tb(a + 1, b, a_serving_first, to) + (1 - p) * tb(a, b + 1, a_serving_first, to)

    need = best_of // 2 + 1

    @lru_cache(None)
    def match(sa, sb, ga, gb, a_srv):
        if sa == need: return 1.0
        if sb == need: return 0.0
        deciding = (sa == sb == need - 1)
        # set over?
        if (ga >= 6 and ga - gb >= 2) or ga == 7:
            return match(sa + 1, sb, 0, 0, a_srv)
        if (gb >= 6 and gb - ga >= 2) or gb == 7:
            return match(sa, sb + 1, 0, 0, a_srv)
        if ga == 6 and gb == 6:
            to = tb_final_to if deciding else 7
            pt = tb(0, 0, a_srv, to)
            # after tiebreak, the player who received first serves first in next set
            return pt * match(sa + 1, sb, 0, 0, not a_srv) + (1 - pt) * match(sa, sb + 1, 0, 0, not a_srv)
        if a_srv:
            g = game(pA, 0, 0)
            return g * match(sa, sb, ga + 1, gb, False) + (1 - g) * match(sa, sb, ga, gb + 1, False)
        g = game(pB, 0, 0)
        return (1 - g) * match(sa, sb, ga + 1, gb, True) + g * match(sa, sb, ga, gb + 1, True)

    return match


STATES = [  # (label, sets_a, sets_b, games_a, games_b, a_serving) for Bo3; Bo5 uses sets 2-0 / 2-1 variants
    ('1-0 sets, 4-2 set 2, A serves', 1, 0, 4, 2, True),
    ('1-0 sets, 5-2 set 2, A serves', 1, 0, 5, 2, True),
    ('1-0 sets, 5-3 set 2, A serves', 1, 0, 5, 3, True),
    ('1-0 sets, 5-3 set 2, B serves', 1, 0, 5, 3, False),
    ('1-0 sets, 5-1 set 2, B serves', 1, 0, 5, 1, False),
    ('1-0 sets, 5-0 set 2, A serves', 1, 0, 5, 0, True),
    ('1-0 sets, 5-4 set 2, A serves', 1, 0, 5, 4, True),
    ('1-1 sets, 5-1 set 3, B serves', 1, 1, 5, 1, False),
    ('1-1 sets, 5-2 set 3, A serves', 1, 1, 5, 2, True),
    ('1-1 sets, 5-3 set 3, A serves', 1, 1, 5, 3, True),
]
out = {}
for tour, pa in (('ATP-like p=0.64', 0.64), ('WTA-like p=0.56', 0.56)):
    for pb_adj in (0.0, 0.03):  # second: the trailer is a bit better on serve (worst case)
        f = make(pa, pa + pb_adj, 3)
        key = f'{tour}, trailer serve +{pb_adj}'
        out[key] = {s[0]: round(1 - f(*s[1:]), 5) for s in STATES}
    f5 = make(pa, pa, 5)
    out[f'{tour}, Bo5'] = {
        '2-0 sets, 5-2 set 3, A serves': round(1 - f5(2, 0, 5, 2, True), 6),
        '2-0 sets, 5-3 set 3, B serves': round(1 - f5(2, 0, 5, 3, False), 6),
        '2-1 sets, 5-2 set 4, A serves': round(1 - f5(2, 1, 5, 2, True), 6),
        '2-2 sets, 5-2 set 5, A serves': round(1 - f5(2, 2, 5, 2, True), 6),
        '2-0 sets, 3-1 set 3, A serves': round(1 - f5(2, 0, 3, 1, True), 6),
    }
json.dump(out, open('/home/user/polysweeper-v1/lab/results/2026-10-05-comeback-tennis-model.json', 'w'), indent=1)
for k, v in out.items():
    print(k)
    for s, x in v.items():
        print(f'   {s:34s} P(leader loses)={x:.4f}  ~1 in {1/x:,.0f}' if x > 0 else f'   {s} 0')


# --- point-level states (match point situations), appended ---
def mid_game(pA, pB, best_of, sa, sb, ga, gb, a_srv, pts_srv, pts_rcv):
    f = make(pA, pB, best_of)
    p = pA if a_srv else pB
    import comeback_tennis_model as _m  # noqa (game fn is internal; recompute simply)
    from functools import lru_cache
    @lru_cache(None)
    def g(a, b):
        if a >= 4 and a - b >= 2: return 1.0
        if b >= 4 and b - a >= 2: return 0.0
        if a >= 3 and b >= 3 and a == b: return p * p / (p * p + (1 - p) ** 2)
        return p * g(a + 1, b) + (1 - p) * g(a, b + 1)
    hold = g(pts_srv, pts_rcv)
    if a_srv:
        return hold * f(sa, sb, ga + 1, gb, False) + (1 - hold) * f(sa, sb, ga, gb + 1, False)
    return (1 - hold) * f(sa, sb, ga + 1, gb, True) + hold * f(sa, sb, ga, gb + 1, True)

if __name__ == '__main__':
    PT = [('Bo3 1-0, 5-2, A serving 40-0', 3, 1, 0, 5, 2, True, 3, 0),
          ('Bo3 1-0, 5-2, A serving 40-15', 3, 1, 0, 5, 2, True, 3, 1),
          ('Bo3 1-0, 5-2, A serving 40-30', 3, 1, 0, 5, 2, True, 3, 2),
          ('Bo3 1-0, 5-3, A serving 40-0', 3, 1, 0, 5, 3, True, 3, 0),
          ('Bo3 1-0, 5-1, B serving 0-40', 3, 1, 0, 5, 1, False, 0, 3),
          ('Bo3 1-0, 5-2, A serving 30-0', 3, 1, 0, 5, 2, True, 2, 0),
          ('Bo3 1-1, 5-2, A serving 40-0', 3, 1, 1, 5, 2, True, 3, 0),
          ('Bo3 1-1, 5-1, A serving 40-0', 3, 1, 1, 5, 1, True, 3, 0),
          ('Bo5 2-0, 5-2, A serving 40-0', 5, 2, 0, 5, 2, True, 3, 0),
          ('Bo5 2-0, 5-3, A serving 40-15', 5, 2, 0, 5, 3, True, 3, 1)]
    out2 = {}
    for tour, pa in (('ATP p=0.64', 0.64), ('WTA p=0.56', 0.56)):
        for lab, bo, *st in PT:
            x = 1 - mid_game(pa, pa, bo, *st)
            out2[f'{tour} | {lab}'] = round(x, 6)
            print(f'{tour} | {lab:34s} P(lose)={x:.5f} ~1 in {1/x:,.0f}')
    json.dump(out2, open('/home/user/polysweeper-v1/lab/results/2026-10-05-comeback-tennis-model-points.json', 'w'), indent=1)
