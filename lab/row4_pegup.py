"""Row 4, price-priority model on the long history: a 5-share bid at B placed at the FIRST moment a live-readable gate is true
(plus a bot delay L seconds) on the side that is ahead.  Every later taker SELL print at or below B before Polymarket's finished
stamp would have met our bid first (no other bidder above B assumed), so the bid fills once such prints add up to 5 shares.
Counts per GAME (one coin toss).  Needs lab/data/raw/row4h/{tape,plays} (lab/row4_history.py).
  python3 lab/row4_pegup.py [B=0.995] [L=45]    -> lab/results/2026-10-09-row4-pegup.json
Gates (all readable live):  D1 = last period/OT, clock <= 5 s, ahead (football OT excluded);  T60 / T120 = same with clock <= 60 / 120 s;
MLB over = final out or walk-off in the 9th or later.   Football/basketball/hockey/MLB; NFL ties and 50/50 results count as losses.
"""
import bisect, collections, json, os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import row4_history as H  # noqa: E402

ROOT = H.ROOT
REG = H.REG


def gate_row(sport, p, X, L=1):
    """p = [ts, period, clock, home, away, ...]; True when the leader's bid should be placed"""
    ts, per, clk, hs, as_ = p[0], p[1], p[2], p[3], p[4]
    if per is None or hs is None or as_ is None or abs(hs - as_) < L:
        return False
    if sport == "MLB":
        top, outs = p[5], p[6]
        if per < 9 or outs is None:
            return False
        if top == 1:
            return outs >= 3 and hs > as_
        return hs > as_ or (outs >= 3 and as_ > hs)
    if sport in ("CFB", "NFL") and per > REG[sport]:
        return False
    if sport == "NHL":                                       # ESPN's NHL clock counts UP (elapsed): remaining = 1200 - clock
        if per > 3:
            return True                                      # overtime sudden death: any lead means the game is over
        return per == 3 and clk is not None and (1200 - clk) <= X
    return per >= REG[sport] and clk is not None and clk <= X


CANCEL = os.environ.get("CANCEL", "none")          # none | lag45 : cancel the bid when the gate no longer holds (state read 45 s late)


def run(B=0.995, L=45, shares=5.0):
    games = [g for g in H.load_games() if not g["void"]]
    out = {"B": B, "delay_s": L, "shares": shares, "cells": {}}
    cells = collections.defaultdict(lambda: collections.Counter())
    for g in games:
        pf = H.PLAYS / f"{g['game']}.json"
        tf = H.TAPE / f"{g['game']}.json"
        if not pf.exists() or not tf.exists():
            continue
        pj = json.loads(pf.read_text())
        if not pj.get("espn"):
            continue
        tape = json.loads(tf.read_text())
        if not tape["ok"]:
            continue
        pl = pj["plays"]
        if g["sport"] == "MLB":
            pl = H.mlb_states(pl)
        home_won = pj["home_won"]
        ts_list = [p[0] for p in pl]
        losers = out.setdefault("loser_games", [])
        prints = sorted(t for t in tape["trades"] if t[1] == "SELL" and 0.95 <= t[2] <= B + 1e-9 and t[0] < g["fin"])
        for name, X, L in (("D1 clock<=1s", 1, 1), ("T60 lead>=1", 60, 1), ("T60 lead>=5 (NBA)", 60, 5), ("T60 lead>=3 (NFL)", 60, 3),
                           ("T60 lead>=2 (NHL)", 60, 2), ("T120 lead>=9 (NBA)", 120, 9), ("T120 lead>=2 (NHL)", 120, 2)):
            if g["sport"] == "MLB" and name != "D1 clock<=1s":
                continue
            if "(NBA)" in name and g["sport"] not in ("NBA",) or "(NFL)" in name and g["sport"] not in ("NFL",) or "(NHL)" in name and g["sport"] not in ("NHL",):
                continue
            key = (g["sport"], "MLB game over" if g["sport"] == "MLB" else name)
            c = cells[key]
            c["games"] += 1
            i = next((k for k, p in enumerate(pl) if gate_row(g["sport"], p, X, L)), None)
            if i is None:
                continue
            c["gate_reached"] += 1
            t_join = pl[i][0] + L
            if t_join >= g["fin"]:
                c["join_after_stamp"] += 1
                continue
            leader_home = pl[i][3] > pl[i][4]
            sold = 0.0
            for t in prints:
                if t[0] < t_join:
                    continue
                token_home = (g["px"][t[4]] == 1.0) == home_won
                if token_home != leader_home:
                    continue
                if CANCEL == "lag45":
                    k = bisect.bisect_right(ts_list, t[0] - 45) - 1
                    if k < 0 or not gate_row(g["sport"], pl[k], X, L) or (pl[k][3] > pl[k][4]) != leader_home:
                        continue                      # our bid would already have been cancelled
                sold += t[3]
                if sold >= shares:
                    c["filled"] += 1
                    if g["px"][t[4]] != 1.0:
                        c["loser"] += 1
                        losers.append([key[0], key[1], g["game"], int(t[0] - g["fin"]), t[2]])
                    c["wait_sum"] += t[0] - t_join
                    break
            c["window_sum"] += g["fin"] - t_join
    for (sport, name), c in sorted(cells.items()):
        out["cells"][f"{sport} | {name}"] = dict(c)
    return out


if __name__ == "__main__":
    B = float(sys.argv[1]) if len(sys.argv) > 1 else 0.995
    L = int(sys.argv[2]) if len(sys.argv) > 2 else 45
    res = run(B, L)
    (ROOT / f"lab/results/2026-10-09-row4-pegup-B{B}-L{L}{'-cancel' if CANCEL != 'none' else ''}.json").write_text(json.dumps(res, indent=1))
    print(f"B={B} delay={L}s, 5-share bid joined at the first gate moment, cancel mode {CANCEL}")
    for ln in res.get("loser_games", [])[:40]:
        print("   loser:", ln)
    for k, c in res["cells"].items():
        g = c.get("games", 0)
        gr = c.get("gate_reached", 0)
        f = c.get("filled", 0)
        print(f"  {k:28s} games {g:5d} gate {gr:5d} filled {f:4d} ({f / max(1, g):.3f} of games) losers {c.get('loser', 0)} "
              f"avg window {c.get('window_sum', 0) / max(1, gr - c.get('join_after_stamp', 0)):.0f}s")
