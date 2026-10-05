"""CS2 comeback rates from bo3.gg round histories (lab/data/raw/cs2_rounds, from comeback_cs2_fetch.py).
Leader = the team ahead in the series (or on the deciding map). Each match counted once per state (first time).
Output: lab/results/2026-10-05-comeback-cs2.json"""
import json, glob, collections
RAW = '/home/user/polysweeper-v1/lab/data/raw/cs2_rounds/'
games = {}
for f in glob.glob(RAW + 'games_*.json'):
    for g in json.load(open(f)):
        games[g['id']] = g
tiers = {}
for f in glob.glob(RAW + 'matches_*.json'):
    for m in json.load(open(f)):
        tiers[m['id']] = (m['tier'], m['bo'])
M = collections.defaultdict(list)
for g in games.values():
    M[g['match_id']].append(g)
def valid(g):
    # labels must reproduce the final score, and the map must not be decided before its last round
    a = b = 0
    n = len(g['rounds'])
    for i, r in enumerate(g['rounds']):
        if r == g['winner']: a += 1
        elif r == g['loser']: b += 1
        else: return False
        if i < n - 1:
            hi, lo = max(a, b), min(a, b)
            if hi >= 13 and (hi + lo <= 24):  # regulation decided early
                return False
            if hi + lo > 24:  # overtime: MR3 halves of 6; decided when a team gets 4 in a 6-round block
                k = (hi + lo - 25) // 6
                base = 12 + 3 * k
                if hi - base >= 4: return False
    return a == g['ws'] and b == g['ls']


bad = [0]
C = collections.defaultdict(lambda: [0, 0])
ex = collections.defaultdict(list)
used = 0
for mid, gs in M.items():
    gs.sort(key=lambda g: g['number'])
    if [g['number'] for g in gs] != list(range(1, len(gs) + 1)): continue
    wins = collections.Counter(g['winner'] for g in gs)
    top = max(wins.values())
    bo = {1: 1, 2: 3, 3: 5}.get(top)
    if bo is None or len(wins) > 2 or len(gs) > bo: continue
    if bo == 1 and len(gs) != 1: continue
    tb = tiers.get(mid)
    if tb and tb[1] != bo: continue
    champ = wins.most_common(1)[0][0]
    tier = (tb[0] if tb else '?')
    used += 1
    series = collections.Counter()
    for g in gs:
        if not g['rounds'] or g['ws'] is None or g['ls'] is None or len(g['rounds']) != g['ws'] + g['ls']:
            series[g['winner']] += 1; continue
        teams = [g['winner'], g['loser']]
        if not valid(g):
            bad[0] += 1; series[g['winner']] += 1; continue
        sc = collections.Counter()
        seen = set()
        for rw in g['rounds']:
            sc[rw] += 1
            a, b = sc[teams[0]], sc[teams[1]]
            if a == b: continue
            lead_t = teams[0] if a > b else teams[1]
            hi, lo = max(a, b), min(a, b)
            s_lead, s_trail = series[lead_t], series[teams[1] if lead_t == teams[0] else teams[0]]
            if bo == 3 and s_lead == 1 and s_trail == 0: ctx = 'Bo3 1-0, map 2'
            elif bo == 3 and s_lead == 1 and s_trail == 1: ctx = 'Bo3 1-1, map 3'
            elif bo == 1: ctx = 'Bo1'
            elif bo == 3 and s_lead == 0 and s_trail == 0: ctx = 'Bo3 0-0, map 1'
            else: continue
            if hi >= 13: continue  # map already decided
            labels = []
            if hi == 12 and lo <= 11: labels.append(f'map point 12-{lo}' if lo <= 10 else 'map point 12-11')
            if hi == 12: labels.append('map point (12+) ahead, regulation')
            if hi >= 10 and hi - lo >= 4: labels.append('10+ rounds, lead 4+')
            if hi >= 10 and hi - lo >= 6: labels.append('10+ rounds, lead 6+')
            if hi >= 10 and hi - lo >= 8: labels.append('10+ rounds, lead 8+')
            for cap in (5, 7, 9):
                if hi == 12 and lo <= cap: labels.append(f'map point, trailer <= {cap} rounds')
            for lab in labels:
                k = f'{ctx} | {lab}'
                if k in seen: continue
                seen.add(k)
                lost = lead_t != champ
                for kk in (k, f'{k} | tier {tier}'):
                    C[kk][0] += 1; C[kk][1] += lost
                if lost and len(ex[k]) < 3: ex[k].append(mid)
        series[g['winner']] += 1
res = {k: {'n': v[0], 'lost': v[1]} for k, v in sorted(C.items())}
json.dump({'maps': len(games), 'matches_used': used, 'states': res, 'loss_examples': ex},
          open('/home/user/polysweeper-v1/lab/results/2026-10-05-comeback-cs2.json', 'w'), indent=0)
print('maps', len(games), 'matches used', used, 'maps rejected as inconsistent', bad[0])
for k, v in res.items():
    if '| tier' in k and not any(t in k for t in ('tier s', 'tier a')): continue
    ub = (3 / v['n']) if v['lost'] == 0 else None
    print(f'{k:60s} n={v["n"]:5d} lost={v["lost"]:4d} rate=1/{(v["n"]/v["lost"]) if v["lost"] else float("inf"):.0f}')

# --- map-level (any series context): P(team at 12-x loses the map) ---
MC = collections.defaultdict(lambda: [0, 0])
for g in games.values():
    if not g['rounds'] or g['ws'] is None or g['ls'] is None or len(g['rounds']) != g['ws'] + g['ls'] or not valid(g): continue
    sc = collections.Counter(); seen = set()
    for rw in g['rounds']:
        sc[rw] += 1
        a, b = sc[g['winner']], sc[g['loser']]
        hi, lo = max(a, b), min(a, b)
        if hi == 12 and lo < 12 and lo not in seen:
            seen.add(lo)
            MC[lo][0] += 1; MC[lo][1] += (b > a)
print('map-level: team at 12-x loses the map')
cum = [0, 0]
mres = {}
for lo in range(0, 12):
    v = MC[lo]; cum[0] += v[0]; cum[1] += v[1]
    mres[f'12-{lo}'] = {'n': v[0], 'lost': v[1]}
    mres[f'12-<= {lo} (first reach of map point)'] = None
    print(f'12-{lo:<2d} n={v[0]:5d} lost={v[1]:3d}')
# first-reach version for cumulative: a map reaches 12 once with a definite lo; count maps by first lo
FR = collections.defaultdict(lambda: [0, 0])
for g in games.values():
    if not g['rounds'] or g['ws'] is None or g['ls'] is None or len(g['rounds']) != g['ws'] + g['ls'] or not valid(g): continue
    sc = collections.Counter()
    for rw in g['rounds']:
        sc[rw] += 1
        a, b = sc[g['winner']], sc[g['loser']]
        if max(a, b) == 12 and min(a, b) < 12:
            FR[min(a, b)][0] += 1; FR[min(a, b)][1] += (b > a); break
c = [0, 0]
for lo in range(0, 12):
    c[0] += FR[lo][0]; c[1] += FR[lo][1]
    mres[f'first map point with trailer <= {lo}'] = {'n': c[0], 'lost': c[1]}
    print(f'first map point, trailer <= {lo:2d}: n={c[0]:5d} lost={c[1]:3d}')
mres = {k: v for k, v in mres.items() if v}
d = json.load(open('/home/user/polysweeper-v1/lab/results/2026-10-05-comeback-cs2.json'))
d['map_level'] = mres
json.dump(d, open('/home/user/polysweeper-v1/lab/results/2026-10-05-comeback-cs2.json', 'w'), indent=0)
