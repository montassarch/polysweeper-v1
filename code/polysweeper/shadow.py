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

Usage (from the code/ folder):
  python -m polysweeper.shadow --leagues cs2 lol dota2 val --minutes 60
  python -m polysweeper.shadow --leagues cs2 lol epl --forever
Stop early: create the file data/shadow/STOP  (the kill switch), or press Ctrl+C.
Nothing here can place a real order: it only READS public data.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .collector import CLOB, GAMMA, get_json, leagues, parse_ts, post_json
from .config import Limits
from .confirm import Confirmer
from .fees import taker_fee
from .killswitch import KillSwitch

OUT = Path("data/shadow")
WATCH_MIN_ASK = 0.90          # start recording full snapshots from this ask
WATCH_MAX_ASK = 0.999         # record snapshots up to here (late band 0.995-0.999 is logged, not bought)
BOOK_BATCH = 40               # order books per request
EVENT_BATCH = 40              # match states per request
REFRESH_SECONDS = 120         # how often to re-list live events
POLL_SECONDS = 15             # how often to read order books
SETTLE_SECONDS = 60           # how often to check for payouts


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
    def __init__(self, league_keys, limits: Limits):
        self.limits = limits
        self.kill = KillSwitch(str(OUT / "STOP"))
        OUT.mkdir(parents=True, exist_ok=True)
        self.snap_f = (OUT / "snapshots.jsonl").open("a")
        self.trade_f = (OUT / "trades.jsonl").open("a")
        self.event_f = (OUT / "events.jsonl").open("a")
        self.err_f = (OUT / "errors.jsonl").open("a")
        self.last_event_state = {}
        self.state_path = OUT / "state.json"
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {"pending": {}, "entered": []}
        all_l = leagues()
        self.series = {k: all_l[k]["series"] for k in league_keys if k in all_l}
        self.markets = {}          # market_id -> dict(event, market, tokens)
        self.counters = {"snapshots": 0, "entries": 0, "thin": 0, "settled": 0, "errors": 0}
        self.confirmer = Confirmer()

    # -- bookkeeping ---------------------------------------------------
    def save(self):
        self.state_path.write_text(json.dumps(self.state))

    def log(self, f, rec):
        f.write(json.dumps(rec) + "\n")
        f.flush()

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

    def error(self, where, exc):
        """A2/A1: never let one bad reply stop the run; write it down and carry on."""
        self.counters["errors"] += 1
        try:
            self.log(self.err_f, {"ts": now_iso(), "where": where, "error": f"{type(exc).__name__}: {exc}"})
        except Exception:
            pass

    def refresh_states(self):
        """A3: re-read live/ended/score for every tracked match, every round (batched)."""
        ids = sorted({info["event"].get("id") for info in self.markets.values() if info["event"].get("id")})
        fresh = {}
        for i in range(0, len(ids), EVENT_BATCH):
            chunk = ids[i:i + EVENT_BATCH]
            for e in get_json(f"{GAMMA}/events?" + "&".join(f"id={x}" for x in chunk)) or []:
                fresh[e.get("id")] = e
        for info in self.markets.values():
            e = fresh.get(info["event"].get("id"))
            if e:
                for k in ("live", "ended", "score", "period"):
                    info["event"][k] = e.get(k)

    def fetch_books(self):
        """A2: read all order books in a few batched requests instead of one by one."""
        tokens = [t for info in self.markets.values() for t in info["tokens"]]
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
        win_idx, why = self.confirmer.winner_index(info["league"], e, info["market"], info["outcomes"])
        if win_idx is not None and mid not in self.state.setdefault("confirmed_logged", []):
            self.state["confirmed_logged"].append(mid)
            self.log(self.event_f, {"ts": now_iso(), "type": "confirmed", "event_id": e.get("id"),
                                    "market_id": mid, "league": info["league"], "winner_idx": win_idx,
                                    "detail": why, "polymarket_ended": ev_state["ended"]})
        for idx, best_ask, asks in in_window:
            if win_idx == idx and ev_state["ended"] is True:
                self.maybe_enter("confirmed", mid, idx, info, best_ask, asks, ev_state, why)

    def note_event_state(self, e, league, ev_state):
        """Log when a match goes live / ends. Gives true start and end times."""
        eid = e.get("id")
        sig = (ev_state["live"], ev_state["ended"], ev_state["period"])
        if self.last_event_state.get(eid) != sig:
            self.last_event_state[eid] = sig
            self.log(self.event_f, {"ts": now_iso(), "event_id": eid, "league": league,
                                    "title": e.get("title"), "state": ev_state})

    def maybe_enter(self, rule, mid, idx, info, best_ask, asks, ev_state, confirm_detail):
        L = self.limits
        key = f"{mid}:{idx}" if rule == "price_only" else f"C:{mid}:{idx}"
        if key in self.state["entered"]:
            return
        vwap, worst, avail = walk_book(asks, L.min_shares, L.price_max)
        if vwap is None:
            self.counters["thin"] += 1
            self.state["entered"].append(key)       # count once
            self.log(self.trade_f, {"type": "skip_thin", "rule": rule, "ts": now_iso(), "key": key,
                                    "league": info["league"], "question": info["market"].get("question"),
                                    "best_ask": best_ask, "available_shares": avail, "event": ev_state})
            return
        rate = (info["market"].get("feeSchedule") or {}).get("rate") or L.fee_rate
        fee = taker_fee(L.min_shares, vwap, rate)
        rec = {"type": "entry", "rule": rule, "ts": now_iso(), "key": key, "market_id": mid, "token_idx": idx,
               "league": info["league"], "question": info["market"].get("question"), "outcome": info["outcomes"][idx],
               "best_ask": best_ask, "vwap": vwap, "worst_price": worst, "shares": L.min_shares,
               "fee": fee, "cost": L.min_shares * vwap + fee, "available_shares": avail,
               "event_ended_flag": ev_state["ended"], "confirm": confirm_detail, "event": ev_state}
        self.log(self.trade_f, rec)
        self.state["entered"].append(key)
        self.state["pending"][key] = rec
        self.counters["entries"] += 1
        label = "CONFIRMED" if rule == "confirmed" else "PRICE-ONLY"
        print(f"[{now_iso()}] SHADOW BUY ({label}) {rec['outcome']} | {(rec['question'] or '')[:50]} | vwap {vwap:.3f} | ended_flag={ev_state['ended']}")
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
            print(f"[{now_iso()}] SETTLED {key}: {res} pnl {pnl:+.2f}")
            self.save()

    # -- main loop -----------------------------------------------------
    def run(self, minutes: float | None):
        end = None if minutes is None else time.time() + minutes * 60
        last_refresh = last_settle = 0.0
        print(f"shadow mode started; leagues={list(self.series)}; stop file: {OUT/'STOP'}")
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
                self.poll()
                if t - last_settle > SETTLE_SECONDS:
                    try:
                        self.settle()
                    except Exception as exc:
                        self.error("settle", exc)
                    last_settle = t
                time.sleep(POLL_SECONDS)
        except KeyboardInterrupt:
            print("stopped by user")
        finally:
            self.save()
            print("summary:", self.counters, "| pending:", len(self.state["pending"]))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--leagues", nargs="+", required=True)
    ap.add_argument("--minutes", type=float, default=None)
    ap.add_argument("--forever", action="store_true")
    ap.add_argument("--config", default="config.json")
    a = ap.parse_args(argv)
    if not a.forever and a.minutes is None:
        ap.error("give --minutes N or --forever")
    sh = Shadow(a.leagues, Limits.from_json(a.config))
    sh.run(None if a.forever else a.minutes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
