"""How often does the LEADING tennis player retire (= a loss for us under Polymarket rules: retirement -> the
player who advances wins)? ESPN free scoreboard, set scores + status. Sample: every 2nd day of 2025, ATP + WTA.
Counts matches where the retiring player was up a set (Bo3) and/or ahead in the current set by >= 3 games.
Output: lab/results/2026-10-05-tennis-retirements.json"""
import json, os, time, urllib.request, datetime, collections
UA = {'User-Agent': 'polysweeper-research/0.1 (read-only)'}
OUT = '/home/user/polysweeper-v1/lab/data/raw/tennis_espn_2025.json'
rows = json.load(open(OUT)) if os.path.exists(OUT) else []
if not rows:
    d0 = datetime.date(2025, 1, 1)
    seen = set()
    for i in range(0, 365, 2):
        day = (d0 + datetime.timedelta(days=i)).strftime('%Y%m%d')
        for tour in ('atp', 'wta'):
            u = f'https://site.api.espn.com/apis/site/v2/sports/tennis/{tour}/scoreboard?dates={day}'
            try:
                d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60))
            except Exception as e:
                print('err', day, tour, e, flush=True); continue
            for ev in d.get('events', []):
                for g in ev.get('groupings', []):
                    gname = g.get('grouping', {}).get('displayName', '')
                    if 'Singles' not in gname: continue
                    for c in g['competitions']:
                        if c['id'] in seen: continue
                        seen.add(c['id'])
                        st = c['status']['type'].get('description')
                        if st not in ('Final', 'Retired'): continue
                        cs = c['competitors']
                        if len(cs) != 2: continue
                        rows.append(dict(id=c['id'], tour=tour, ev=ev.get('name'), st=st,
                                         w=[x.get('winner') for x in cs],
                                         ls=[[l.get('value') for l in x.get('linescores', [])] for x in cs]))
            time.sleep(0.3)
        if i % 40 == 0: print(day, len(rows), flush=True)
    json.dump(rows, open(OUT, 'w'))
C = collections.Counter()
ex = []
for r in rows:
    C[(r['tour'], 'matches')] += 1
    if r['st'] != 'Retired': continue
    C[(r['tour'], 'retired')] += 1
    wi = 0 if r['w'][0] else 1
    lo = 1 - wi  # the retiring player = the non-winner
    a, b = r['ls'][lo], r['ls'][wi]
    if not a or len(a) != len(b): continue
    sets_lo = sum(1 for x, y in zip(a[:-1], b[:-1]) if x > y)
    sets_wi = sum(1 for x, y in zip(a[:-1], b[:-1]) if y > x)
    cur = (a[-1] or 0) - (b[-1] or 0)
    if sets_lo > sets_wi:
        C[(r['tour'], 'retiring player was a set up')] += 1
        if cur >= 3:
            C[(r['tour'], 'retiring player a set up AND >=3 games ahead in current set')] += 1; ex.append((r['ev'], a, b))
    if sets_lo == sets_wi and cur >= 3 and len(a) >= 3:
        C[(r['tour'], 'retiring player >=3 games ahead in deciding set')] += 1; ex.append((r['ev'], a, b))
    if sets_lo >= sets_wi and cur >= 1:
        C[(r['tour'], 'retiring player ahead on sets-or-level and ahead in current set')] += 1
res = {f'{k[0]} | {k[1]}': v for k, v in sorted(C.items())}
json.dump({'counts': res, 'examples': ex[:20]}, open('/home/user/polysweeper-v1/lab/results/2026-10-05-tennis-retirements.json', 'w'), indent=1)
for k, v in res.items(): print(k, v)
for e in ex[:10]: print(e)
