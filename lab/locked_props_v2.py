"""Idea #17 "locked lines", corrected re-measure (tester, 2026-10-04) after red-team review.
Fixes vs locked_props_scan.py / locked_props_nfl.py:
 1. 'maker_bid_win_via_loser' dropped (a taker SELLING the loser is not a maker buying the winner).
 2. SAFE time instead of lock time:
    MLB  = start of the first PITCH after the scoring play ends (statsapi playEvents); NRFI-No = first pitch
           of the 2nd inning; lock on the game's final play -> play end + 120 s.
    NFL  = wallclock of the first play after the scoring play that is not the try / a timeout / end of
           period (ESPN puts the try's points on the TD row, and wallclock = play START).
 3. Game matching: Gamma market gameStartTime within 15 min of official start + both team codes in slug;
    doubleheaders skipped.
Trades: reused from the earlier raw files where possible (they hold every trade after the old, earlier
lock), else fetched from the Data API.
Usage: python3 lab/locked_props_v2.py  -> lab/results/2026-10-04-locked-props-v2.json (+ raw per-market
file lab/data/raw/2026-10-04-locked-props-v2-raw.json)"""
import json, sys, time
from datetime import date, timedelta, datetime
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, '/home/user/polysweeper-v1/lab')
from locked_props_scan import get, iso, trades, PM
RAW = '/home/user/polysweeper-v1/lab/data/raw/'
OUT = '/home/user/polysweeper-v1/lab/results/2026-10-04-locked-props-v2.json'

def gst(m):
    s = m.get('gameStartTime')
    return iso(s.replace(' ', 'T').replace('+00', '+00:00')) if s else None

def find_event(prefix, a, h, t0, dates):
    for d in dates:
        e = get(f'https://gamma-api.polymarket.com/events?slug={prefix}-{a}-{h}-{d}')
        if not e: continue
        ms = [m for m in e[0]['markets'] if gst(m)]
        if ms and abs(gst(ms[0]) - t0) <= 900:
            return e[0], f'{prefix}-{a}-{h}-{d}'
    return None, None

# ---------------- MLB ----------------
def mlb_locks(feed, away, home):
    plays = [p for p in feed['liveData']['plays']['allPlays'] if p['about'].get('endTime')]
    pitches = sorted(iso(e['startTime']) for p in plays for e in p['playEvents']
                     if e.get('isPitch') and e.get('startTime'))
    def next_pitch(t):
        for x in pitches:
            if x > t: return x, 'next_pitch'
        return t + 120, 'game_end+120'
    out, prev, rev = {}, (0, 0), []
    for p in plays:
        a, h = p['result']['awayScore'], p['result']['homeScore']
        t = iso(p['about']['endTime']); inn = p['about']['inning']
        if a < prev[0] or h < prev[1]: rev.append((t, prev, (a, h)))
        if (a, h) != prev:
            s, how = next_pitch(t)
            for x in range(30):
                L, tag = x + 0.5, f'{x}pt5'
                for key, cond in ((f'total-{tag}', a + h > L), (f'team-total-{away}-{tag}', a > L),
                                  (f'team-total-{home}-{tag}', h > L), (f'f5-total-{tag}', inn <= 5 and a + h > L)):
                    if cond and key not in out: out[key] = ('Over', t, s, how, inn)
            if inn == 1 and 'nrfi' not in out: out['nrfi'] = ('Yes', t, s, how, inn)
            prev = (a, h)
        if 'nrfi' not in out and inn > 1:
            last1 = [q for q in plays if q['about']['inning'] == 1][-1]
            t1 = iso(last1['about']['endTime']); s, how = next_pitch(t1)
            out['nrfi'] = ('No', t1, s, how, 1)
    return out, rev

def mlb_game(d, g):
    if g.get('doubleHeader', 'N') != 'N': return [], {'skip_dh': 1}
    away = g['teams']['away']['team']['abbreviation'].lower(); home = g['teams']['home']['team']['abbreviation'].lower()
    away, home = PM.get(away, away), PM.get(home, home)
    t0 = iso(g['gameDate'])
    ev, slug = find_event('mlb', away, home, t0, [d, datetime.utcfromtimestamp(t0).date()])
    if not ev: return [], {'no_event': 1}
    feed = get(f"https://statsapi.mlb.com/api/v1.1/game/{g['gamePk']}/feed/live")
    if not feed: return [], {'no_feed': 1}
    lk, rev = mlb_locks(feed, away, home)
    return markets(ev, slug, lk), {'reversals': rev}

# ---------------- NFL ----------------
SKIP_NFL = ('extra point', 'two-point', 'two point', 'pat', 'timeout', 'warning', 'end period', 'end of', 'end quarter', 'end half')
def nfl_locks(summ, a, h):
    pl = [p for d in (summ or {}).get('drives', {}).get('previous', []) for p in d.get('plays', []) if p.get('wallclock')]
    out, prev, rev = {}, (0, 0), []
    for i, p in enumerate(pl):
        if 'awayScore' not in p or 'homeScore' not in p: continue
        if any(k in (p.get('type', {}).get('text') or '').lower() for k in SKIP_NFL): continue   # timeouts carry 0-0
        A, H, q, t = p.get('awayScore', 0), p.get('homeScore', 0), p.get('period', {}).get('number', 0), iso(p['wallclock'])
        if A < prev[0] or H < prev[1]: rev.append((t, prev, (A, H)))
        if (A, H) != prev:
            s, how = t + 900, 'no_next_play+900'
            for r in pl[i + 1:]:
                ty = (r.get('type', {}).get('text') or '').lower()
                if any(k in ty for k in SKIP_NFL): continue
                if iso(r['wallclock']) > t: s, how = iso(r['wallclock']), 'next_play'; break
            for x in range(80):
                L, tag = x + 0.5, f'{x}pt5'
                for key, cond in ((f'total-{tag}', A + H > L), (f'team-total-{a}-{tag}', A > L),
                                  (f'team-total-{h}-{tag}', H > L), (f'1h-total-{tag}', q <= 2 and A + H > L)):
                    if cond and key not in out: out[key] = ('Over', t, s, how, q)
            prev = (A, H)
    return out, rev

def nfl_game(ev):
    comp = ev['competitions'][0]
    tm = {c['homeAway']: c['team']['abbreviation'].lower() for c in comp['competitors']}
    tm = {k: {'wsh': 'was', 'lar': 'la'}.get(v, v) for k, v in tm.items()}
    a, h = tm['away'], tm['home']; t0 = iso(ev['date'])
    pe, slug = find_event('nfl', a, h, t0, sorted({datetime.utcfromtimestamp(t0).date(), datetime.utcfromtimestamp(t0 - 6 * 3600).date()}))
    if not pe: return [], {'no_event': 1}
    s = get('https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event=' + ev['id'])
    lk, rev = nfl_locks(s, a, h)
    return markets(pe, slug, lk), {'reversals': rev}

# ---------------- common ----------------
OLD = {}
for f in ('2026-09-26-locked-props.json', '2026-10-03-locked-props.json', '2026-10-04-locked-props-nfl.json'):
    for x in json.load(open(RAW + f)): OLD[x['slug']] = x

def markets(ev, slug, lk):
    res = []
    for m in ev['markets']:
        suf = m['slug'][len(slug) + 1:]
        if suf not in lk: continue
        win, lt, safe, how, inn = lk[suf]
        oc = json.loads(m['outcomes']); op = json.loads(m.get('outcomePrices') or '[]')
        if win not in oc: continue
        res_p = float(op[oc.index(win)]) if op else None
        o = OLD.get(m['slug'])
        if o and o['lock'] <= safe:   # old raw holds every trade after the old (earlier) lock, as (dt, kind, px, size)
            # rebuild raw: taker_buy_win / maker_bid_win are winner-side; drop *_via_loser and taker_buy_loser
            tr = [(o['lock'] + p[0], p[1], p[2], p[3]) for p in o['post'] if p[1] in ('taker_buy_win', 'maker_bid_win')]
        else:
            tr = []
            for t in trades(m['conditionId']):
                if t['outcome'] != win: continue
                tr.append((t['timestamp'], 'taker_buy_win' if t['side'] == 'BUY' else 'maker_bid_win', t['price'], t['size']))
        post = [(round(ts - safe, 1), k, px, sz) for ts, k, px, sz in tr if ts >= lt]
        ct = m.get('closedTime')
        res.append(dict(slug=m['slug'], win=win, lock=lt, safe=safe, how=how, inn=inn, res_price=res_p,
                        uma=m.get('umaResolutionStatus'), rate=(m.get('feeSchedule') or {}).get('rate', 0.05),
                        delay=m.get('secondsDelay'),
                        closed=iso(ct.replace(' ', 'T').replace('+00', '+00:00')) if ct else None, post=post))
    return res

def summarize(rows, days):
    ok = [r for r in rows if r['res_price'] is not None and r['res_price'] > 0.99]
    bad = [dict(slug=r['slug'], res=r['res_price'], uma=r['uma']) for r in rows if r['res_price'] is not None and r['res_price'] <= 0.99]
    o = dict(locked_markets=len(rows), settled_as_predicted=len(ok), against_arithmetic=bad,
             unresolved=sum(r['res_price'] is None for r in rows),
             safe_how={k: sum(r['how'] == k for r in rows) for k in {r['how'] for r in rows}},
             median_safe_minus_lock_s=sorted(r['safe'] - r['lock'] for r in rows)[len(rows) // 2] if rows else None,
             seconds_delay_values=sorted({str(r['delay']) for r in rows}))
    for cap in (0.99, 0.985):
        for off in (0, 30, 120):
            mk = sh = usd = edge = 0; low = 0
            for r in ok:
                f = [p for p in r['post'] if p[0] >= off and p[1] == 'taker_buy_win' and p[2] <= cap]
                s = sum(p[3] for p in f)
                low += sum(p[3] for p in f if p[2] < 0.9)
                if s >= 5: mk += 1
                sh += s; usd += sum(p[2] * p[3] for p in f)
                edge += sum(p[3] * ((1 - p[2]) - r['rate'] * p[2] * (1 - p[2])) for p in f)
            o[f'taker_ask_le{cap}_safe+{off}s'] = dict(markets_ge5sh=mk, shares=round(sh), usd=round(usd), edge_usd=round(edge, 2),
                                                       edge_usd_per_day=round(edge / days, 2), shares_below_090=round(low))
    for off in (0, 120):
        f = [(r, p) for r in ok for p in r['post'] if p[0] >= off and p[1] == 'maker_bid_win' and 0.9 <= p[2] <= 0.99]
        o[f'resting_bid_fills_0.90-0.99_safe+{off}s'] = dict(markets=len({r['slug'] for r, _ in f}), shares=round(sum(p[3] for _, p in f)))
    # time from safe to close
    d = sorted(r['closed'] - r['safe'] for r in ok if r['closed'])
    o['median_s_safe_to_close'] = round(d[len(d) // 2]) if d else None
    return o

if __name__ == '__main__':
    jobs, d = [], date(2026, 9, 20)
    while d <= date(2026, 10, 3):
        s = get(f'https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={d}&hydrate=team')
        for dd in (s or {}).get('dates', []):
            for g in dd['games']:
                if g['status']['abstractGameState'] == 'Final': jobs.append((str(d), g))
        d += timedelta(days=1)
    nfl, d = [], date(2026, 9, 17)
    while d <= date(2026, 10, 3):
        nfl += (get(f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={d.strftime('%Y%m%d')}") or {}).get('events', [])
        d += timedelta(days=1)
    nfl = [e for e in nfl if e['status']['type']['completed']]
    print('mlb games', len(jobs), 'nfl games', len(nfl), flush=True)
    with ThreadPoolExecutor(4) as ex:
        mr = list(ex.map(lambda j: mlb_game(*j), jobs))
        nr = list(ex.map(nfl_game, nfl))
    out = {}
    for name, rs, days in (('MLB 2026-09-20..10-03', mr, 14), ('NFL 2026-09-17..10-03', nr, 17)):
        rows = [x for r, _ in rs for x in r]
        info = [i for _, i in rs]
        o = summarize(rows, days)
        o['games'] = len(rs); o['matched_games'] = sum(1 for r, _ in rs if r)
        o['skipped_doubleheaders'] = sum(i.get('skip_dh', 0) for i in info)
        o['no_event'] = sum(i.get('no_event', 0) for i in info)
        o['score_reversals'] = [x for i in info for x in i.get('reversals', [])]
        out[name] = o
        json.dump(rows, open(RAW + f"2026-10-04-locked-props-v2-{name[:3].lower()}-raw.json", 'w'))
    json.dump(out, open(OUT, 'w'), indent=1)
    print(json.dumps(out, indent=1)[:6000])
