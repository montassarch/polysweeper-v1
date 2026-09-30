"""SHADOW MODE: watch live matches, place NO orders, record what would have happened.

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

from .collector import CLOB, GAMMA, get_json, leagues, parse_ts
from .config import Limits
from .fees import taker_fee
from .killswitch import KillSwitch

OUT = Path("data/shadow")
WATCH_MIN_ASK = 0.90          # start recording full snapshots from this ask
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


class Shadow:
    def __init__(self, league_keys, limits: Limits):
        self.limits = limits
        self.kill = KillSwitch(str(OUT / "STOP"))
        OUT.mkdir(parents=True, exist_ok=True)
        self.snap_f = (OUT / "snapshots.jsonl").open("a")
        self.trade_f = (OUT / "trades.jsonl").open("a")
        self.state_path = OUT / "state.json"
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {"pending": {}, "entered": []}
        all_l = leagues()
        self.series = {k: all_l[k]["series"] for k in league_keys if k in all_l}
        self.markets = {}          # market_id -> dict(event, market, tokens)
        self.counters = {"snapshots": 0, "entries": 0, "thin": 0, "settled": 0}

    # -- bookkeeping ---------------------------------------------------
    def save(self):
        self.state_path.write_text(json.dumps(self.state))

    def log(self, f, rec):
        f.write(json.dumps(rec) + "\n")
        f.flush()

    # -- discovery -----------------------------------------------------
    def refresh(self):
        now = datetime.now(timezone.utc)
        since = (now - timedelta(hours=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        horizon = now + timedelta(minutes=45)
        found = {}
        for league, sid in self.series.items():
            evs = get_json(f"{GAMMA}/events?series_id={sid}&active=true&closed=false"
                           f"&start_date_min={since}&order=startTime&ascending=true&limit=60") or []
            for e in evs:
                st = parse_ts(e.get("startTime"))
                if st and datetime.fromtimestamp(st, timezone.utc) > horizon:
                    continue                       # not started (or about to)
                if e.get("ended") is None and not e.get("live"):
                    continue                       # no live-state data for this event
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

    # -- polling -------------------------------------------------------
    def poll(self):
        for mid, info in list(self.markets.items()):
            e, m = info["event"], info["market"]
            ev_state = {"live": e.get("live"), "ended": e.get("ended"), "score": e.get("score"), "period": e.get("period")}
            for idx, tok in enumerate(info["tokens"]):
                book = get_json(f"{CLOB}/book?token_id={tok}")
                if not book:
                    continue
                asks = book.get("asks", [])
                bids = book.get("bids", [])
                best_ask = min((float(a["price"]) for a in asks), default=None)
                best_bid = max((float(b["price"]) for b in bids), default=None)
                if best_ask is None or best_ask < WATCH_MIN_ASK:
                    continue
                snap = {"ts": now_iso(), "market_id": mid, "league": info["league"], "outcome": info["outcomes"][idx],
                        "best_ask": best_ask, "best_bid": best_bid,
                        "asks_top5": sorted(([float(a["price"]), float(a["size"])] for a in asks))[:5],
                        "bids_top3": sorted(([float(b["price"]), float(b["size"])] for b in bids), reverse=True)[:3],
                        "event": ev_state}
                self.log(self.snap_f, snap)
                self.counters["snapshots"] += 1
                self.maybe_enter(mid, tok, idx, info, e, best_ask, asks, ev_state)

    def maybe_enter(self, mid, tok, idx, info, e, best_ask, asks, ev_state):
        L = self.limits
        key = f"{mid}:{idx}"
        if key in self.state["entered"]:
            return
        if not (L.price_min <= best_ask <= L.price_max):
            return
        vwap, worst, avail = walk_book(asks, L.min_shares, L.price_max)
        if vwap is None:
            self.counters["thin"] += 1
            self.state["entered"].append(key)       # count once
            self.log(self.trade_f, {"type": "skip_thin", "ts": now_iso(), "key": key, "league": info["league"],
                                    "question": info["market"].get("question"), "best_ask": best_ask,
                                    "available_shares": avail, "event": ev_state})
            return
        rate = (info["market"].get("feeSchedule") or {}).get("rate") or L.fee_rate
        fee = taker_fee(L.min_shares, vwap, rate)
        rec = {"type": "entry", "ts": now_iso(), "key": key, "market_id": mid, "league": info["league"],
               "question": info["market"].get("question"), "outcome": info["outcomes"][idx],
               "best_ask": best_ask, "vwap": vwap, "worst_price": worst, "shares": L.min_shares,
               "fee": fee, "cost": L.min_shares * vwap + fee, "available_shares": avail,
               "event_ended_flag": ev_state["ended"], "event": ev_state}
        self.log(self.trade_f, rec)
        self.state["entered"].append(key)
        self.state["pending"][key] = rec
        self.counters["entries"] += 1
        print(f"[{now_iso()}] SHADOW BUY {rec['outcome']} | {rec['question'][:50]} | vwap {vwap:.3f} | ended_flag={ev_state['ended']}")
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
            idx = int(key.split(":")[1])
            f = finals[idx]
            res = "win" if f >= 0.99 else "loss" if f <= 0.01 else "split"
            payout = {"win": 1.0, "loss": 0.0, "split": 0.5}[res] * rec["shares"]
            pnl = payout - rec["cost"]
            self.log(self.trade_f, {"type": "settled", "ts": now_iso(), "key": key, "result": res, "pnl": pnl,
                                    "closed_time": m.get("closedTime")})
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
                    self.refresh()
                    last_refresh = t
                self.poll()
                if t - last_settle > SETTLE_SECONDS:
                    self.settle()
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
