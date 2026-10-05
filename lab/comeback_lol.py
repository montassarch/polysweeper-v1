"""LoL series comebacks (map level) from Leaguepedia's free Cargo API (ScoreboardGames, game order per match).
States: Bo3 leader 1-0; Bo5 leader 2-0, 2-1. Best-of inferred from wins needed (2 -> Bo3, 3 -> Bo5).
Output: lab/results/2026-10-05-comeback-lol.json"""
import json, os, time, urllib.request, urllib.parse, collections
UA = {'User-Agent': 'polysweeper-research/0.1 (read-only research; polite)'}
RAW = '/home/user/polysweeper-v1/lab/data/raw/lol_games.json'
if not os.path.exists(RAW):
    rows, off = [], 0
    while True:
        q = {'action': 'cargoquery', 'format': 'json', 'tables': 'ScoreboardGames',
             'fields': 'MatchId,N_GameInMatch,WinTeam,Team1,Team2,DateTime_UTC,Tournament',
             'limit': '500', 'offset': str(off), 'where': 'DateTime_UTC > "2019-01-01"', 'order_by': 'DateTime_UTC'}
        u = 'https://lol.fandom.com/api.php?' + urllib.parse.urlencode(q)
        for i in range(5):
            try:
                d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60)); break
            except Exception as e:
                print('retry', off, e, flush=True); time.sleep(10 * (i + 1)); d = None
        if d and 'error' in d and d['error'].get('code') == 'ratelimited':
            print('ratelimited at', off, flush=True); time.sleep(90); continue
        if not d or 'cargoquery' not in d:
            print('stop', off, str(d)[:200]); break
        b = [x['title'] for x in d['cargoquery']]
        rows += b
        if len(b) < 500: break
        off += 500
        if off % 10000 == 0: print(off, flush=True)
        time.sleep(8)
    json.dump(rows, open(RAW, 'w'))
rows = json.load(open(RAW))
M = collections.defaultdict(list)
for r in rows:
    M[r['MatchId']].append(r)
C = collections.defaultdict(lambda: [0, 0])
TIER1 = ('LCK', 'LPL', 'LEC', 'LCS', 'LTA', 'Worlds', 'MSI', 'Mid-Season', 'World Championship', 'First Stand', 'PCS', 'VCS', 'LCP', 'CBLOL', 'LJL')
for mid, gs in M.items():
    gs.sort(key=lambda r: int(r['N GameInMatch'] or 0))
    wins = collections.Counter(r['WinTeam'] for r in gs)
    if not gs or not gs[0]['WinTeam']: continue
    top = max(wins.values())
    if top not in (2, 3): continue
    bo = 3 if top == 2 else 5
    if sum(wins.values()) > (3 if bo == 3 else 5) or len(wins) > 2: continue
    champ = wins.most_common(1)[0][0]
    tier = 'tier1' if any(t in (gs[0]['Tournament'] or '') for t in TIER1) else 'other'
    sc = collections.Counter()
    seen = set()
    for r in gs[:-1]:
        sc[r['WinTeam']] += 1
        teams = list(sc.keys())
        a = r['WinTeam']; b = [t for t in wins if t != a]
        other = sc[b[0]] if b else 0
        lead = (sc[a], other) if sc[a] >= other else None
        # record state from the leader's view
        leader = max(sc, key=lambda t: sc[t]); lw = sc[leader]; tw = sum(sc.values()) - lw
        if lw == tw: continue
        key = f'Bo{bo} {lw}-{tw}'
        if key in seen: continue
        seen.add(key)
        for k in (key, f'{key} {tier}'):
            C[k][0] += 1; C[k][1] += (leader != champ)
res = {k: {'n': v[0], 'lost': v[1], 'rate': round(v[1] / v[0], 4)} for k, v in sorted(C.items())}
json.dump({'matches': len(M), 'states': res}, open('/home/user/polysweeper-v1/lab/results/2026-10-05-comeback-lol.json', 'w'), indent=0)
for k, v in res.items(): print(f'{k:22s} n={v["n"]:6d} lost={v["lost"]:5d} rate={v["rate"]}')
