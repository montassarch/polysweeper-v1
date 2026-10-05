"""Were MLB leaders still for sale at <= 0.99 on Polymarket when the lead was big late in the game?
Games Aug-Sep 2026 with a lead of >= 4 runs after 8 full innings (from the linescore cache of comeback_mlb.py).
Window = from the end of the 8th inning to the final out (MLB Stats API play timestamps).
Polymarket trades (data-api, by condition id) on the leader's outcome in that window, by price band.
Output: lab/results/2026-10-05-mlb-biglead-supply.json"""
import json, glob, time, urllib.request, collections
from datetime import datetime
UA = {'User-Agent': 'polysweeper-research/0.1 (read-only)'}
def get(u):
    for i in range(3):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60))
        except Exception as e: err = e; time.sleep(2)
    print('fail', u[:90], err); return None
def iso(s): return datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp()
ALIAS = {'chw': 'cws', 'ari': 'az', 'was': 'wsh', 'oak': 'ath'}
import os
for mo in (8, 9):
    f = f'/home/user/polysweeper-v1/lab/data/raw/mlb_linescores/2026-{mo:02d}.json'
    if not os.path.exists(f):
        d = get(f'https://statsapi.mlb.com/api/v1/schedule?sportId=1&gameType=R&startDate=2026-{mo:02d}-01&endDate=2026-{mo:02d}-{31 if mo == 8 else 30}&hydrate=linescore')
        json.dump(d, open(f, 'w'))
cand = []
for f in sorted(glob.glob('/home/user/polysweeper-v1/lab/data/raw/mlb_linescores/2026-0[89].json')):
    for dd in json.load(open(f)).get('dates', []):
        for g in dd['games']:
            inn = g.get('linescore', {}).get('innings', [])
            if g.get('status', {}).get('abstractGameState') != 'Final' or len(inn) < 9: continue
            a = sum((i.get('away', {}).get('runs') or 0) for i in inn[:8]); h = sum((i.get('home', {}).get('runs') or 0) for i in inn[:8])
            if abs(a - h) >= 4:
                cand.append((g['gamePk'], dd['date'], a - h))
print('candidate games', len(cand))
sched = {}
out = []
for pk, date, diff in cand:
    feed = get(f'https://statsapi.mlb.com/api/v1.1/game/{pk}/feed/live')
    if not feed: continue
    gd = feed['gameData']
    ab = [gd['teams'][s]['abbreviation'].lower() for s in ('away', 'home')]
    ab = [ALIAS.get(x, x) for x in ab]
    plays = [p for p in feed['liveData']['plays']['allPlays'] if p['about'].get('endTime')]
    p8 = [p for p in plays if p['about']['inning'] <= 8]
    t0 = iso(p8[-1]['about']['endTime']); t1 = iso(plays[-1]['about']['endTime'])
    fa, fh = plays[-1]['result']['awayScore'], plays[-1]['result']['homeScore']
    leader_home = diff < 0
    lead_won = (fh > fa) if leader_home else (fa > fh)
    slug = f'mlb-{ab[0]}-{ab[1]}-{date}'
    ev = get(f'https://gamma-api.polymarket.com/events?slug={slug}')
    if not ev:
        out.append(dict(pk=pk, slug=slug, err='noevent')); continue
    mk = [m for m in ev[0]['markets'] if m.get('sportsMarketType') == 'moneyline' or m['slug'] == slug]
    if not mk:
        out.append(dict(pk=pk, slug=slug, err='nomarket')); continue
    m = mk[0]
    outs = json.loads(m['outcomes'])
    leader_name = gd['teams']['home' if leader_home else 'away']['teamName']
    li = [i for i, o in enumerate(outs) if leader_name.lower() in o.lower() or o.lower() in gd['teams']['home' if leader_home else 'away']['name'].lower()]
    if not li:
        out.append(dict(pk=pk, slug=slug, err='nooutcome', outs=outs)); continue
    lo = outs[li[0]]
    trades, off = [], 0
    while off < 3000:
        t = get(f'https://data-api.polymarket.com/trades?market={m["conditionId"]}&limit=500&offset={off}&takerOnly=true')
        if not t: break
        trades += t
        if len(t) < 500 or min(x['timestamp'] for x in t) < t0: break
        off += 500
        time.sleep(0.2)
    win = [x for x in trades if t0 <= x['timestamp'] <= t1 and x['outcome'] == lo and x['side'] == 'BUY']
    bands = collections.Counter()
    for x in win:
        p = float(x['price']); b = '<0.96' if p < 0.96 else '0.96-0.98' if p < 0.98 else '0.98-0.99' if p <= 0.99 else '0.991-0.999' if p <= 0.999 else '1'
        bands[b] += float(x['size'])
    out.append(dict(pk=pk, slug=slug, lead=abs(diff), won=lead_won, window_min=round((t1 - t0) / 60, 1),
                    shares_by_band={k: round(v) for k, v in bands.items()}, n_trades=len(win)))
    time.sleep(0.2)
json.dump(out, open('/home/user/polysweeper-v1/lab/results/2026-10-05-mlb-biglead-supply.json', 'w'), indent=0)
ok = [o for o in out if 'err' not in o]
print('matched', len(ok), 'errors', collections.Counter(o['err'] for o in out if 'err' in o))
S = collections.defaultdict(lambda: collections.Counter())
for o in ok:
    k = min(o['lead'], 7)
    S[k]['games'] += 1
    S[k]['won'] += o['won']
    for b, v in o['shares_by_band'].items():
        if v >= 5: S[k]['games with ' + b] += 1
        S[k]['shares ' + b] += v
for k in sorted(S): print('lead', k, dict(S[k]))
