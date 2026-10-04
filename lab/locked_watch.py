"""Idea #17 "locked lines" LIVE shadow watcher (measurement only: no orders, no wallet).

Watches today's NFL (ESPN) and MLB (MLB Stats API) games. For every open Polymarket market of those games
whose result becomes arithmetic during play (game total / team total / NFL 1st-half total / MLB first-5 total
Overs, MLB NRFI both ways) it:
  1. detects the LOCK from the scoreboard (one request per sport every --poll s, default 5),
  2. finds the SAFE time from play-by-play (red-team guards):
       NFL: first play after the scoring play that is not the try / a timeout / end of period
            (ESPN puts the try's points on the TD row and wallclock = play START);
       MLB: first PITCH after the scoring play has ended (NRFI-No: first pitch of the 2nd inning),
  3. records the winner's order book (best ask, ask depth <=0.95/<=0.99/<=0.995) via CLOB POST /books at
     safe+0/10/30/60/120 s (measured from the moment we SAW the safe event) and once when the game is final,
  4. logs a pretend fill of 5 shares when asks <=0.99 are still resting after the guard (first time only),
  5. logs every score decrease / reversal (scoreboard and play-by-play).
Output: JSONL lab/data/raw/locked_watch/<UTC date>.jsonl, summary printed + written at the end.

Usage:
  python3 lab/locked_watch.py --minutes 120              # live, unattended, stops after 120 min
  python3 lab/locked_watch.py --replay-mlb 822679        # dry run: parse a finished MLB feed
  python3 lab/locked_watch.py --replay-nfl 401772...     # dry run: parse a finished ESPN NFL game
Stop early: Ctrl+C (summary still written)."""
import argparse, json, os, sys, time, traceback, urllib.request
from datetime import datetime, timezone, timedelta

UA = {'User-Agent': 'polysweeper-research/0.1 (read-only data collection)', 'Content-Type': 'application/json'}
GAMMA, CLOB = 'https://gamma-api.polymarket.com', 'https://clob.polymarket.com'
ESPN = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl'
MLBAPI = 'https://statsapi.mlb.com/api'
OUTDIR = '/home/user/polysweeper-v1/lab/data/raw/locked_watch/'
SNAPS = (0, 10, 30, 60, 120)
PM_MLB = {'az': 'ari', 'ath': 'oak', 'chw': 'cws'}
PM_NFL = {'wsh': 'was', 'lar': 'la'}   # ESPN -> Polymarket slug codes
SKIP_NFL = ('extra point', 'two-point', 'two point', 'pat', 'timeout', 'warning', 'end period', 'end of', 'end quarter', 'end half')
NREQ = {'n': 0}

def http(url, body=None, timeout=15, tries=2):
    for i in range(tries):
        try:
            NREQ['n'] += 1
            data = json.dumps(body).encode() if body is not None else None
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=UA), timeout=timeout) as r:
                return json.load(r)
        except Exception:
            time.sleep(0.5 + i)
    return None

def iso(s):
    s = s.replace(' ', 'T')
    if s.endswith('+00'): s += ':00'
    return datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp()

class Log:
    def __init__(self, path, echo=True):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.f, self.echo = open(path, 'a'), echo
    def __call__(self, kind, **kw):
        rec = dict(t=round(time.time(), 2), kind=kind, **kw)
        self.f.write(json.dumps(rec) + '\n'); self.f.flush()
        if self.echo and kind not in ('book',):
            print(datetime.utcnow().strftime('%H:%M:%S'), kind, json.dumps(kw)[:220], flush=True)

# ---------------------------------------------------------------- lock arithmetic (shared by live + replay)
def keys_locked(sport, a, h, A, H, period, inning1_over=False):
    """market-suffix -> winning outcome, for the score (A,H) reached in `period` (NFL quarter / MLB inning)."""
    out = {}
    for x in range(80 if sport == 'nfl' else 30):
        L, tag = x + 0.5, f'{x}pt5'
        if A + H > L: out[f'total-{tag}'] = 'Over'
        if A > L: out[f'team-total-{a}-{tag}'] = 'Over'
        if H > L: out[f'team-total-{h}-{tag}'] = 'Over'
        if sport == 'nfl' and period <= 2 and A + H > L: out[f'1h-total-{tag}'] = 'Over'
        if sport == 'mlb' and period <= 5 and A + H > L: out[f'f5-total-{tag}'] = 'Over'
    if sport == 'mlb' and period == 1 and A + H > 0: out['nrfi'] = 'Yes'
    return out

def nfl_scoring_and_safe(summary, A, H):
    """find the play where the score first became (A,H) and the safe time (first later non-try play)."""
    pl = [p for d in (summary or {}).get('drives', {}).get('previous', []) for p in d.get('plays', [])]
    cur = (summary or {}).get('drives', {}).get('current') or {}
    pl += [p for p in cur.get('plays', []) if p not in pl]
    pl = [p for p in pl if p.get('wallclock') and 'awayScore' in p and 'homeScore' in p
          and not ('timeout' in (p.get('type', {}).get('text') or '').lower() or 'warning' in (p.get('type', {}).get('text') or '').lower())]
    for i, p in enumerate(pl):
        if (p['awayScore'], p['homeScore']) == (A, H):
            t = iso(p['wallclock'])
            for r in pl[i + 1:]:
                ty = (r.get('type', {}).get('text') or '').lower()
                if any(k in ty for k in SKIP_NFL): continue
                if iso(r['wallclock']) > t:
                    return dict(score_play_t=t, score_play=(p.get('type', {}).get('text')), safe_t=iso(r['wallclock']),
                                safe_play=r.get('type', {}).get('text'), period=p.get('period', {}).get('number', 0))
            return dict(score_play_t=t, score_play=p.get('type', {}).get('text'), safe_t=None, period=p.get('period', {}).get('number', 0))
    return None

def nfl_scores_seq(summary):
    pl = [p for d in (summary or {}).get('drives', {}).get('previous', []) for p in d.get('plays', [])]
    return [(p['awayScore'], p['homeScore']) for p in pl if 'awayScore' in p and 'homeScore' in p
            and not any(k in (p.get('type', {}).get('text') or '').lower() for k in SKIP_NFL)]   # timeouts carry 0-0

def mlb_scoring_and_safe(feed, A, H):
    plays = feed['liveData']['plays']['allPlays']
    pitches = sorted(iso(e['startTime']) for p in plays for e in p['playEvents'] if e.get('isPitch') and e.get('startTime'))
    for p in plays:
        r = p['result']
        if (r.get('awayScore'), r.get('homeScore')) == (A, H) and p['about'].get('endTime') and p['about'].get('isComplete', True):
            t = iso(p['about']['endTime'])
            nxt = [x for x in pitches if x > t]
            return dict(score_play_t=t, score_play=r.get('event'), safe_t=nxt[0] if nxt else None, period=p['about']['inning'])
    return None

def mlb_inning1_scoreless_safe(feed):
    plays = feed['liveData']['plays']['allPlays']
    if any(p['about']['inning'] >= 2 for p in plays):
        if any(p['about']['inning'] == 1 and (p['result'].get('awayScore', 0) + p['result'].get('homeScore', 0)) > 0 for p in plays):
            return None
        p2 = [iso(e['startTime']) for p in plays if p['about']['inning'] >= 2 for e in p['playEvents'] if e.get('isPitch') and e.get('startTime')]
        return dict(score_play_t=None, score_play='end of 1st 0-0', safe_t=min(p2) if p2 else None, period=1)
    return None

# ---------------------------------------------------------------- Polymarket side
WANT = ('total-', 'team-total-', '1h-total-', 'f5-total-', 'nrfi')
def find_event(prefix, a, h, t0):
    for d, (x, y) in [(d, o) for d in sorted({datetime.utcfromtimestamp(t0).date(), datetime.utcfromtimestamp(t0 - 6 * 3600).date()})
                      for o in ((a, h), (h, a))]:
        slug = f'{prefix}-{x}-{y}-{d}'
        e = http(f'{GAMMA}/events?slug={slug}')
        if not e: continue
        ms = [m for m in e[0]['markets'] if m.get('gameStartTime')]
        if ms and abs(iso(ms[0]['gameStartTime']) - t0) <= 900:
            mk = {}
            for m in e[0]['markets']:
                suf = m['slug'][len(slug) + 1:]
                if not suf.startswith(WANT) or m.get('closed'): continue
                mk[suf] = dict(slug=m['slug'], outcomes=json.loads(m['outcomes']), tokens=json.loads(m.get('clobTokenIds') or '[]'),
                               rate=(m.get('feeSchedule') or {}).get('rate', 0.05), cid=m['conditionId'], delay=m.get('secondsDelay'))
            return slug, mk
    return None, {}

def books(tokens):
    out = {}
    for i in range(0, len(tokens), 40):
        r = http(f'{CLOB}/books', [{'token_id': t} for t in tokens[i:i + 40]]) or []
        for b in r:
            asks = sorted((float(x['price']), float(x['size'])) for x in b.get('asks', []))
            bids = sorted(((float(x['price']), float(x['size'])) for x in b.get('bids', [])), reverse=True)
            out[b.get('asset_id')] = dict(best_ask=asks[0][0] if asks else None, best_ask_sz=asks[0][1] if asks else 0,
                                          best_bid=bids[0][0] if bids else None,
                                          d95=round(sum(s for p, s in asks if p <= 0.95), 2), d99=round(sum(s for p, s in asks if p <= 0.99), 2),
                                          d995=round(sum(s for p, s in asks if p <= 0.995), 2),
                                          asks_le_099=[(p, s) for p, s in asks if p <= 0.99][:10])
    return out

def fill5(asks_le_099):
    need, cost = 5.0, 0.0
    for p, s in asks_le_099:
        take = min(need, s); cost += take * p; need -= take
        if need <= 0: return round(cost / 5, 4)
    return None

# ---------------------------------------------------------------- live watcher
class Game:
    def __init__(self, sport, gid, a, h, t0, slug, mk):
        self.sport, self.gid, self.a, self.h, self.t0, self.slug, self.mk = sport, gid, a, h, t0, slug, mk
        self.score = (0, 0); self.max = (0, 0); self.period = 0; self.final = False
        self.pending = {}      # (A,H) or 'nrfi0' -> list of suffixes waiting for safe time
        self.locked = {}       # suffix -> dict(win, token, lock_seen, safe_t, safe_seen, snaps_done, filled)
        self.final_done = False; self.pbp_last = None; self.nrfi_tried = False; self.last_pbp = 0

class Watcher:
    def __init__(self, log, poll):
        self.log, self.poll, self.games = log, poll, {}
        self.day = datetime.now(timezone.utc)

    def discover(self):
        now = time.time()
        # NFL (ESPN scoreboard groups games by US date)
        for d in {self.day.strftime('%Y%m%d'), (self.day - timedelta(hours=8)).strftime('%Y%m%d')}:
            sb = http(f'{ESPN}/scoreboard?dates={d}') or {}
            for ev in sb.get('events', []):
                key = 'nfl:' + ev['id']
                if key in self.games and self.games[key].slug: continue
                t0 = iso(ev['date'])
                if ev['status']['type']['completed'] or not (-6 * 3600 < now - t0 < 6 * 3600 or 0 < t0 - now < 3 * 3600): continue
                comp = ev['competitions'][0]
                tm = {c['homeAway']: c['team']['abbreviation'].lower() for c in comp['competitors']}
                tm = {k: PM_NFL.get(v, v) for k, v in tm.items()}
                slug, mk = find_event('nfl', tm['away'], tm['home'], t0)
                self.games[key] = Game('nfl', ev['id'], tm['away'], tm['home'], t0, slug, mk)
                self.log('game', sport='nfl', gid=ev['id'], slug=slug, markets=len(mk), start=ev['date'])
        # MLB
        for d in {self.day.date(), (self.day - timedelta(hours=8)).date()}:
            s = http(f'{MLBAPI}/v1/schedule?sportId=1&date={d}&hydrate=team') or {}
            for dd in s.get('dates', []):
                for g in dd['games']:
                    key = f"mlb:{g['gamePk']}"
                    if key in self.games and (self.games[key] is None or self.games[key].slug): continue
                    t0 = iso(g['gameDate'])
                    if g['status']['abstractGameState'] == 'Final' or not (-6 * 3600 < now - t0 < 6 * 3600 or 0 < t0 - now < 3 * 3600): continue
                    if g.get('doubleHeader', 'N') != 'N':
                        self.games[key] = None; self.log('skip_doubleheader', gid=g['gamePk']); continue
                    a = g['teams']['away']['team']['abbreviation'].lower(); h = g['teams']['home']['team']['abbreviation'].lower()
                    a, h = PM_MLB.get(a, a), PM_MLB.get(h, h)
                    slug, mk = find_event('mlb', a, h, t0)
                    self.games[key] = Game('mlb', g['gamePk'], a, h, t0, slug, mk)
                    self.log('game', sport='mlb', gid=g['gamePk'], slug=slug, markets=len(mk), start=g['gameDate'])

    def scores(self):
        """one scoreboard request per sport -> {key: (A, H, period, final, live)}"""
        out = {}
        if any(k.startswith('nfl') and g for k, g in self.games.items()):
            for d in {self.day.strftime('%Y%m%d'), (self.day - timedelta(hours=8)).strftime('%Y%m%d')}:
                for ev in (http(f'{ESPN}/scoreboard?dates={d}') or {}).get('events', []):
                    c = {x['homeAway']: int(x.get('score') or 0) for x in ev['competitions'][0]['competitors']}
                    st = ev['status']
                    out['nfl:' + ev['id']] = (c['away'], c['home'], st.get('period', 0), st['type']['completed'], st['type']['state'] == 'in')
        if any(k.startswith('mlb') and g for k, g in self.games.items()):
            for d in {self.day.date(), (self.day - timedelta(hours=8)).date()}:
                s = http(f'{MLBAPI}/v1/schedule?sportId=1&date={d}&hydrate=linescore') or {}
                for dd in s.get('dates', []):
                    for g in dd['games']:
                        ls = g.get('linescore') or {}
                        A = (ls.get('teams', {}).get('away', {}) or {}).get('runs', 0) or 0
                        H = (ls.get('teams', {}).get('home', {}) or {}).get('runs', 0) or 0
                        out[f"mlb:{g['gamePk']}"] = (A, H, ls.get('currentInning', 0) or 0, g['status']['abstractGameState'] == 'Final',
                                                    g['status']['abstractGameState'] == 'Live')
        return out

    def token_of(self, g, suf, win):
        m = g.mk.get(suf)
        if not m or win not in m['outcomes'] or len(m['tokens']) != len(m['outcomes']): return None
        return m['tokens'][m['outcomes'].index(win)]

    def step(self):
        now = time.time()
        sc = self.scores()
        for key, g in self.games.items():
            if not g or g.final_done or key not in sc: continue
            A, H, per, final, live = sc[key]
            if (A, H) != g.score:
                if A < g.max[0] or H < g.max[1]:
                    self.log('score_reversal', game=key, src='scoreboard', prev=g.max, now=(A, H),
                             locked_affected=[s for s, L in g.locked.items()])
                else:
                    newk = keys_locked(g.sport, g.a, g.h, A, H, per)
                    if g.sport == 'mlb' and per == 1 and A + H > 0: newk['nrfi'] = 'Yes'
                    fresh = [s for s in newk if s in g.mk and s not in g.locked and not any(s in v for v in g.pending.values())]
                    if fresh:
                        g.pending[(A, H)] = fresh
                        self.log('lock_seen', game=key, score=(A, H), period=per, markets=fresh)
                    g.max = (max(g.max[0], A), max(g.max[1], H))
                g.score = (A, H)
            g.period = per
            if (g.sport == 'mlb' and per >= 2 and 'nrfi' in g.mk and 'nrfi' not in g.locked and not g.nrfi_tried
                    and not any('nrfi' in v for v in g.pending.values())):
                g.nrfi_tried = True; g.pending['nrfi0'] = ['nrfi']
                self.log('lock_check', game=key, what='nrfi No (1st inning scoreless?)')
            if g.pending: self.resolve_pending(key, g)
            if final and not g.final_done:
                g.final = True
                if g.pending: self.log('pending_at_final', game=key, pending={str(k): v for k, v in g.pending.items()})
                self.snapshot(key, g, list(g.locked), tag='final')
                g.final_done = True
                self.log('game_final', game=key, score=(A, H), locked=len(g.locked))
        self.do_snaps(now)

    def resolve_pending(self, key, g):
        # NFL safe time comes ~3-4 min after the score (kickoff after the try): poll the big ESPN summary every
        # 15 s only; MLB feed every poll (next pitch comes ~30 s after the run)
        if g.sport == 'nfl' and time.time() - g.last_pbp < 15: return
        g.last_pbp = time.time()
        pbp = self.pbp(g)
        if pbp is None: return
        for sk, sufs in list(g.pending.items()):
            if sk == 'nrfi0':
                if any(p['about']['inning'] == 1 and p['result'].get('awayScore', 0) + p['result'].get('homeScore', 0) > 0
                       for p in pbp['liveData']['plays']['allPlays']):
                    del g.pending[sk]; continue          # a run scored in the 1st: NRFI-No never locks
                info = mlb_inning1_scoreless_safe(pbp)
                win = 'No'
            else:
                info = nfl_scoring_and_safe(pbp, *sk) if g.sport == 'nfl' else mlb_scoring_and_safe(pbp, *sk)
                win = None
            if not info or not info.get('safe_t'): continue
            del g.pending[sk]
            # re-check period from play-by-play for period-limited markets (1H / F5 / NRFI)
            seen = time.time()
            for s in sufs:
                if s.startswith('1h-') and info['period'] > 2: continue
                if s.startswith('f5-') and info['period'] > 5: continue
                w = win or ('Yes' if s == 'nrfi' else 'Over')
                if s == 'nrfi' and w == 'Yes' and info['period'] != 1: continue
                tok = self.token_of(g, s, w)
                if not tok: self.log('no_token', game=key, market=s); continue
                g.locked[s] = dict(win=w, token=tok, safe_t=info['safe_t'], safe_seen=seen, score_play_t=info.get('score_play_t'),
                                   snaps=[], filled=False)
            self.log('safe', game=key, score=sk, info=info, seen_lag_s=round(seen - info['safe_t'], 1),
                     markets=[s for s in sufs if s in g.locked])

    def pbp(self, g):
        if g.sport == 'nfl':
            s = http(f'{ESPN}/summary?event={g.gid}', timeout=20)
            if s:
                seq = nfl_scores_seq(s)
                for i in range(1, len(seq)):
                    if seq[i][0] < seq[i - 1][0] or seq[i][1] < seq[i - 1][1]:
                        sig = (i, seq[i - 1], seq[i])
                        if sig != g.pbp_last:
                            g.pbp_last = sig; self.log('score_reversal', game=f'nfl:{g.gid}', src='pbp', prev=seq[i - 1], now=seq[i])
            return s
        return http(f'{MLBAPI}/v1.1/game/{g.gid}/feed/live', timeout=20)

    def snapshot(self, key, g, sufs, tag):
        toks = [g.locked[s]['token'] for s in sufs if s in g.locked]
        if not toks: return
        bk = books(toks)
        for s in sufs:
            L = g.locked.get(s)
            if not L: continue
            b = bk.get(L['token'])
            self.log('book', game=key, market=s, win=L['win'], tag=tag, since_safe_seen=round(time.time() - L['safe_seen'], 1),
                     since_safe=round(time.time() - L['safe_t'], 1), book=b)
            if b and not L['filled'] and tag != 'final' and b['asks_le_099']:
                px = fill5(b['asks_le_099'])
                if px:
                    L['filled'] = True
                    fee = 5 * g.mk[s]['rate'] * px * (1 - px)
                    self.log('pretend_fill', game=key, market=s, win=L['win'], tag=tag, px=px, shares=5,
                             edge_usd=round(5 * (1 - px) - fee, 4), since_safe=round(time.time() - L['safe_t'], 1))

    def do_snaps(self, now):
        for key, g in self.games.items():
            if not g: continue
            due = {}
            for s, L in g.locked.items():
                for off in SNAPS:
                    if off not in L['snaps'] and now >= L['safe_seen'] + off:
                        L['snaps'].append(off); due.setdefault(off, []).append(s); break
            for off, sufs in due.items():
                self.snapshot(key, g, sufs, tag=f'safe+{off}')

def summarize(path, out):
    recs = [json.loads(l) for l in open(path)]
    S = dict(games=sum(r['kind'] == 'game' for r in recs), locks=sum(len(r.get('markets', [])) for r in recs if r['kind'] == 'safe'),
             reversals=[r for r in recs if r['kind'] == 'score_reversal'], pretend_fills=[r for r in recs if r['kind'] == 'pretend_fill'])
    by = {}
    for r in recs:
        if r['kind'] == 'book' and r.get('book'):
            d = by.setdefault(r['tag'], dict(n=0, ask_le_099=0, ask_le_0985=0, sh_le_099=0.0))
            d['n'] += 1; b = r['book']
            if b['best_ask'] is not None and b['best_ask'] <= 0.99: d['ask_le_099'] += 1; d['sh_le_099'] += b['d99']
            if b['best_ask'] is not None and b['best_ask'] <= 0.985: d['ask_le_0985'] += 1
    S['books_by_tag'] = by
    S['pretend_edge_usd'] = round(sum(r['edge_usd'] for r in S['pretend_fills']), 3)
    json.dump(S, open(out, 'w'), indent=1)
    print(json.dumps({k: (v if not isinstance(v, list) else len(v)) for k, v in S.items()}, indent=1))

def live(minutes, poll):
    day = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    path = OUTDIR + f'{day}.jsonl'
    log = Log(path); w = Watcher(log, poll)
    log('start', minutes=minutes, poll=poll)
    end = time.time() + minutes * 60; last_disc = 0
    try:
        while time.time() < end:
            t = time.time()
            try:
                if t - last_disc > 600: w.discover(); last_disc = t
                w.step()
            except Exception as e:
                log('error', err=repr(e), tb=traceback.format_exc()[-600:])
            time.sleep(max(0.5, poll - (time.time() - t)))
    except KeyboardInterrupt:
        pass
    log('stop', requests=NREQ['n'])
    summarize(path, OUTDIR + f'{day}-summary.json')

# ---------------------------------------------------------------- dry runs on finished games
def replay_mlb(pk):
    f = http(f'{MLBAPI}/v1.1/game/{pk}/feed/live')
    gd = f['gameData']; a = gd['teams']['away']['abbreviation'].lower(); h = gd['teams']['home']['abbreviation'].lower()
    a, h = PM_MLB.get(a, a), PM_MLB.get(h, h)
    t0 = iso(gd['datetime']['dateTime'])
    slug, mk = find_event('mlb', a, h, t0)
    allm = http(f'{GAMMA}/events?slug={slug}') if slug else None
    print('game', pk, a, h, 'slug', slug)
    prev, locked = (0, 0), {}
    for p in f['liveData']['plays']['allPlays']:
        A, H = p['result'].get('awayScore', 0), p['result'].get('homeScore', 0)
        if (A, H) != prev:
            info = mlb_scoring_and_safe(f, A, H)
            ks = [k for k in keys_locked('mlb', a, h, A, H, p['about']['inning']) if k not in locked]
            for k in ks: locked[k] = (keys_locked('mlb', a, h, A, H, p['about']['inning'])[k], info)
            print(f" {A}-{H} inn {p['about']['inning']} play={info['score_play']} safe-lock={info['safe_t'] - info['score_play_t'] if info['safe_t'] else None:.0f}s new keys={len(ks)}")
            prev = (A, H)
    n0 = mlb_inning1_scoreless_safe(f)
    if n0 and 'nrfi' not in locked: locked['nrfi'] = ('No', n0)
    check(slug, allm, locked)

def replay_nfl(eid):
    s = http(f'{ESPN}/summary?event={eid}')
    comp = s['header']['competitions'][0]
    tm = {c['homeAway']: PM_NFL.get(c['team']['abbreviation'].lower(), c['team']['abbreviation'].lower()) for c in comp['competitors']}
    a, h = tm['away'], tm['home']; t0 = iso(comp['date'])
    slug, mk = find_event('nfl', a, h, t0)
    allm = http(f'{GAMMA}/events?slug={slug}') if slug else None
    print('game', eid, a, h, 'slug', slug)
    prev, locked = (0, 0), {}
    for d in s['drives']['previous']:
        for p in d.get('plays', []):
            if 'awayScore' not in p or any(k in (p.get('type', {}).get('text') or '').lower() for k in SKIP_NFL): continue
            A, H = p['awayScore'], p['homeScore']
            if (A, H) != prev and A >= prev[0] and H >= prev[1]:
                info = nfl_scoring_and_safe(s, A, H)
                kl = keys_locked('nfl', a, h, A, H, p.get('period', {}).get('number', 0))
                ks = [k for k in kl if k not in locked]
                for k in ks: locked[k] = (kl[k], info)
                print(f" {A}-{H} Q{info['period']} {info['score_play']} -> safe on '{info.get('safe_play')}' +{(info['safe_t'] or 0) - info['score_play_t']:.0f}s new keys={len(ks)}")
                prev = (A, H)
    check(slug, allm, locked)

def check(slug, allm, locked):
    if not allm: print('no Polymarket event'); return
    ok = bad = 0
    for m in allm[0]['markets']:
        suf = m['slug'][len(slug) + 1:]
        if suf not in locked: continue
        win = locked[suf][0]; oc = json.loads(m['outcomes']); op = json.loads(m.get('outcomePrices') or '[]')
        if op and win in oc and float(op[oc.index(win)]) > 0.99: ok += 1
        else: bad += 1; print('  MISMATCH', suf, win, op)
    print(f'locked markets on Polymarket: {ok + bad}, settled as arithmetic: {ok}, against: {bad}')

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--minutes', type=float, default=120)
    ap.add_argument('--poll', type=float, default=5)
    ap.add_argument('--replay-mlb'); ap.add_argument('--replay-nfl')
    a = ap.parse_args()
    if a.replay_mlb: replay_mlb(a.replay_mlb)
    elif a.replay_nfl: replay_nfl(a.replay_nfl)
    else: live(a.minutes, a.poll)
