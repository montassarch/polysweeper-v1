"""SHADOW MODE: watch live matches, place NO orders, record what would have happened.

Two pretend strategies are recorded side by side:
  price_only - buy when the real ask is 0.96-0.995 and 5 shares are for sale.
  confirmed  - same, but ONLY when an outside source (ESPN for football, OpenDota
               for Dota 2) confirms a normal finish with this token as winner AND
               Polymarket has flagged the match as ended.

For every token whose real best ask enters the sweep window, it "pretends" to buy
the minimum order (5 shares) by walking the REAL order book, records the average
fill price, fees, and whether Polymarket had already flagged the match as ended.
When the market closes, it records win/loss and the fake profit.

Live feed (v2.6): Polymarket's websocket keeps order books up to date in real time. Matches near
the end (a side bid 0.85+) get their score re-read every 2 seconds; the moment one is decided or
ended, its book is read and the rules run at once. Every score change of every watched match,
with the prices at that moment, goes to data/shadow/daily/<date>.jsonl.

Usage (from the code/ folder):
  python -m polysweeper.shadow --leagues cs2 lol dota2 val --minutes 60
  python -m polysweeper.shadow --leagues cs2 lol epl --forever
  add --no-live to run without the live feed (15-second polling only)
Stop early: create the file data/shadow/STOP  (the kill switch), or press Ctrl+C.
Nothing here can place a real order: it only READS public data.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .collector import CLOB, GAMMA, get_json, leagues, parse_ts, post_json
from .config import Limits
from .confirm import Confirmer
from .fees import taker_fee
from .killswitch import KillSwitch
from .livefeed import LiveFeed
from .scorecheck import allows as score_allows, sport_of, winner_outcome
from .endwindow import EndWatch

OUT = Path("data/shadow")
WATCH_MIN_ASK = 0.90          # start recording full snapshots from this ask
WATCH_MAX_ASK = 0.999         # record snapshots up to here (late band 0.995-0.999 is logged, not bought)
BOOK_BATCH = 40               # order books per request
EVENT_BATCH = 40              # match states per request
REFRESH_SECONDS = 120         # how often to re-list live events
POLL_SECONDS = 15             # how often to read order books
SETTLE_SECONDS = 60           # how often to check for payouts
FAST_SECONDS = 2              # matches near the end: re-read their state this often
HOT_BID = 0.85                # "near the end": a side's best bid is at least this
STATUS_FIRST, STATUS_EVERY = 300, 3600   # live feed status line: after 5 minutes, then hourly
LIVE_FILE = "live.json"       # snapshot for the desktop app, rewritten every loop (not synced to GitHub)


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def walk_book(asks, shares_needed: float, max_price: float):
    """Buy `shares_needed` from the lowest asks up to max_price.
    Returns (vwap, worst_price, available_shares). vwap/worst None if not enough size."""
    levels = sorted(((float(a["price"]), float(a["size"])) for a in asks), key=lambda x: x[0])
    got = cost = 0.0
    worst = None
    avail = 0.0
    for price, size in levels:
        if price > max_price:
            break
        avail += size
        take = min(size, shares_needed - got)
        if take > 0:
            got += take
            cost += take * price
            worst = price
    if got + 1e-9 < shares_needed:
        return None, None, avail
    return cost / got, worst, avail


def fill_levels(asks, shares_needed: float, max_price: float):
    """Which sell orders a buy of `shares_needed` would take, cheapest first: [[price, shares], ...]."""
    out, got = [], 0.0
    for price, size in sorted((float(a["price"]), float(a["size"])) for a in asks):
        if price > max_price or got >= shares_needed - 1e-9:
            break
        take = min(size, shares_needed - got)
        out.append([price, round(take, 4)])
        got += take
    return out


def book_problem(idx, stats):
    """A5: a high ask only means something if the market around it is real.
    Returns a reason to refuse, or None.
      - nobody bids at least 0.50 for this token -> no real buyers, price is stale
      - another outcome is ALSO offered at 0.10 or more -> both sides 'expensive', junk book"""
    best_ask, best_bid, _, _ = stats[idx]
    if best_bid is None or best_bid < 0.50:
        return "no real bids on this side (best bid below 0.50)"
    for j, (other_ask, _, _, _) in stats.items():
        if j != idx and other_ask is not None and other_ask >= 0.10:
            return f"other side also offered at {other_ask:.3f} (inconsistent book)"
    return None


class Shadow:
    def __init__(self, league_keys, limits: Limits, live: bool = False):
        self.limits = limits
        self.kill = KillSwitch(str(OUT / "STOP"))
        OUT.mkdir(parents=True, exist_ok=True)
        self.snap_f = (OUT / "snapshots.jsonl").open("a")
        self.trade_f = (OUT / "trades.jsonl").open("a")
        self.event_f = (OUT / "events.jsonl").open("a")
        self.err_f = (OUT / "errors.jsonl").open("a")
        self.last_event_state = {}
        self.live_on = live
        self.live = LiveFeed(on_error=self.feed_error)
        self.feed_errors = {"hour": None, "n": 0}
        self.endwatch = EndWatch(lambda rec: self.log(self.event_f, dict(rec, ts=now_iso())),
                                 live=self.live, detail=self.daily)
        self.last_best = {}        # market_id -> {idx: (best ask, best bid)} from the last book read
        self.score_sig = {}        # event_id -> last (score, period, live, ended) written to the daily file
        self.titled = set()        # (date, event_id) whose title is already in that day's file (this run)
        self.feed_check = {"checks": 0, "agree": 0}
        self.started_at = now_iso()
        self.followups = []        # fill checks waiting: second look after ~2 s, public trades after ~10 s
        self.state_path = OUT / "state.json"
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {"pending": {}, "entered": []}
        all_l = leagues()
        self.series = {k: all_l[k]["series"] for k in league_keys if k in all_l}
        self.markets = {}          # market_id -> dict(event, market, tokens)
        self.counters = {"snapshots": 0, "entries": 0, "thin": 0, "settled": 0, "errors": 0,
                         "fast_reads": 0, "fast_rechecks": 0, "score_rows": 0}
        self.confirmer = Confirmer()

    # -- bookkeeping ---------------------------------------------------
    def save(self):
        self.state_path.write_text(json.dumps(self.state))

    def log(self, f, rec):
        f.write(json.dumps(rec) + "\n")
        f.flush()

    def close(self):
        """Close the data files (on Windows an open file cannot be deleted or replaced)."""
        for f in (self.snap_f, self.trade_f, self.event_f, self.err_f):
            try:
                f.close()
            except OSError:
                pass

    def daily(self, rec):
        """One line in data/shadow/daily/<UTC date>.jsonl (a new file each day keeps files small)."""
        d = OUT / "daily"
        d.mkdir(parents=True, exist_ok=True)
        with (d / f"{datetime.now(timezone.utc):%Y-%m-%d}.jsonl").open("a") as f:
            f.write(json.dumps(rec) + "\n")

    def feed_error(self, where, exc):
        """Live feed problems: at most 5 lines per hour in errors.jsonl (it retries on its own)."""
        hour = datetime.now(timezone.utc).strftime("%Y-%m-%d %H")
        if self.feed_errors["hour"] != hour:
            self.feed_errors.update(hour=hour, n=0)
        self.feed_errors["n"] += 1
        if self.feed_errors["n"] <= 5:
            self.error(where, exc)

    # -- discovery -----------------------------------------------------
    def open_events(self, sid):
        """All open (not closed) events of a league, page by page.
        A6: do NOT filter on start_date: that is the LISTING date, often days before the match."""
        evs, offset = [], 0
        while offset < 1000:
            page = get_json(f"{GAMMA}/events?series_id={sid}&active=true&closed=false&limit=100&offset={offset}") or []
            evs += page
            if len(page) < 100:
                break
            offset += 100
        return evs

    def refresh(self):
        now = datetime.now(timezone.utc)
        earliest = now - timedelta(hours=12)     # matches that started up to 12 h ago (long series)
        horizon = now + timedelta(minutes=45)    # and matches starting within 45 minutes
        found = {}
        for league, sid in self.series.items():
            for e in self.open_events(sid):
                st = parse_ts(e.get("startTime"))           # the real match start time
                if not st:
                    continue
                st_dt = datetime.fromtimestamp(st, timezone.utc)
                if st_dt > horizon or st_dt < earliest:
                    continue
                if e.get("ended") is None and not e.get("live") and st_dt < now - timedelta(minutes=5):
                    continue                       # started but no live-state data at all
                for m in e.get("markets", []):
                    if m.get("sportsMarketType") != "moneyline" or not m.get("acceptingOrders"):
                        continue
                    try:
                        toks = json.loads(m["clobTokenIds"])
                        outs = json.loads(m["outcomes"])
                    except (KeyError, ValueError):
                        continue
                    found[m["id"]] = {"league": league, "event": e, "market": m, "tokens": toks, "outcomes": outs}
        self.markets = found
        self.endwatch.close_missing(set(found))
        self.live.set_tokens(t for info in found.values() for t in info["tokens"])

    def error(self, where, exc):
        """A2/A1: never let one bad reply stop the run; write it down and carry on."""
        self.counters["errors"] += 1
        try:
            self.log(self.err_f, {"ts": now_iso(), "where": where, "error": f"{type(exc).__name__}: {exc}"})
        except Exception:
            pass

    def refresh_states(self, event_ids=None, tries=5):
        """A3: re-read live/ended/score for every tracked match (or only EVENT_IDS), batched.
        Writes every score change to the daily file. Returns the ids of matches whose state changed."""
        ids = sorted({info["event"].get("id") for info in self.markets.values() if info["event"].get("id")}
                     if event_ids is None else event_ids)
        fresh = {}
        for i in range(0, len(ids), EVENT_BATCH):
            chunk = ids[i:i + EVENT_BATCH]
            for e in get_json(f"{GAMMA}/events?" + "&".join(f"id={x}" for x in chunk), tries=tries) or []:
                fresh[e.get("id")] = e
        for info in self.markets.values():
            e = fresh.get(info["event"].get("id"))
            if e:
                for k in ("live", "ended", "score", "period"):
                    info["event"][k] = e.get(k)
        return self.log_scores(fresh)

    def log_scores(self, fresh):
        """Option 3 data: one daily-file line per score/state change, with every side's best ask and
        bid at that moment (live feed if it has the book, else the last book read)."""
        changed = set()
        for eid, e in fresh.items():
            sig = (e.get("score"), e.get("period"), e.get("live"), e.get("ended"))
            if self.score_sig.get(eid) == sig:
                continue
            self.score_sig[eid] = sig
            changed.add(eid)
            mkts = [(mid, info) for mid, info in self.markets.items() if info["event"].get("id") == eid]
            if not mkts:
                continue
            books = []
            for mid, info in mkts:
                for idx, tok in enumerate(info["tokens"]):
                    top = self.live.top(tok) or self.last_best.get(mid, {}).get(idx) or (None, None)
                    books.append([mid, idx, top[0], top[1]])
            rec = {"type": "score", "ts": now_iso(), "t": round(time.time(), 2), "event_id": eid,
                   "league": mkts[0][1]["league"], "score": sig[0], "period": sig[1], "live": sig[2],
                   "ended": sig[3], "books": books}
            day_key = (datetime.now(timezone.utc).date(), eid)
            if day_key not in self.titled:          # names once per match per daily file, to keep lines short
                self.titled.add(day_key)
                rec["title"] = e.get("title")
                rec["outcomes"] = {mid: info["outcomes"] for mid, info in mkts}
            self.daily(rec)
            self.counters["score_rows"] += 1
        return changed

    def fetch_books(self, mids=None):
        """A2: read all order books (or only those of MIDS) in a few batched requests."""
        tokens = [t for mid, info in self.markets.items() if mids is None or mid in mids for t in info["tokens"]]
        books = {}
        for i in range(0, len(tokens), BOOK_BATCH):
            chunk = tokens[i:i + BOOK_BATCH]
            for b in post_json(f"{CLOB}/books", [{"token_id": t} for t in chunk]) or []:
                if isinstance(b, dict) and b.get("asset_id"):
                    books[str(b["asset_id"])] = b
        return books

    def poll(self):
        try:
            self.refresh_states()
        except Exception as exc:
            self.error("refresh_states", exc)
        try:
            books = self.fetch_books()
        except Exception as exc:
            self.error("fetch_books", exc)
            return
        for mid, info in list(self.markets.items()):
            try:
                self.poll_market(mid, info, books)
            except Exception as exc:
                self.error(f"market {mid}", exc)

    def poll_market(self, mid, info, books):
        L = self.limits
        e = info["event"]
        ev_state = {"live": e.get("live"), "ended": e.get("ended"), "score": e.get("score"), "period": e.get("period")}
        self.note_event_state(e, info["league"], ev_state)
        stats = {}
        for idx, tok in enumerate(info["tokens"]):
            book = books.get(str(tok))
            if not book:
                continue
            asks = book.get("asks", [])
            bids = book.get("bids", [])
            stats[idx] = (min((float(a["price"]) for a in asks), default=None),
                          max((float(b["price"]) for b in bids), default=None), asks, bids)
            live = self.live.top(tok)
            if live is not None:                    # does the live feed agree with the book we just read?
                self.feed_check["checks"] += 1
                self.feed_check["agree"] += live == stats[idx][:2]
        self.last_best[mid] = {idx: st[:2] for idx, st in stats.items()}
        try:
            self.endwatch.observe(mid, info, ev_state, stats, time.time())
        except Exception as exc:
            self.error(f"endwatch {mid}", exc)
        in_window = []
        watched = False
        for idx, (best_ask, best_bid, asks, bids) in stats.items():
            if best_ask is None or best_ask < WATCH_MIN_ASK or best_ask > WATCH_MAX_ASK:
                continue
            self.log(self.snap_f, {"ts": now_iso(), "market_id": mid, "league": info["league"],
                                   "outcome": info["outcomes"][idx], "token_idx": idx,
                                   "best_ask": best_ask, "best_bid": best_bid,
                                   "asks_top5": sorted(([float(a["price"]), float(a["size"])] for a in asks))[:5],
                                   "bids_top3": sorted(([float(b["price"]), float(b["size"])] for b in bids), reverse=True)[:3],
                                   "event": ev_state})
            self.counters["snapshots"] += 1
            if best_ask >= L.price_min:
                watched = True                     # A4: in buy band OR late band -> check the result
            if L.price_min <= best_ask <= L.price_max:
                problem = book_problem(idx, stats)
                if problem:
                    key = f"bad:{mid}:{idx}"
                    if key not in self.state["entered"]:
                        print(f"[{now_iso()}] skip (junk book) {info['outcomes'][idx]} @ {best_ask:.3f} | {(info['market'].get('question') or '')[:50]} | {problem}")
                        self.state["entered"].append(key)
                        self.log(self.trade_f, {"type": "skip_bad_book", "ts": now_iso(), "key": key,
                                                "league": info["league"], "question": info["market"].get("question"),
                                                "outcome": info["outcomes"][idx], "best_ask": best_ask,
                                                "reason": problem, "event": ev_state})
                    continue
                in_window.append((idx, best_ask, asks))
        if not watched:
            return
        # Rule 1: price only (buy when the real ask is in range and 5 shares are for sale)
        for idx, best_ask, asks in in_window:
            self.maybe_enter("price_only", mid, idx, info, best_ask, asks, ev_state, None)
        # Rule 2: confirmed result (external source says this token won, normal finish,
        #         AND Polymarket has flagged the match as ended).
        # The result is also checked when a token is only in the late band (0.995-0.999),
        # so we can later study that band on the same matches. Buying rules are unchanged.
        # Rule 3: score check (check 2). Polymarket's own score says this side has WON
        #         the match, the match is flagged ended, and the book passed the junk filter.
        sport = sport_of(info["league"])
        for idx, best_ask, asks in in_window:
            verdict = score_allows(e, info["outcomes"], idx, sport) if sport else "n/a"
            if verdict == "agree" and ev_state["ended"] is True:
                self.maybe_enter("score", mid, idx, info, best_ask, asks, ev_state, f"score {e.get('score')}")
            elif verdict == "against" and f"against:{mid}:{idx}" not in self.state["entered"]:
                self.state["entered"].append(f"against:{mid}:{idx}")     # a buy check 2 blocks
                print(f"[{now_iso()}] BLOCKED by score check: {info['outcomes'][idx]} @ {best_ask:.3f} | score {e.get('score')} says the other side won")
                self.log(self.trade_f, {"type": "skip_score_against", "ts": now_iso(), "key": f"against:{mid}:{idx}",
                                        "league": info["league"], "question": info["market"].get("question"),
                                        "outcome": info["outcomes"][idx], "best_ask": best_ask, "event": ev_state})
        win_idx, why = self.confirmer.winner_index(info["league"], e, info["market"], info["outcomes"])
        if win_idx is not None and mid not in self.state.setdefault("confirmed_logged", []):
            self.state["confirmed_logged"].append(mid)
            self.log(self.event_f, {"ts": now_iso(), "type": "confirmed", "event_id": e.get("id"),
                                    "market_id": mid, "league": info["league"], "winner_idx": win_idx,
                                    "detail": why, "polymarket_ended": ev_state["ended"]})
        for idx, best_ask, asks in in_window:
            if win_idx == idx and ev_state["ended"] is True:
                self.maybe_enter("confirmed", mid, idx, info, best_ask, asks, ev_state, why)

    def fast_tick(self):
        """Matches near the end (a side's best bid 0.85+, not ended): re-read their state now. If one was
        just decided or ended, read its book and run the rules at once, not up to 15 seconds later."""
        hot = {}
        for mid, info in self.markets.items():
            e = info["event"]
            st = parse_ts(e.get("startTime"))
            if e.get("ended") is True or not e.get("id") or (st and st > time.time()):
                continue                            # over, or not started yet
            bids = [(self.live.top(t) or self.last_best.get(mid, {}).get(i) or (None, None))[1]
                    for i, t in enumerate(info["tokens"])]
            if max((b for b in bids if b is not None), default=0) >= HOT_BID:
                hot[mid] = info
        if not hot:
            return
        self.counters["fast_reads"] += 1
        changed = self.refresh_states({info["event"]["id"] for info in hot.values()}, tries=1)
        for mid, info in hot.items():
            e = info["event"]
            if e["id"] not in changed:
                continue
            sport = sport_of(info["league"])
            if e.get("ended") is not True and (winner_outcome(e, info["outcomes"], sport) if sport else None) is None:
                continue
            self.counters["fast_rechecks"] += 1
            self.poll_market(mid, info, self.fetch_books({mid}))

    def check_fills(self, now=None):
        """Would a real order have filled? For every pretend buy: a second look at the book ~2 s later
        (are the shares still there at our price?) and, ~10 s later, the public trades (did someone
        else buy them first?). One "fill_check" line per buy in trades.jsonl."""
        now = time.time() if now is None else now
        for f in list(self.followups):
            try:
                if "second" not in f and now >= f["t0"] + 2:
                    book = (post_json(f"{CLOB}/books", [{"token_id": f["token"]}], tries=1) or [{}])[0]
                    f["second"] = round(sum(float(a["size"]) for a in book.get("asks", [])
                                            if float(a["price"]) <= f["worst"] + 1e-9), 2)
                if "others" not in f and now >= f["t0"] + 10:
                    trades = get_json(f"https://data-api.polymarket.com/trades?market={f['cond']}&limit=100",
                                      tries=1) if f.get("cond") else None
                    took = [t for t in trades or [] if str(t.get("asset")) == f["token"] and t.get("side") == "BUY"
                            and float(t.get("price") or 1) <= f["worst"] + 1e-9
                            and f["t0"] - 3 <= float(t.get("timestamp") or 0) <= f["t0"] + 10]
                    f["others"] = (round(sum(float(t.get("size") or 0) for t in took), 2), len(took),
                                   trades is not None)
            except Exception as exc:
                f.setdefault("problems", 0)
                f["problems"] += 1
                if f["problems"] >= 3:
                    self.followups.remove(f)
                    self.error("fill check", exc)
                continue
            if "second" in f and "others" in f:
                still = f["second"] >= f["shares"]
                shares, n, known = f["others"]
                verdict = "likely filled" if still else "taken by others" if n else "gone"
                self.log(self.trade_f, {"type": "fill_check", "ts": now_iso(), "key": f["key"], "rule": f["rule"],
                                        "second_look_shares": f["second"], "still_there": still,
                                        "others_bought_shares": shares, "others_trades": n,
                                        "trades_checked": known, "verdict": verdict})
                self.followups.remove(f)

    def write_live(self):
        """data/shadow/live.json: what shadow mode sees right now, for the desktop app (PolySweeper.exe).
        Rewritten every loop (about every 2 seconds). Never allowed to disturb shadow mode."""
        try:
            now = time.time()
            rows = []
            for mid, info in self.markets.items():
                e = info["event"]
                prices = []
                for i, tok in enumerate(info["tokens"]):
                    top = self.live.top(tok)
                    src = "live" if top is not None else "book"
                    top = top or self.last_best.get(mid, {}).get(i) or (None, None)
                    prices.append([top[0], top[1], src])
                bids = [p[1] for p in prices if p[1] is not None]
                st = parse_ts(e.get("startTime"))
                rows.append({"mid": mid, "league": info["league"], "title": e.get("title") or info["market"].get("question"),
                             "question": info["market"].get("question"), "outcomes": info["outcomes"], "prices": prices,
                             "score": e.get("score"), "period": e.get("period"), "live": e.get("live"),
                             "ended": e.get("ended"), "start": st,
                             "hot": bool(e.get("ended") is not True and not (st and st > now)
                                         and bids and max(bids) >= HOT_BID),
                             "window": mid in self.endwatch.open})
            rows.sort(key=lambda r: (not r["hot"], not r["live"], r["start"] or 0))
            pending = [{k: r.get(k) for k in ("key", "rule", "ts", "market_id", "token_idx", "league", "question",
                                              "outcome", "vwap", "cost", "shares")}
                       for r in self.state["pending"].values()]
            c = self.feed_check
            snap = {"ts": now_iso(), "t": round(now, 2), "version": "2.7", "started": self.started_at,
                    "live_on": self.live_on, "live_feed": self.live.status(),
                    "agree_pct": round(100 * c["agree"] / c["checks"], 1) if c["checks"] else None,
                    "counters": self.counters, "markets": rows, "pending": pending}
            tmp = OUT / (LIVE_FILE + ".tmp")
            tmp.write_text(json.dumps(snap))
            os.replace(tmp, OUT / LIVE_FILE)
        except Exception:                           # e.g. the app is reading the file at this moment (Windows)
            self.counters["live_file_skips"] = self.counters.get("live_file_skips", 0) + 1

    def live_status(self):
        """One line in events.jsonl: is the live feed working on this PC?"""
        c = self.feed_check
        self.log(self.event_f, {"type": "live_feed_status", "ts": now_iso(), "enabled": self.live_on,
                                **self.live.status(), "book_checks": c["checks"],
                                "book_checks_agree_pct": round(100 * c["agree"] / c["checks"], 1) if c["checks"] else None,
                                "fast_reads": self.counters["fast_reads"], "fast_rechecks": self.counters["fast_rechecks"],
                                "score_rows": self.counters["score_rows"]})

    def note_event_state(self, e, league, ev_state):
        """Log when a match goes live / ends. Gives true start and end times."""
        eid = e.get("id")
        sig = (ev_state["live"], ev_state["ended"], ev_state["period"])
        if self.last_event_state.get(eid) != sig:
            self.last_event_state[eid] = sig
            self.log(self.event_f, {"ts": now_iso(), "event_id": eid, "league": league,
                                    "title": e.get("title"), "state": ev_state})

    def match_bought(self, rule, mid, eid):
        """The side already bought in this match under this rule, or None.
        A match is an event: football has three moneyline markets (home, draw, away) per match.
        Buys made before this check existed carry no event id, so they are matched by market."""
        side = self.state.get("matches", {}).get(f"{rule}:{eid}")
        if side:
            return side
        return next((r.get("outcome") or "a side" for r in self.state["pending"].values()
                     if r.get("rule", "price_only") == rule and r.get("market_id") == mid), None)

    def maybe_enter(self, rule, mid, idx, info, best_ask, asks, ev_state, confirm_detail):
        L = self.limits
        key = {"price_only": f"{mid}:{idx}", "confirmed": f"C:{mid}:{idx}", "score": f"S:{mid}:{idx}"}[rule]
        if key in self.state["entered"]:
            return
        eid = info["event"].get("id") or f"market {mid}"
        first = self.match_bought(rule, mid, eid)
        if first:                                   # B7: max 1 pretend buy per match (per rule)
            self.state["entered"].append(key)       # count once
            print(f"[{now_iso()}] skip (one buy per match) {info['outcomes'][idx]} @ {best_ask:.3f} | {(info['market'].get('question') or '')[:50]} | already bought {first}")
            self.log(self.trade_f, {"type": "skip_second_buy", "rule": rule, "ts": now_iso(), "key": key,
                                    "league": info["league"], "question": info["market"].get("question"),
                                    "outcome": info["outcomes"][idx], "best_ask": best_ask,
                                    "reason": f"already bought {first} in this match", "event": ev_state})
            self.save()
            return
        vwap, worst, avail = walk_book(asks, L.min_shares, L.price_max)
        if vwap is None:
            self.counters["thin"] += 1
            self.state["entered"].append(key)       # count once
            print(f"[{now_iso()}] skip (too few shares) {info['outcomes'][idx]} @ {best_ask:.3f}: only {avail:g} for sale up to {L.price_max}")
            self.log(self.trade_f, {"type": "skip_thin", "rule": rule, "ts": now_iso(), "key": key,
                                    "league": info["league"], "question": info["market"].get("question"),
                                    "best_ask": best_ask, "available_shares": avail, "event": ev_state})
            return
        rate = (info["market"].get("feeSchedule") or {}).get("rate") or L.fee_rate
        fee = taker_fee(L.min_shares, vwap, rate)
        rec = {"type": "entry", "rule": rule, "ts": now_iso(), "key": key, "market_id": mid, "token_idx": idx,
               "event_id": eid, "league": info["league"], "question": info["market"].get("question"), "outcome": info["outcomes"][idx],
               "best_ask": best_ask, "vwap": vwap, "worst_price": worst, "shares": L.min_shares,
               "fee": fee, "cost": L.min_shares * vwap + fee, "available_shares": avail,
               "event_ended_flag": ev_state["ended"], "confirm": confirm_detail, "event": ev_state,
               # check 2 verdict on EVERY entry, so we can see which losses it would have blocked
               "score_check": score_allows(info["event"], info["outcomes"], idx, sport_of(info["league"])) if sport_of(info["league"]) else "n/a"}
        rec["fills"] = fill_levels(asks, L.min_shares, L.price_max)
        rec["asks_top5"] = sorted([float(a["price"]), float(a["size"])] for a in asks)[:5]
        self.log(self.trade_f, rec)
        self.followups.append({"key": key, "rule": rule, "token": str(info["tokens"][idx]), "t0": time.time(),
                               "cond": info["market"].get("conditionId"), "worst": worst, "shares": L.min_shares})
        self.state["entered"].append(key)
        self.state.setdefault("matches", {})[f"{rule}:{eid}"] = rec["outcome"] or "a side"
        self.state["pending"][key] = rec
        self.counters["entries"] += 1
        label = {"confirmed": "CONFIRMED", "score": "SCORE-CHECK", "price_only": "PRICE-ONLY"}[rule]
        print(f"\n[{now_iso()}] SHADOW BUY ({label}) {rec['outcome']} | {(rec['question'] or '')[:60]}")
        print(f"    why:   match {'ENDED' if ev_state['ended'] else 'still in play'}, score {ev_state.get('score')}"
              + (f", result source: {confirm_detail}" if rule == "confirmed" else "") + f", score check: {rec['score_check']}")
        print("    book:  sellers " + ", ".join(f"{sz:g} @ {px:.3f}" for px, sz in rec["asks_top5"]))
        print("    fill:  " + " + ".join(f"{sh:g} @ {px:.3f}" for px, sh in rec["fills"])
              + f"  -> {L.min_shares:g} shares, avg {vwap:.4f}, fee ${fee:.4f}, cost ${rec['cost']:.2f}")
        print(f"    if it wins: +${L.min_shares - rec['cost']:.2f}   if it loses: -${rec['cost']:.2f}")
        self.save()

    def settle(self):
        for key, rec in list(self.state["pending"].items()):
            m = get_json(f"{GAMMA}/markets/{rec['market_id']}")
            if not m or not m.get("closed"):
                continue
            try:
                finals = [float(x) for x in json.loads(m["outcomePrices"])]
            except (KeyError, ValueError):
                continue
            idx = rec.get("token_idx", int(key.split(":")[-1]))
            f = finals[idx]
            res = "win" if f >= 0.99 else "loss" if f <= 0.01 else "split"
            payout = {"win": 1.0, "loss": 0.0, "split": 0.5}[res] * rec["shares"]
            pnl = payout - rec["cost"]
            self.log(self.trade_f, {"type": "settled", "ts": now_iso(), "key": key, "rule": rec.get("rule", "price_only"),
                                    "result": res, "pnl": pnl, "closed_time": m.get("closedTime")})
            del self.state["pending"][key]
            self.counters["settled"] += 1
            print(f"[{now_iso()}] PAID OUT: {rec.get('outcome')} | {(rec.get('question') or '')[:50]} | {res.upper()} {pnl:+.2f} ({rec.get('rule', 'price_only')})")
            self.save()

    # -- main loop -----------------------------------------------------
    def run(self, minutes: float | None):
        end = None if minutes is None else time.time() + minutes * 60
        last_refresh = last_settle = last_poll = 0.0
        next_status = time.time() + STATUS_FIRST
        print(f"shadow mode started; leagues={list(self.series)}; live feed: {'on' if self.live_on else 'off'}; stop file: {OUT/'STOP'}")
        if self.live_on:
            self.live.start()
        try:
            while end is None or time.time() < end:
                if self.kill.is_active():
                    print("kill switch (STOP file) found; stopping")
                    break
                t = time.time()
                if t - last_refresh > REFRESH_SECONDS:
                    try:
                        self.refresh()
                    except Exception as exc:
                        self.error("refresh", exc)
                    last_refresh = t
                if t - last_poll >= POLL_SECONDS:
                    self.poll()
                    last_poll = t
                else:
                    try:
                        self.fast_tick()
                    except Exception as exc:
                        self.error("fast_tick", exc)
                if t - last_settle > SETTLE_SECONDS:
                    try:
                        self.settle()
                    except Exception as exc:
                        self.error("settle", exc)
                    last_settle = t
                if t >= next_status:
                    self.live_status()
                    next_status = t + STATUS_EVERY
                try:
                    self.check_fills()
                except Exception as exc:
                    self.error("check_fills", exc)
                self.write_live()
                time.sleep(FAST_SECONDS)
        except KeyboardInterrupt:
            print("stopped by user")
        finally:
            self.live.stop()
            self.endwatch.close_all()
            self.live_status()
            self.save()
            self.close()
            print("summary:", self.counters, "| pending:", len(self.state["pending"]))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--leagues", nargs="+", default=None,
                    help="league keys; default: the list in shadow_leagues.txt")
    ap.add_argument("--minutes", type=float, default=None)
    ap.add_argument("--forever", action="store_true")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--no-live", action="store_true", help="no live feed: 15-second polling only")
    a = ap.parse_args(argv)
    if not a.forever and a.minutes is None:
        ap.error("give --minutes N or --forever")
    if not a.leagues:
        a.leagues = Path("shadow_leagues.txt").read_text().split()
    sh = Shadow(a.leagues, Limits.from_json(a.config), live=not a.no_live)
    sh.run(None if a.forever else a.minutes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
