"""Rule "final_bid" for shadow mode (owner 2026-10-09): a PRETEND resting buy order after the match is over.

Why: the lab found that buys made during play are how losses happen, and that a resting bid at 0.98+ placed only
after the game's last play never landed on the loser (0 of 4,263 US games, 13 months). The winner's sell side is
usually empty by then (365Scores test: 56 of 56), but sellers still unload INTO bids, so a bid can get filled.

How (nothing here places a real order; it only reads public data):
  1. Candidates: two-outcome moneylines in leagues 365Scores covers (tennis, US sports), started, near the end
     (a side's best bid 0.85+) or flagged ended.
  2. A background thread asks 365Scores (Israel, free JSON) about each candidate every few seconds. When 365Scores
     says the game has normally ended ("Just Ended", "Ended", "Final", after OT/SO), with a clear winner, it hands
     the result to the main loop. Walkovers, retirements, abandoned or unknown states are never used.
  3. Order of checks (owner 2026-10-09): 365Scores first, then AT ONCE a second fast source (LiveScore; ESPN where
     LiveScore has no such league) must say the same game is over with the same winner. Polymarket is checked LAST
     and only as a veto: its score must not show the other side ahead, and it must not have flagged the match
     ended yet (too late to rest a bid). (v2.8 waited for Polymarket's score to agree, and that only happens at
     its ended flag, so every bid came too late.) Then the winner's book: best bid 0.97+.
  4. Pretend bid: 5 shares at one tick above the best bid, capped at price_max (0.995). If that is already the
     best bid, we join the queue behind the shares already there. If someone sells at or below our price
     (an ask), it is a plain taker buy instead (fee paid).
  5. Fill: the background thread reads Polymarket's public trades for that token: taker SELLs at exactly our
     price after we placed it (beyond the queue ahead of us) fill us. Needs 5 shares (minimum order).
  6. Cancel when Polymarket flags the match ended, after 30 minutes, or when the market leaves the list.
     A filled bid becomes a normal pending entry (rule "final_bid") and is paid out by shadow's settle().
All network calls happen in the background thread with short timeouts, so a slow site never stalls shadow mode.
"""
from __future__ import annotations

import json
import queue
import re
import threading
import time
import unicodedata
import urllib.request

from .collector import UA, parse_ts
from .scorecheck import sport_of, title_teams, us_score, winner_outcome

S365 = "https://webws.365scores.com/web"
LS = "https://prod-public-api.livescore.com/v1/api/app"
LS_SPORT = {"atp": "tennis", "wta": "tennis", "itf": "tennis", "nhl": "hockey", "nba": "basketball", "wnba": "basketball"}
LS_OVER = {"FT", "AET", "AP", "Ended", "Fin"}          # never "Int." (interrupted) or "Ret." (retired)
ESPN = "https://site.api.espn.com/apis/site/v2/sports"
ESPN_PATH = {"atp": "tennis/atp", "wta": "tennis/wta", "nhl": "hockey/nhl", "mlb": "baseball/mlb",
             "nfl": "football/nfl", "cfb": "football/college-football", "nba": "basketball/nba",
             "wnba": "basketball/wnba"}
ESPN_QUERY = {"football/college-football": ["?groups=80&limit=300", "?groups=81&limit=300"]}   # FBS + FCS
SECOND_WAIT_S = 600       # after 365Scores says final, wait this long for the second source
TRADES = "https://data-api.polymarket.com/trades"
SPORT365 = {"atp": 3, "wta": 3, "itf": 3, "nhl": 4, "nba": 2, "wnba": 2, "nfl": 6, "cfb": 6, "mlb": 7}
FINAL_OK = {"just ended", "ended", "final", "after ot", "after overtime", "after so", "after penalties shootout",
            "after extra innings", "end of game"}
HOT_BID = 0.85            # candidate once a side's best bid is this high (or the match is flagged ended)
MIN_MARKET_BID = 0.97     # the winner's best bid must be at least this when we place (the market agrees)
MAX_REST_S = 1800         # cancel a resting bid after 30 minutes
POLL_365_S = 4            # per-game 365Scores read, per candidate
LIST_365_S = 60           # 365Scores "current games" list per sport
TRADES_S = 10             # public trades read per resting bid
TIMEOUT = 8               # every network call in the background thread
STOP_WORDS = {"fc", "cf", "sc", "ac", "afc", "club", "de", "the", "team", "w", "jr", "sr"}


def fetch(url, timeout=TIMEOUT):
    """One quick GET; None on any problem (the background thread just tries again later)."""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
            return json.load(r)
    except Exception:
        return None


def toks(name):
    n = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    return [w for w in re.split(r"[^a-z0-9]+", n) if w and w not in STOP_WORDS]


def same_team(a, b):
    """Loose name match: 'Boston Bruins' ~ 'Bruins', 'Jannik Sinner' ~ 'Sinner J.'."""
    ta, tb = toks(a), toks(b)
    if not ta or not tb:
        return False
    ja, jb = "".join(ta), "".join(tb)
    if ja == jb or (min(len(ja), len(jb)) >= 4 and (ja in jb or jb in ja)):
        return True
    return any(len(w) >= 4 and w in tb for w in ta)


def side_map(outcomes, home, away):
    """(outcome index of 365's home side, of its away side), or None when the names don't match one way only."""
    straight = same_team(outcomes[0], home) and same_team(outcomes[1], away)
    crossed = same_team(outcomes[0], away) and same_team(outcomes[1], home)
    if straight == crossed:
        return None
    return (0, 1) if straight else (1, 0)


def final_365(game):
    """365Scores game JSON -> (winner 'home'/'away', home score, away score, status) for a normal finish,
    else None. statusGroup 4 = over; the status text must be a known normal ending; no win description
    (walkover, retirement ...)."""
    if not game or game.get("statusGroup") != 4:
        return None
    status = (game.get("statusText") or "").strip()
    if status.lower() not in FINAL_OK or (game.get("winDescription") or "").strip():
        return None
    h = (game.get("homeCompetitor") or {}).get("score")
    a = (game.get("awayCompetitor") or {}).get("score")
    if h is None or a is None or h < 0 or a < 0 or h == a:
        return None
    w = game.get("winner")
    side = "home" if h > a else "away"
    if w in (1, 2) and (w == 1) != (side == "home"):
        return None                          # 365's own winner field disagrees with its score: don't trust it
    return side, h, a, status


def bid_price(best_bid, tick, cap):
    """Our resting price: one tick above the best bid, never above the cap. Returns (price, joins_queue)."""
    p = round(min(cap, best_bid + tick), 4)
    return p, p <= best_bid + 1e-9


def pm_veto(event, outcomes, idx, sport):
    """Polymarket, checked LAST: a reason to refuse, or None. Refuse when its score shows the OTHER side ahead
    (tennis: the other side has won; US sports: more points). A score that has not caught up yet is fine."""
    if sport == "tennis":
        w = winner_outcome(event, outcomes, sport)
        return None if w is None or w == idx else f"Polymarket score {event.get('score')} says the other side won"
    r, teams = us_score(event.get("score")), title_teams(event.get("title", ""))
    if not r or not teams or r[0] == r[1]:
        return None
    lead_name = teams[0 if r[0] > r[1] else 1].strip().lower()
    hits = [i for i, o in enumerate(outcomes) if o.strip().lower() == lead_name]
    if len(hits) == 1 and hits[0] != idx:
        return f"Polymarket score {event.get('score')} has the other side ahead"
    return None


def ls_winner(d, outcomes):
    """LiveScore scoreboard JSON -> outcome index of the winner if the game is normally over, else None."""
    if not d or str(d.get("Eps") or "") not in LS_OVER:
        return None
    try:
        h, a = float(d.get("Tr1")), float(d.get("Tr2"))
        m = side_map(outcomes, d["T1"][0]["Nm"], d["T2"][0]["Nm"])
    except (TypeError, ValueError, KeyError, IndexError):
        return None
    if not m or h == a:
        return None
    return m[0] if h > a else m[1]


def espn_winner(board, outcomes):
    """ESPN scoreboard JSON -> outcome index of the winner of the one completed game between these two sides."""
    hits = []
    for ev in (board or {}).get("events", []):
        comps = list(ev.get("competitions", [])) + [c for g in ev.get("groupings", []) for c in g.get("competitions", [])]
        for c in comps:
            cs = c.get("competitors", [])
            st = (c.get("status") or ev.get("status") or {}).get("type", {})
            if len(cs) != 2 or not st.get("completed") or st.get("state") != "post":
                continue
            names = [(x.get("team") or x.get("athlete") or {}).get("displayName", "") for x in cs]
            m = side_map(outcomes, names[0], names[1])
            won = [bool(x.get("winner")) for x in cs]
            if m and won.count(True) == 1:
                hits.append(m[0] if won[0] else m[1])
    return hits[0] if len(hits) == 1 else None


def queue_at(bids, price):
    return sum(float(b["size"]) for b in bids if abs(float(b["price"]) - price) < 1e-9)


def sold_into(trades, token, price, after, until=None):
    """Shares taker-SOLD at or below our price on this token after we placed the bid (and before cancel).
    A sell printed at a LOWER bid would have hit our higher pretend bid first, so it counts too (reviewer
    2026-10-09: counting only our exact price hid the crash case, where sellers dump far below us)."""
    n = 0.0
    for t in trades or []:
        try:
            ts = float(t.get("timestamp") or 0)
            if (str(t.get("asset")) == str(token) and t.get("side") == "SELL"
                    and float(t.get("price")) <= price + 1e-9 and ts > after and (until is None or ts <= until)):
                n += float(t.get("size") or 0)
        except (TypeError, ValueError):
            continue
    return n


class FinalBid:
    def __init__(self, shadow):
        self.sh = shadow                        # uses: markets, state, limits, live, last_best, log, error, save
        self.q = queue.Queue()
        self.candidates = {}                    # mid -> snapshot for the thread (replaced, never mutated)
        self.orders_view = {}                   # key -> snapshot of resting bids for the thread
        self.results = {}                       # mid -> 365 final, waiting for Polymarket to agree
        self._thread = None
        self._stop = threading.Event()

    # -- state (kept in shadow's state.json so a restart keeps resting bids) --
    @property
    def orders(self):
        return self.sh.state.setdefault("final_bids", {})

    @property
    def done(self):
        return self.sh.state.setdefault("final_bid_done", [])

    def start(self):
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, name="final-bid", daemon=True)
            self._thread.start()

    def stop(self):
        self._stop.set()

    # -- main thread: called every shadow loop (about every 2 s) ------------
    def step(self, now=None):
        now = time.time() if now is None else now
        self.start()
        while True:
            try:
                kind, key, data = self.q.get_nowait()
            except queue.Empty:
                break
            if kind == "final" and key not in self.results and key not in self.done:
                self.results[key] = dict(data, t=now)
            elif kind == "disagree" and key not in self.done:
                self._finish(key, "skip", f"sources disagree: 365Scores and {data['second']} name different winners", data)
            elif kind == "fills" and key in self.orders:
                self.orders[key]["sold_at_price"] = data
        for mid in list(self.results):
            try:
                self._try_place(mid, now)
            except Exception as exc:            # one bad market must not block the others or repeat forever
                self.results.pop(mid, None)
                self._mark_done(mid)
                self.sh.error(f"final_bid place {mid}", exc)
        for key in list(self.orders):
            try:
                self._check_order(key, now)
            except Exception as exc:
                self.orders.pop(key, None)
                self.sh.error(f"final_bid order {key}", exc)
        self._pick_candidates(now)              # last, so a match just bid on is no longer asked about
        self.orders_view = {k: {"token": o["token"], "cond": o["cond"], "price": o["price"], "t0": o["t0"]}
                            for k, o in self.orders.items()}

    def _pick_candidates(self, now):
        c = {}
        for mid, info in self.sh.markets.items():
            if info["league"] not in SPORT365 or len(info["outcomes"]) != 2 or mid in self.done or mid in self.results:
                continue
            e = info["event"]
            st = parse_ts(e.get("startTime"))
            if not st or st > now:
                continue
            bids = [(self.sh.live.top(t) or self.sh.last_best.get(mid, {}).get(i) or (None, None))[1]
                    for i, t in enumerate(info["tokens"])]
            if e.get("ended") is True or max((b for b in bids if b is not None), default=0) >= HOT_BID:
                c[mid] = {"sport365": SPORT365[info["league"]], "league": info["league"],
                          "outcomes": list(info["outcomes"]), "start": st}
        self.candidates = c

    def _try_place(self, mid, now):
        r = self.results[mid]
        info = self.sh.markets.get(mid)
        if info is None:
            self._finish(mid, "skip", "market left the list", r)
            return
        idx = r["winner_idx"]
        e = info["event"]
        if e.get("ended") is True:
            self._finish(mid, "skip", "Polymarket had already flagged the match ended (too late to rest a bid)", r)
            return
        veto = pm_veto(e, info["outcomes"], idx, sport_of(info["league"]))   # Polymarket last, veto only
        if veto:
            self._finish(mid, "skip", veto, r)
            return
        book = self.sh.fetch_books({mid}).get(str(info["tokens"][idx])) or {}
        bids, asks = book.get("bids", []), book.get("asks", [])
        best_bid = max((float(b["price"]) for b in bids), default=None)
        best_ask = min((float(a["price"]) for a in asks), default=None)
        if best_bid is None or best_bid < MIN_MARKET_BID:
            self._finish(mid, "skip", f"market does not agree yet (winner's best bid {best_bid})", r)
            return
        L = self.sh.limits
        tick = float(info["market"].get("orderPriceMinTickSize") or 0.01)
        price, joins = bid_price(best_bid, tick, L.price_max)
        key = f"F:{mid}:{idx}"
        base = {"rule": "final_bid", "key": key, "market_id": mid, "token_idx": idx, "event_id": e.get("id"),
                "league": info["league"], "question": info["market"].get("question"),
                "outcome": info["outcomes"][idx], "s365": r, "pm_score": e.get("score"),
                "pm_ended": e.get("ended"), "best_bid": best_bid, "best_ask": best_ask}
        offered = sum(float(a["size"]) for a in asks if float(a["price"]) <= price + 1e-9)
        if best_ask is not None and best_ask <= price and offered >= L.min_shares:
            # someone is selling at or below our price: a plain taker buy at their ask (fee paid)
            self._enter(dict(base, how="taker", price=best_ask, fee=None, t0=now), now)
            self._mark_done(mid)
            del self.results[mid]
            return
        if best_ask is not None and best_ask <= price:   # a few shares offered below us: bid just under them
            price, joins = round(best_ask - tick, 4), False
            if price < MIN_MARKET_BID:
                self._finish(mid, "skip", f"too few shares offered and no room to bid below {best_ask}", r)
                return
            joins = price <= best_bid + 1e-9
        q_ahead = queue_at(bids, price) if joins else 0.0
        o = dict(base, price=price, joins_queue=joins, queue_ahead=q_ahead, t0=now,
                 token=str(info["tokens"][idx]), cond=info["market"].get("conditionId"), sold_at_price=0.0)
        self.orders[key] = o
        self._mark_done(mid)
        del self.results[mid]
        self.sh.log(self.sh.trade_f, dict(o, type="final_bid_placed", ts=self.sh_now()))
        print(f"[{self.sh_now()}] PRETEND BID (FINAL-BID) {o['outcome']} {L.min_shares:g} @ {price:.3f} | "
              f"{(o['question'] or '')[:50]} | 365Scores {r['status']} {r['home']}-{r['away']} + {r.get('second')}, PM score {e.get('score')}"
              + (f", queue ahead {q_ahead:g}" if joins else ", top of the book"))
        self.sh.save()

    def _check_order(self, key, now):
        o = self.orders[key]
        L = self.sh.limits
        info = self.sh.markets.get(o["market_id"])
        got = max(0.0, o.get("sold_at_price", 0.0) - o["queue_ahead"])
        if got >= L.min_shares:
            del self.orders[key]
            self._enter(dict(o, how="resting bid filled", fee=0.0), now)
            return
        if info is None:
            o.setdefault("missing_since", now)
        else:
            o.pop("missing_since", None)
        gone = info is None and now - o["missing_since"] > 300
        why = ("market left the list for 5 minutes" if gone else
               None if info is None else
               "Polymarket flagged the match ended" if info["event"].get("ended") is True else
               "30 minutes without a fill" if now - o["t0"] > MAX_REST_S else None)
        if why:
            del self.orders[key]
            self.sh.log(self.sh.trade_f, {"type": "final_bid_cancel", "ts": self.sh_now(), "key": key,
                                          "rule": "final_bid", "reason": why, "filled_shares": round(got, 2),
                                          "rested_s": round(now - o["t0"], 1), "price": o["price"]})
            print(f"[{self.sh_now()}] pretend bid cancelled ({why}): {o['outcome']} @ {o['price']:.3f}, "
                  f"{got:g} of {L.min_shares:g} shares would have filled")
            self.sh.save()

    def _enter(self, o, now):
        """A filled pretend bid becomes a normal pending entry; shadow's settle() pays it out."""
        L = self.sh.limits
        from .fees import taker_fee
        price = o["price"]
        fee = o["fee"] if o["fee"] is not None else taker_fee(
            L.min_shares, price, (self.sh.markets.get(o["market_id"], {}).get("market", {}).get("feeSchedule") or {}).get("rate") or L.fee_rate)
        rec = {"type": "entry", "rule": "final_bid", "ts": self.sh_now(), "key": o["key"], "market_id": o["market_id"],
               "token_idx": o["token_idx"], "event_id": o["event_id"], "league": o["league"],
               "question": o["question"], "outcome": o["outcome"], "best_ask": o.get("best_ask"),
               "vwap": price, "worst_price": price, "shares": L.min_shares, "fee": fee,
               "cost": L.min_shares * price + fee, "how": o["how"], "rested_s": round(now - o["t0"], 1),
               "event_ended_flag": (self.sh.markets.get(o["market_id"], {}).get("event") or {}).get("ended"),
               "confirm": f"365Scores {o['s365']['status']} {o['s365']['home']}-{o['s365']['away']} + {o['s365'].get('second')}; PM score {o['pm_score']}"}
        self.sh.log(self.sh.trade_f, rec)
        self.sh.state["entered"].append(o["key"])
        self.sh.state.setdefault("matches", {})[f"final_bid:{o['event_id']}"] = o["outcome"]
        self.sh.state["pending"][o["key"]] = rec
        self.sh.counters["entries"] += 1
        print(f"\n[{self.sh_now()}] SHADOW BUY (FINAL-BID, {o['how']}) {o['outcome']} {L.min_shares:g} @ {price:.3f} "
              f"| {(o['question'] or '')[:60]} | cost ${rec['cost']:.2f}")
        self.sh.save()

    def _mark_done(self, mid):
        self.done.append(mid)
        del self.done[:-3000]                   # keep state.json small: the last 3,000 matches are enough

    def _finish(self, mid, kind, reason, r):
        self._mark_done(mid)
        self.results.pop(mid, None)
        info = self.sh.markets.get(mid) or {}
        self.sh.log(self.sh.trade_f, {"type": f"final_bid_{kind}", "ts": self.sh_now(), "rule": "final_bid",
                                      "market_id": mid, "league": info.get("league"),
                                      "question": (info.get("market") or {}).get("question"), "reason": reason, "s365": r})
        self.sh.save()

    def sh_now(self):
        from .shadow import now_iso
        return now_iso()

    # -- background thread: 365Scores and public trades only (no logging, no state) --
    def _run(self):
        games, lists, last_game, last_trades = {}, {}, {}, {}
        ls_ids, ls_lists, first, espn_cache = {}, {}, {}, {}
        while not self._stop.is_set():
            try:
                now = time.time()
                cands = self.candidates
                for cache in (games, last_game, ls_ids, first):        # forget matches that are no longer candidates
                    for k in [k for k in cache if k not in cands]:
                        del cache[k]
                for k in [k for k in last_trades if k not in self.orders_view]:
                    del last_trades[k]
                for sp in {c["sport365"] for c in cands.values()}:
                    if now - lists.get(sp, (0, None))[0] > LIST_365_S:
                        d = fetch(f"{S365}/games/current/?appTypeId=5&langId=1&timezoneName=UTC&userCountryId=1&sports={sp}")
                        lists[sp] = (now, (d or {}).get("games", []))
                for mid, c in cands.items():
                    if mid not in games:
                        hits = []
                        for g in lists.get(c["sport365"], (0, []))[1]:
                            st = parse_ts(g.get("startTime"))
                            if st and abs(st - c["start"]) > 3 * 3600:
                                continue
                            m = side_map(c["outcomes"], (g.get("homeCompetitor") or {}).get("name"),
                                         (g.get("awayCompetitor") or {}).get("name"))
                            if m:
                                hits.append((g["id"], m))
                        if len(hits) == 1:
                            games[mid] = hits[0]
                        continue
                    sp_ls = LS_SPORT.get(c["league"])
                    if sp_ls and mid not in ls_ids:     # LiveScore id, looked up once the 365 game is known
                        if now - ls_lists.get(sp_ls, (0, None))[0] > LIST_365_S:
                            d = fetch(f"{LS}/live/{sp_ls}/0?MD=1")
                            ls_lists[sp_ls] = (now, [x for st in (d or {}).get("Stages", []) for x in st.get("Events", [])])
                        hits = [x.get("Eid") for x in ls_lists[sp_ls][1]
                                if x.get("Eid") and x.get("T1") and x.get("T2")
                                and side_map(c["outcomes"], x["T1"][0].get("Nm"), x["T2"][0].get("Nm"))]
                        if len(hits) == 1:
                            ls_ids[mid] = hits[0]
                    if now - last_game.get(mid, 0) < POLL_365_S:
                        continue
                    last_game[mid] = now
                    gid, (home_idx, away_idx) = games[mid]
                    if mid not in first:                # 1st source: 365Scores
                        d = fetch(f"{S365}/game/?appTypeId=5&langId=1&timezoneName=UTC&userCountryId=1&gameId={gid}")
                        f = final_365((d or {}).get("game"))
                        if not f:
                            continue
                        side, h, a, status = f
                        first[mid] = {"game_id": gid, "status": status, "home": h, "away": a,
                                      "winner_idx": home_idx if side == "home" else away_idx, "seen": round(now, 2)}
                    r = first[mid]
                    if now - r["seen"] > SECOND_WAIT_S:
                        continue                        # second source never confirmed (or disagreed): give up
                    w2, src = None, None                # 2nd source, asked at once: LiveScore, else ESPN
                    if mid in ls_ids:
                        w2, src = ls_winner(fetch(f"{LS}/scoreboard/{LS_SPORT[c['league']]}/{ls_ids[mid]}?locale=en"),
                                            c["outcomes"]), "LiveScore"
                    if w2 is None and c["league"] in ESPN_PATH:
                        path = ESPN_PATH[c["league"]]
                        if now - espn_cache.get(path, (0, None))[0] > 10:      # ESPN at most every 10 s per league
                            boards = [fetch(f"{ESPN}/{path}/scoreboard{q}") for q in ESPN_QUERY.get(path, [""])]
                            espn_cache[path] = (now, {"events": [ev for b in boards for ev in (b or {}).get("events", [])]})
                        w2, src = espn_winner(espn_cache[path][1], c["outcomes"]), "ESPN"
                    if w2 is None:
                        continue                        # not confirmed yet: ask again in a few seconds
                    if w2 != r["winner_idx"]:
                        self.q.put(("disagree", mid, dict(r, second=src, second_idx=w2)))
                        r["seen"] = -1e12               # never again for this match
                        continue
                    self.q.put(("final", mid, dict(r, second=src, confirmed=round(time.time(), 2))))
                for key, o in self.orders_view.items():
                    if now - last_trades.get(key, 0) < TRADES_S or not o.get("cond"):
                        continue
                    last_trades[key] = now
                    tr = fetch(f"{TRADES}?market={o['cond']}&limit=500")
                    if tr is not None:
                        self.q.put(("fills", key, sold_into(tr, o["token"], o["price"], o["t0"])))
            except Exception:
                pass                            # never let the helper thread die; the main loop logs nothing here
            self._stop.wait(2)
