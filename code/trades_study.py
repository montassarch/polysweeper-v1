"""V2 research M2: public trades study.

For finished match-winner markets (last ~7 days), pull every public trade and look at
BUYS at high prices (0.90+): how often they lose, how much money trades there, how long
before payout, and which wallets do it repeatedly (sweeper-like wallets).

  python trades_study.py collect [markets_per_league]   -> data/trades_study/raw.jsonl
  python trades_study.py analyse                        -> data/trades_study/summary.json
"""
import json, sys, statistics, collections
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from pathlib import Path
from polysweeper.collector import leagues, get_json, GAMMA, parse_ts

DATA = "https://data-api.polymarket.com"
OUT = Path("data/trades_study")
LEAGUES = ["cs2", "lol", "dota2", "val", "r6siege", "mlbb", "hok", "ow", "codmw",
           "atp", "wta", "itf", "setkamemd", "setkawoua",
           "epl", "lal", "bun", "sea", "fl1", "ucl", "uel", "mlb", "nfl", "nba", "nhl"]
BANDS = [(0.90, 0.95), (0.95, 0.96), (0.96, 0.98), (0.98, 0.99), (0.99, 0.995), (0.995, 0.999), (0.999, 1.0001)]


def band(p):
    for lo, hi in BANDS:
        if lo <= p < hi:
            return f"{lo:.3f}-{min(hi, 1):.3f}"
    return None


def market_trades(cid):
    rows, off = [], 0
    while off <= 9000:
        page = get_json(f"{DATA}/trades?market={cid}&limit=1000&offset={off}&takerOnly=false")
        if not isinstance(page, list) or not page:
            break
        rows += page
        if len(page) < 1000:
            break
        off += 1000
    return rows


def collect(per_league):
    OUT.mkdir(parents=True, exist_ok=True)
    L = leagues()
    since = datetime.now(timezone.utc) - timedelta(days=8)
    done = set()
    raw = OUT / "raw.jsonl"
    if raw.exists():
        done = {json.loads(l)["market_id"] for l in raw.open()}
    f = raw.open("a")
    pool = ThreadPoolExecutor(max_workers=6)
    for lg in LEAGUES:
        if lg not in L:
            print("skip (unknown league)", lg); continue
        todo, off = [], 0
        while len(todo) < per_league and off < 2000:
            evs = get_json(f"{GAMMA}/events?series_id={L[lg]['series']}&closed=true&limit=100&offset={off}"
                           f"&order=endDate&ascending=false") or []
            if not evs:
                break
            for e in evs:
                for m in e.get("markets", []):
                    if m.get("sportsMarketType") != "moneyline" or m["id"] in done:
                        continue
                    closed = parse_ts(m.get("closedTime"))
                    if not closed or datetime.fromtimestamp(closed, timezone.utc) < since:
                        continue
                    try:
                        outs = json.loads(m["outcomes"]); px = [float(x) for x in json.loads(m["outcomePrices"])]
                    except (KeyError, ValueError):
                        continue
                    todo.append((e, m, outs, px, closed))
            off += 100
        todo = todo[:per_league]
        for (e, m, outs, px, closed), trades in zip(todo, pool.map(lambda x: market_trades(x[1]["conditionId"]), todo)):
            hi = [{"wallet": t["proxyWallet"], "name": t.get("name") or t.get("pseudonym"), "side": t["side"],
                   "outcome_idx": t.get("outcomeIndex"), "price": t["price"], "size": t["size"], "ts": t["timestamp"]}
                  for t in trades if t["price"] >= 0.90]
            rec = {"market_id": m["id"], "league": lg, "title": e.get("title"), "outcomes": outs, "final": px,
                   "closed_ts": closed, "start_ts": parse_ts(e.get("startTime")), "n_trades": len(trades),
                   "volume": float(m.get("volume") or 0), "high_trades": hi}
            f.write(json.dumps(rec) + "\n"); f.flush()
            done.add(m["id"])
        print(f"{lg}: {len(todo)} markets", flush=True)


def analyse():
    recs = [json.loads(l) for l in (OUT / "raw.jsonl").open()]
    by_band = collections.defaultdict(lambda: {"buys": 0, "lost_buys": 0, "dollars": 0.0, "lost_dollars": 0.0,
                                               "void_buys": 0, "markets": set(), "lost_markets": set(), "mins_to_close": []})
    wallets = collections.defaultdict(lambda: {"name": None, "markets": set(), "buys": 0, "dollars": 0.0, "lost": 0,
                                               "lost_dollars": 0.0, "profit": 0.0, "leagues": collections.Counter(),
                                               "prices": [], "mins_to_close": []})
    losses = []
    timing = collections.defaultdict(lambda: {"buys": 0, "lost": 0, "dollars": 0.0})   # 0.96+ buys by time before payout
    per_market_late = []
    for r in recs:
        final = r["final"]
        void = sorted(final) != [0.0, 1.0]
        late_dollars = 0.0
        for t in r["high_trades"]:
            if t["side"] != "BUY" or t["outcome_idx"] is None:
                continue
            b = band(t["price"])
            if not b:
                continue
            pay = final[t["outcome_idx"]]
            cost = t["price"] * t["size"]
            mins = (r["closed_ts"] - t["ts"]) / 60
            s = by_band[b]
            s["buys"] += 1; s["dollars"] += cost; s["markets"].add(r["market_id"]); s["mins_to_close"].append(mins)
            if t["price"] >= 0.96 and not void:
                tb = "0-15 min" if mins < 15 else "15-60 min" if mins < 60 else "1-3 h" if mins < 180 else "3 h+"
                timing[tb]["buys"] += 1; timing[tb]["dollars"] += cost
                if pay == 0:
                    timing[tb]["lost"] += 1
            if void:
                s["void_buys"] += 1
            elif pay == 0:
                s["lost_buys"] += 1; s["lost_dollars"] += cost; s["lost_markets"].add(r["market_id"])
                if t["price"] >= 0.96:
                    losses.append({"league": r["league"], "title": r["title"], "bought": r["outcomes"][t["outcome_idx"]],
                                   "price": t["price"], "size": t["size"], "wallet": t["wallet"], "name": t["name"],
                                   "mins_before_close": round(mins, 1)})
            if t["price"] >= 0.99:
                late_dollars += cost
                w = wallets[t["wallet"]]
                w["name"] = t["name"]; w["markets"].add(r["market_id"]); w["buys"] += 1; w["dollars"] += cost
                w["leagues"][r["league"]] += 1; w["prices"].append(t["price"]); w["mins_to_close"].append(mins)
                w["profit"] += t["size"] * pay - cost
                if not void and pay == 0:
                    w["lost"] += 1; w["lost_dollars"] += cost
        per_market_late.append(late_dollars)

    def med(x):
        return round(statistics.median(x), 1) if x else None

    bands = {}
    for b, s in sorted(by_band.items()):
        decided = s["buys"] - s["void_buys"]
        bands[b] = {"buys": s["buys"], "markets": len(s["markets"]), "dollars": round(s["dollars"]),
                    "lost_buys": s["lost_buys"], "lost_markets": len(s["lost_markets"]),
                    "loss_rate_buys": round(s["lost_buys"] / decided, 4) if decided else None,
                    "loss_rate_dollars": round(s["lost_dollars"] / s["dollars"], 4) if s["dollars"] else None,
                    "break_even_loss_rate": round(1 - float(b.split("-")[0]), 4),
                    "median_minutes_before_payout": med(s["mins_to_close"])}
    top = sorted(wallets.items(), key=lambda kv: len(kv[1]["markets"]), reverse=True)[:25]
    top_w = [{"wallet": k, "name": v["name"], "markets": len(v["markets"]), "buys": v["buys"],
              "dollars": round(v["dollars"]), "lost_buys": v["lost"], "lost_dollars": round(v["lost_dollars"]),
              "profit": round(v["profit"], 2), "median_price": round(statistics.median(v["prices"]), 4),
              "median_minutes_before_payout": med(v["mins_to_close"]),
              "top_leagues": dict(v["leagues"].most_common(4))} for k, v in top]
    days = (max(r["closed_ts"] for r in recs) - min(r["closed_ts"] for r in recs)) / 86400 or 1
    summary = {"markets": len(recs), "days_covered": round(days, 1),
               "by_league": dict(collections.Counter(r["league"] for r in recs)),
               "bands": bands, "top_wallets_099plus": top_w,
               "timing_096plus": {k: {"buys": v["buys"], "lost": v["lost"], "dollars": round(v["dollars"])} for k, v in timing.items()},
               "late_dollars_per_market_099plus": {"median": med(per_market_late),
                                                   "p90": round(sorted(per_market_late)[int(len(per_market_late) * .9)]) if per_market_late else None,
                                                   "total": round(sum(per_market_late))},
               "losses_096plus": sorted(losses, key=lambda x: -x["price"] * x["size"])[:40],
               "n_losses_096plus": len(losses)}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps({k: summary[k] for k in ("markets", "days_covered", "bands", "late_dollars_per_market_099plus", "n_losses_096plus")}, indent=1))


if __name__ == "__main__":
    if sys.argv[1] == "collect":
        collect(int(sys.argv[2]) if len(sys.argv) > 2 else 100)
    analyse()
