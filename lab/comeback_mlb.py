"""Comeback rates in MLB from inning linescores (free MLB Stats API, one call per month).
States at half-inning boundaries: e.g. 'home leads by k after top 9' (game over unless home... no, home
already won if leading after top 9), 'away leads by k going to bottom 9', 'leader by k after 8 innings'.
Output: lab/results/2026-10-05-comeback-mlb.json"""
import json, os, time, urllib.request, collections
R = '/home/user/polysweeper-v1/lab/'
UA = {'User-Agent': 'polysweeper-research/0.1 (read-only)'}
RAW = R + 'data/raw/mlb_linescores/'
os.makedirs(RAW, exist_ok=True)

def get(u):
    return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60))

games = []
for yr in range(2008, 2026):
    for mo in range(3, 12):
        f = RAW + f'{yr}-{mo:02d}.json'
        if not os.path.exists(f):
            last = 30 if mo in (4, 6, 9, 11) else 31
            u = (f'https://statsapi.mlb.com/api/v1/schedule?sportId=1&gameType=R,F,D,L,W&startDate={yr}-{mo:02d}-01'
                 f'&endDate={yr}-{mo:02d}-{last}&hydrate=linescore')
            try:
                d = get(u)
            except Exception as e:
                print('err', yr, mo, e); continue
            json.dump(d, open(f, 'w'))
            time.sleep(0.3)
        d = json.load(open(f))
        for dd in d.get('dates', []):
            for g in dd['games']:
                if g.get('status', {}).get('abstractGameState') != 'Final':
                    continue
                ls = g.get('linescore', {})
                inn = ls.get('innings', [])
                if len(inn) < 9:
                    continue  # shortened games
                a = [i.get('away', {}).get('runs') for i in inn]
                h = [i.get('home', {}).get('runs') for i in inn]
                games.append((g['gamePk'], a, h))
games = list({g[0]: g for g in games}.values())
print('games', len(games))

# state counters: key -> [n, leader_lost]
C = collections.defaultdict(lambda: [0, 0])
for pk, a, h in games:
    A = sum(x or 0 for x in a); H = sum(x or 0 for x in h)
    if A == H:
        continue
    for n in (6, 7, 8):  # after n full innings
        sa = sum((x or 0) for x in a[:n]); sh = sum((x or 0) for x in h[:n])
        d = sa - sh
        if d == 0: continue
        k = min(abs(d), 8)
        lead_home = d < 0
        lost = (H > A) != lead_home
        C[f'after {n} full innings, {"home" if lead_home else "away"} leads by {k}'][0] += 1
        C[f'after {n} full innings, {"home" if lead_home else "away"} leads by {k}'][1] += lost
        C[f'after {n} full innings, leader by {k}'][0] += 1
        C[f'after {n} full innings, leader by {k}'][1] += lost
    # after top of 9th: away leads by k going into bottom 9
    sa = sum((x or 0) for x in a[:9]); sh = sum((x or 0) for x in h[:8])
    d = sa - sh
    if d > 0:
        k = min(d, 8)
        C[f'away leads by {k} entering bottom 9'][0] += 1
        C[f'away leads by {k} entering bottom 9'][1] += (H > A)
out = {k: {'n': v[0], 'lost': v[1]} for k, v in sorted(C.items())}
json.dump({'games': len(games), 'states': out}, open(R + 'results/2026-10-05-comeback-mlb.json', 'w'), indent=0)
for k, v in sorted(C.items()):
    if 'leader by' in k or 'entering' in k:
        ub = 3 / v[0] if v[1] == 0 else None
        print(f'{k:45s} n={v[0]:6d} lost={v[1]:4d} rate={v[1]/v[0]:.4f}')
