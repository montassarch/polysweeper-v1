"""Idea #17 "locked lines": MLB side markets that become mathematically certain DURING the game
(total Over X once runs > X; team-total Over; first-5-innings Over; NRFI Yes once a run scores in the 1st,
NRFI No once the 1st inning ends 0-0). For each such market: lock time from the free MLB Stats API
play-by-play (endTime of the play that locked it, conservative), then every public trade (Data API,
taker side) AFTER the lock: at what price could the winner be bought, how much, how fast, and when the
market closed. Usage: python3 lab/locked_props_scan.py 2026-09-20 2026-10-03
Output: lab/data/raw/<last date>-locked-props.json + printed summary."""
import json, re, sys, time, urllib.request, collections
from datetime import datetime, timezone, date, timedelta
from concurrent.futures import ThreadPoolExecutor
UA = {'User-Agent': 'polysweeper-research/0.1 (read-only)'}
R = '/home/user/polysweeper-v1/lab/'
def get(u, tries=3):
    for i in range(tries):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30))
        except Exception as e:
            time.sleep(1 + i)
    return None
def iso(s): return datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp()
PM = {'az': 'ari', 'ath': 'oak', 'chw': 'cws'}
def locks_for(feed, away, home):
    """returns dict market-suffix -> (winning outcome, lock ts, inning)"""
    plays = [p for p in feed['liveData']['plays']['allPlays'] if p['about'].get('endTime')]
    out = {}
    first_cross = {}  # key -> ts
    prev = (0, 0)
    for p in plays:
        a, h = p['result']['awayScore'], p['result']['homeScore']
        t = iso(p['about']['endTime']); inn = p['about']['inning']
        if (a, h) != prev:
            for x in range(0, 30):
                L = x + 0.5
                tag = f'{x}pt5'
                if a + h > L and f'total-{tag}' not in out: out[f'total-{tag}'] = ('Over', t, inn)
                if a > L and f'team-total-{away}-{tag}' not in out: out[f'team-total-{away}-{tag}'] = ('Over', t, inn)
                if h > L and f'team-total-{home}-{tag}' not in out: out[f'team-total-{home}-{tag}'] = ('Over', t, inn)
                if inn <= 5 and a + h > L and f'f5-total-{tag}' not in out: out[f'f5-total-{tag}'] = ('Over', t, inn)
            if inn == 1 and 'nrfi' not in out: out['nrfi'] = ('Yes', t, inn)
            prev = (a, h)
        if 'nrfi' not in out and (inn > 1):
            # first play of 2nd inning started -> 1st ended scoreless; use end of last 1st-inning play
            last1 = [q for q in plays if q['about']['inning'] == 1][-1]
            out['nrfi'] = ('No', iso(last1['about']['endTime']), 1)
    return out
def trades(cid):
    rows, off = [], 0
    while off <= 3000:
        pg = get(f'https://data-api.polymarket.com/trades?market={cid}&limit=500&offset={off}')
        if not pg: break
        rows += pg
        if len(pg) < 500: break
        off += 500
    return rows
def game(d, g):
    away = g['teams']['away']['team']['abbreviation'].lower(); home = g['teams']['home']['team']['abbreviation'].lower()
    away, home = PM.get(away, away), PM.get(home, home)
    ev = get(f'https://gamma-api.polymarket.com/events?slug=mlb-{away}-{home}-{d}')
    if not ev: return []
    feed = get(f"https://statsapi.mlb.com/api/v1.1/game/{g['gamePk']}/feed/live")
    if not feed: return []
    lk = locks_for(feed, away, home)
    res = []
    for m in ev[0]['markets']:
        suf = m['slug'][len(f'mlb-{away}-{home}-{d}-'):]
        if suf not in lk: continue
        win, lt, inn = lk[suf]
        oc = json.loads(m['outcomes']); op = json.loads(m.get('outcomePrices') or '[]')
        settled = op and float(op[oc.index(win)]) > 0.99
        tr = trades(m['conditionId'])
        post = []
        for t in tr:
            dt = t['timestamp'] - lt
            if dt < 0: continue
            w = t['outcome'] == win
            # effective price paid for the WINNER by whoever ended up long the winner
            if t['side'] == 'BUY' and w: kind, px = 'taker_buy_win', t['price']
            elif t['side'] == 'SELL' and w: kind, px = 'maker_bid_win', t['price']
            elif t['side'] == 'SELL' and not w: kind, px = 'maker_bid_win_via_loser', 1 - t['price']
            else: kind, px = 'taker_buy_loser', t['price']
            post.append((dt, kind, round(px, 4), t['size']))
        ct = m.get('closedTime')
        res.append(dict(slug=m['slug'], win=win, lock=lt, inn=inn, settled_ok=bool(settled), closed=iso(ct.replace(' ', 'T').replace('+00', '+00:00')) if ct else None,
                        n_trades=len(tr), post=post))
    return res
if __name__ == '__main__':
    d0, d1 = date.fromisoformat(sys.argv[1]), date.fromisoformat(sys.argv[2])
    jobs = []
    d = d0
    while d <= d1:
        s = get(f'https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={d}&hydrate=team')
        for dd in (s or {}).get('dates', []):
            for g in dd['games']:
                if g['status']['abstractGameState'] == 'Final': jobs.append((str(d), g))
        d += timedelta(days=1)
    print('games', len(jobs), flush=True)
    with ThreadPoolExecutor(4) as ex:
        allr = [r for rs in ex.map(lambda j: game(*j), jobs) for r in rs]
    json.dump(allr, open(R + f'data/raw/{d1}-locked-props.json', 'w'))
    print('locked markets', len(allr), 'settled as predicted', sum(r['settled_ok'] for r in allr))
