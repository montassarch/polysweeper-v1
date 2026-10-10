"""Check the shadow rule `final_bid` against the public tape (ps-researcher, 2026-10-10). Read-only.

Question: shadow placed N pretend resting bids (0.995, one tick above the best bid, 5 shares) after 365Scores + a
second source said "match over", and none filled. Is that what the real tape says too, or is the shadow's fill
detection (or the model in tennis_t1_stress.py) off?

For every `final_bid_placed` row in code/data/shadow/trades.jsonl we pull the market's public trades (Data API) and
list, for the winner's token, the taker SELLs after we placed the bid: inside the time we rested (until the
cancel row = Polymarket's ended flag) and in the 10 minutes after it. Sells at or below our price would have hit
our bid first (price priority); the queue ahead at our price is shown too.

Usage: python3 lab/final_bid_vs_tape.py [out.json]
"""
import collections
import datetime
import json
import os
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {"User-Agent": "polysweeper-research/0.1 (read-only data collection)"}
TRADES = "https://data-api.polymarket.com/trades"


def get(url, tries=4):
    d = 2.0
    for _ in range(tries):
        try:
            time.sleep(0.25)
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                return json.load(r)
        except Exception:
            time.sleep(d)
            d *= 2
    return None


def ts_of(s):
    return datetime.datetime.fromisoformat(s).timestamp()


def pull(cond, since):
    """All public trades of this market newer than `since` (unix s), newest first, paged."""
    out, off = [], 0
    while off <= 3000:
        d = get(f"{TRADES}?market={cond}&limit=500&offset={off}&takerOnly=false")
        if not d:
            break
        out += d
        if min(float(t.get("timestamp") or 0) for t in d) < since or len(d) < 500:
            break
        off += 500
    return [t for t in out if float(t.get("timestamp") or 0) >= since]


def main():
    rows = [json.loads(l) for l in open(os.path.join(ROOT, "code/data/shadow/trades.jsonl")) if l.strip()]
    fb = [r for r in rows if r.get("rule") == "final_bid"]
    placed = {r["key"]: r for r in fb if r["type"] == "final_bid_placed"}
    canc = {r["key"]: r for r in fb if r["type"] == "final_bid_cancel"}
    res = []
    for k, p in placed.items():
        c = canc.get(k)
        t0 = p["t0"]
        t_end = ts_of(c["ts"]) if c else t0 + 1800
        tr = pull(p["cond"], t0 - 600)
        mine = [t for t in tr if str(t.get("asset")) == str(p["token"])]
        sells = [t for t in mine if t.get("side") == "SELL"]
        px = p["price"]

        def tot(lst, lo, hi, maxp=None):
            return round(sum(float(t["size"]) for t in lst if lo < float(t["timestamp"]) <= hi
                             and (maxp is None or float(t["price"]) <= maxp + 1e-9)), 1)

        win_sells = [t for t in sells if t0 < float(t["timestamp"]) <= t_end]
        late_sells = [t for t in sells if t_end < float(t["timestamp"]) <= t_end + 600]
        by_price = collections.Counter()
        for t in win_sells:
            by_price[round(float(t["price"]), 3)] += float(t["size"])
        by_price_late = collections.Counter()
        for t in late_sells:
            by_price_late[round(float(t["price"]), 3)] += float(t["size"])
        res.append({
            "key": k, "league": p["league"], "q": p["question"][:70], "price": px, "best_bid": p["best_bid"],
            "queue_ahead": p["queue_ahead"], "rested_s": c["rested_s"] if c else None,
            "shadow_filled": (c or {}).get("filled_shares"),
            "sells_in_window_total": tot(sells, t0, t_end),
            "sells_in_window_le_px": tot(sells, t0, t_end, px),
            "sells_window_by_price": dict(sorted(by_price.items())),
            "sells_after_cancel_10min_le_px": tot(sells, t_end, t_end + 600, px),
            "sells_after_cancel_by_price": dict(sorted(by_price_late.items())),
            "sells_before_t0_le_px_600s": tot(sells, t0 - 600, t0, px),
            "n_trades_pulled": len(tr),
            "t0": t0, "t_end": t_end,
        })
        print(res[-1]["league"], res[-1]["q"][:45].ljust(45), "rest", res[-1]["rested_s"], "px", px,
              "| window sells", res[-1]["sells_in_window_total"], "<=px", res[-1]["sells_in_window_le_px"],
              "| after cancel <=px", res[-1]["sells_after_cancel_10min_le_px"], "| qa", p["queue_ahead"],
              "| by price", res[-1]["sells_window_by_price"])
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "lab/results/2026-10-10-finalbid-vs-tape.json")
    json.dump({"generated": datetime.datetime.utcnow().isoformat() + "Z", "bids": res}, open(out, "w"), indent=1)
    n = len(res)
    f_win = sum(1 for r in res if r["sells_in_window_le_px"] >= 5)
    f_win_q = sum(1 for r in res if r["sells_in_window_le_px"] - r["queue_ahead"] >= 5)
    f_late = sum(1 for r in res if r["sells_after_cancel_10min_le_px"] >= 5)
    print(f"\nbids {n}; tape says sold >=5 sh at/below our price inside the window: {f_win}; beyond queue: {f_win_q}; "
          f"only after the cancel (10 min): {f_late}")


if __name__ == "__main__":
    main()
