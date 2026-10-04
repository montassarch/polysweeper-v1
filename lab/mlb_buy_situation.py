"""Idea #15/#17 prototype: rebuild the game situation (inning, outs, score) at each 0.95+ MLB buy of
wallet 0x4dDC... using the free MLB Stats API play-by-play (each play has an end timestamp).
Input: lab/data/raw/2026-10-04-lockedline-wallet.json (from lockedline_wallet.py).
Output: lab/data/raw/2026-10-04-mlb-buy-situation.json + printed table."""
import json, sys, re, time, urllib.request, collections
from datetime import datetime, timezone
R = '/home/user/polysweeper-v1/lab/'
UA = {'User-Agent': 'polysweeper-research/0.1 (read-only)'}
def get(u):
    return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30))
def iso(s):
    return datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp()
rows = [r for r in json.load(open(R + 'data/raw/2026-10-04-lockedline-wallet.json')) if r['slug'].startswith('mlb-')]
sched, feeds, out = {}, {}, []
ALIAS = {'cws': 'cws', 'chw': 'cws', 'kc': 'kc', 'sd': 'sd', 'sf': 'sf', 'tb': 'tb', 'az': 'az', 'ari': 'az', 'wsh': 'wsh', 'was': 'wsh', 'ath': 'ath', 'oak': 'ath'}
for r in rows:
    m = re.match(r'mlb-([a-z]+)-([a-z]+)-(\d{4}-\d{2}-\d{2})-?(.*)', r['slug'])
    a, h, d, kind = m.groups()
    if d not in sched:
        sched[d] = get(f'https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={d}&hydrate=team')['dates']
        time.sleep(0.2)
    pk = None
    for dd in sched[d]:
        for g in dd['games']:
            ab = (g['teams']['away']['team']['abbreviation'].lower(), g['teams']['home']['team']['abbreviation'].lower())
            if ALIAS.get(ab[0], ab[0]) == ALIAS.get(a, a) and ALIAS.get(ab[1], ab[1]) == ALIAS.get(h, h):
                pk = g['gamePk']
    if not pk:
        out.append(dict(r, err='nogame')); continue
    if pk not in feeds:
        feeds[pk] = get(f'https://statsapi.mlb.com/api/v1.1/game/{pk}/feed/live'); time.sleep(0.2)
    f = feeds[pk]
    plays = [p for p in f['liveData']['plays']['allPlays'] if p['about'].get('endTime')]
    end = iso(plays[-1]['about']['endTime'])
    st = None
    for p in plays:
        if iso(p['about']['endTime']) <= r['ts']:
            st = p
    s = dict(inning=st['about']['inning'] if st else 0, half=st['about']['halfInning'] if st else '-',
             outs=st['count']['outs'] if st else 0, away=st['result']['awayScore'] if st else 0,
             home=st['result']['homeScore'] if st else 0) if st else dict(inning=0, half='-', outs=0, away=0, home=0)
    tot = s['away'] + s['home']
    first_runs = None
    fi = [p for p in plays if p['about']['inning'] == 1]
    # locked logic
    line = re.search(r'(\d+)pt(\d)', kind)
    line = float(line.group(1) + '.' + line.group(2)) if line else None
    after_end = r['ts'] >= end
    locked = False
    if kind.startswith('total') and r['outcome'] == 'Over': locked = tot > line
    elif kind.startswith('total') and r['outcome'] == 'Under': locked = after_end and tot < line
    elif kind == 'nrfi' and r['outcome'] == 'No':
        locked = any(iso(p['about']['endTime']) <= r['ts'] and p['about']['inning'] == 1 and (p['result']['awayScore'] + p['result']['homeScore']) > 0 for p in fi)
    elif kind == 'nrfi' and r['outcome'] == 'Yes':
        locked = (s['inning'] > 1 or (s['inning'] == 1 and s['half'] == 'bottom' and s['outs'] == 3)) and all((p['result']['awayScore'] + p['result']['homeScore']) == 0 for p in fi)
    elif kind.startswith('f5'): locked = None
    else: locked = after_end
    out.append(dict(r, pk=pk, kind=re.sub(r'\d+pt\d', 'X', kind) or 'moneyline', line=line, secs_to_end=round(r['ts'] - end), locked=locked, **s))
json.dump(out, open(R + 'data/raw/2026-10-04-mlb-buy-situation.json', 'w'), indent=0)
c = collections.Counter((o.get('kind'), o['outcome'] if o['outcome'] in ('Over', 'Under', 'Yes', 'No') else 'team', o.get('locked'), o.get('res')) for o in out)
for k, v in sorted(c.items(), key=lambda x: -x[1]): print(k, v)
