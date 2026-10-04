"""Idea #17 for NFL: totals / team totals / first-half totals that lock DURING the game once the Over is crossed.
Lock time = ESPN play 'wallclock' of the scoring play (play start; scoring plays are all reviewed, so we also
report fills >=120 s after it). Trades from the Data API as in locked_props_scan.py.
Usage: python3 lab/locked_props_nfl.py 20260917 20261003  -> lab/data/raw/2026-10-04-locked-props-nfl.json"""
import json, sys, time, re
from datetime import datetime, timedelta, date
sys.path.insert(0, '/home/user/polysweeper-v1/lab')
from locked_props_scan import get, iso, trades
from concurrent.futures import ThreadPoolExecutor
def game(ev):
    comp = ev['competitions'][0]
    tm = {c['homeAway']: c['team']['abbreviation'].lower() for c in comp['competitors']}
    a, h = tm['away'], tm['home']
    t0 = iso(ev['date'])
    pm = None
    for dd in {datetime.utcfromtimestamp(t0).date(), datetime.utcfromtimestamp(t0 - 6 * 3600).date()}:
        e = get(f'https://gamma-api.polymarket.com/events?slug=nfl-{a}-{h}-{dd}')
        if e: pm, slug = e[0], f'nfl-{a}-{h}-{dd}'
    if not pm: return []
    s = get('https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event=' + ev['id'])
    pl = [p for d in (s or {}).get('drives', {}).get('previous', []) for p in d.get('plays', []) if p.get('wallclock')]
    lk = {}
    for p in pl:
        A, H, q, t = p.get('awayScore', 0), p.get('homeScore', 0), p.get('period', {}).get('number', 0), iso(p['wallclock'])
        for x in range(0, 80):
            L = x + 0.5; tag = f'{x}pt5'
            for key, cond in ((f'total-{tag}', A + H > L), (f'team-total-{a}-{tag}', A > L), (f'team-total-{h}-{tag}', H > L),
                              (f'1h-total-{tag}', q <= 2 and A + H > L)):
                if cond and key not in lk: lk[key] = (t, q)
    out = []
    for m in pm['markets']:
        suf = m['slug'][len(slug) + 1:]
        if suf not in lk: continue
        lt, q = lk[suf]
        oc = json.loads(m['outcomes']); op = json.loads(m.get('outcomePrices') or '[]')
        if 'Over' not in oc: continue
        ok = bool(op) and float(op[oc.index('Over')]) > 0.99
        post = []
        for t in trades(m['conditionId']):
            dt = t['timestamp'] - lt
            if dt < 0: continue
            w = t['outcome'] == 'Over'
            if t['side'] == 'BUY' and w: k, px = 'taker_buy_win', t['price']
            elif t['side'] == 'SELL' and w: k, px = 'maker_bid_win', t['price']
            elif t['side'] == 'SELL': k, px = 'maker_bid_win_via_loser', 1 - t['price']
            else: k, px = 'taker_buy_loser', t['price']
            post.append((dt, k, round(px, 4), t['size']))
        ct = m.get('closedTime')
        out.append(dict(slug=m['slug'], win='Over', lock=lt, inn=q, settled_ok=ok, closed=iso(ct.replace(' ', 'T').replace('+00', '+00:00')) if ct else None, post=post))
    return out
d0, d1 = sys.argv[1], sys.argv[2]
evs, d = [], date(int(d0[:4]), int(d0[4:6]), int(d0[6:]))
while d.strftime('%Y%m%d') <= d1:
    evs += (get(f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={d.strftime('%Y%m%d')}") or {}).get('events', [])
    d += timedelta(days=1)
evs = [e for e in evs if e['status']['type']['completed']]
print('games', len(evs), flush=True)
with ThreadPoolExecutor(4) as ex:
    allr = [r for rs in ex.map(game, evs) for r in rs]
json.dump(allr, open('/home/user/polysweeper-v1/lab/data/raw/2026-10-04-locked-props-nfl.json', 'w'))
print('locked markets', len(allr), 'settled as predicted', sum(r['settled_ok'] for r in allr))
