"""NFL comeback rates from ESPN's free site API (scoring plays with quarter and clock).
State: a team leads by >= L at some moment in quarter Q (first time reached). Did it lose (or tie)?
Output: lab/results/2026-10-05-comeback-nfl.json"""
import json, os, sys, time, urllib.request, collections
UA = {'User-Agent': 'polysweeper-research/0.1 (read-only)'}
RAW = '/home/user/polysweeper-v1/lab/data/raw/nfl_espn/'
os.makedirs(RAW, exist_ok=True)


def get(u):
    for i in range(3):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60))
        except Exception as e:
            err = e; time.sleep(3)
    print('fail', u, err, flush=True)


B = 'https://site.api.espn.com/apis/site/v2/sports/football/'
league = sys.argv[1] if len(sys.argv) > 1 else 'nfl'
years = range(2014, 2026) if league == 'nfl' else range(2015, 2026)
for yr in years:
    f = RAW + f'{league}-{yr}.json'
    if os.path.exists(f): continue
    games = {}
    weeks = [(2, w) for w in range(1, 19)] + [(3, w) for w in range(1, 6)] if league == 'nfl' else \
            [(2, w) for w in range(1, 17)] + [(3, 1)]
    for st, w in weeks:
        extra = '&groups=80&limit=300' if league == 'college-football' else ''
        d = get(B + f'{league}/scoreboard?dates={yr}&seasontype={st}&week={w}{extra}')
        if not d: continue
        for e in d.get('events', []):
            if e['status']['type'].get('completed'):
                c = e['competitions'][0]['competitors']
                games[e['id']] = {x['homeAway']: (x['team']['abbreviation'], int(x['score'])) for x in c}
        time.sleep(0.2)
    from concurrent.futures import ThreadPoolExecutor
    def one(item):
        gid, teams = item
        s = get(B + f'{league}/summary?event={gid}')
        if not s: return None
        sp = [(p['period']['number'], p['clock']['value'], p['awayScore'], p['homeScore']) for p in s.get('scoringPlays', [])]
        return dict(id=gid, teams=teams, sp=sp)
    print(league, yr, 'games listed', len(games), flush=True)
    with ThreadPoolExecutor(6) as ex_:
        out = [r for r in ex_.map(one, games.items()) if r]
    json.dump(out, open(f, 'w'))
    print(league, yr, len(out), flush=True)

# analysis
C = collections.defaultdict(lambda: [0, 0])
ex = []
for f in sorted(os.listdir(RAW)):
    if not f.startswith(league + '-'): continue
    for g in json.load(open(RAW + f)):
        A, H = g['teams']['away'][1], g['teams']['home'][1]
        seen = set()
        for q, clk, a, h in g['sp']:
            d = h - a
            if d == 0: continue
            lead_home = d > 0
            won = (H > A) if lead_home else (A > H)
            qq = min(q, 5)
            for L in (14, 17, 21, 24, 28):
                if abs(d) >= L and (L, qq) not in seen:
                    seen.add((L, qq))
                    k = f'lead>={L} reached in Q{qq}' if qq < 5 else f'lead>={L} in OT'
                    C[k][0] += 1; C[k][1] += (not won)
                    if not won and L >= 17: ex.append((g['id'], k, g['teams'], A, H))
        # Q4 with time left: lead >=L with <= 5:00 left, checked at scoring plays only (lower bound on exposure)
res = {k: {'n': v[0], 'lost_or_tied': v[1]} for k, v in sorted(C.items())}
json.dump({'league': league, 'states': res, 'losses': ex}, open(
    f'/home/user/polysweeper-v1/lab/results/2026-10-05-comeback-{league}.json', 'w'), indent=0)
for k, v in sorted(C.items()):
    print(f'{k:28s} n={v[0]:5d} lost/tied={v[1]:3d}')
for e in ex: print(e)
