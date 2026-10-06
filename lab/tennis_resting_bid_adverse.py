"""Tennis (ATP/WTA events on Polymarket, last ~7 days): taker SELL fills at 0.96-0.99 (= a resting bid at that level gets hit) in the 30 minutes before Polymarket's
finished stamp: how often is the token a loser?  Moneyline market only.   python3 lab/tennis_resting_bid_adverse.py"""
import collections, json, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
from polysweeper.collector import get_json, GAMMA, parse_ts  # noqa: E402

DATA = "https://data-api.polymarket.com"
cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).timestamp()
evs = []
for sid in (10365, 10366):
    off = 0
    while True:
        page = get_json(f"{GAMMA}/events?series_id={sid}&closed=true&limit=100&offset={off}&order=startDate&ascending=false")
        if not isinstance(page, list) or not page:
            break
        stop = False
        for e in page:
            st = parse_ts(e["startTime"]) if e.get("startTime") else None
            if st is not None and st < cutoff:
                stop = True; continue
            evs.append(e)
        if stop or len(page) < 100:
            break
        off += 100


def one(e):
    ml = [m for m in e.get("markets", []) if m.get("sportsMarketType") == "moneyline"]
    if not ml or not e.get("finishedTimestamp"):
        return []
    m = ml[0]
    try:
        px = [float(x) for x in json.loads(m["outcomePrices"])]
    except (KeyError, ValueError, TypeError):
        return []
    if sorted(px) != [0.0, 1.0]:
        return []
    fin = parse_ts(e["finishedTimestamp"])
    rows, off = [], 0
    while off <= 5000:
        page = get_json(f"{DATA}/trades?market={m['conditionId']}&limit=500&offset={off}")
        if not isinstance(page, list) or not page:
            break
        rows += page
        if len(page) < 500 or min(t["timestamp"] for t in page) < fin - 4 * 3600:
            break
        off += 500
    out = []
    for t in rows:
        dt = t["timestamp"] - fin
        if t["side"] == "SELL" and 0.96 <= float(t["price"]) <= 0.99 and -4 * 3600 <= dt < 0:
            out.append((e["slug"], dt, float(t["price"]), float(t["size"]), px[t["outcomeIndex"]] == 1.0))
    return out


with ThreadPoolExecutor(max_workers=5) as pool:
    res = [x for r in pool.map(one, evs) for x in r]
lost = [r for r in res if not r[4]]
games = {r[0] for r in res}
print("tennis matches in the sample:", len(evs), "| bid-hits (taker SELL at 0.96-0.99) in the 30 min before the stamp:", len(res), "in", len(games), "matches; on LOSERS:", len(lost),
      f"({len(lost)/max(1,len(res)):.1%}); loser matches:", len({r[0] for r in lost}))
pnl = sum(r[3] * ((1 - r[2]) if r[4] else -r[2]) for r in res)
print(f"bidder pnl on those fills: ${pnl:.0f}; shares {sum(r[3] for r in res):.0f}; median size {sorted(r[3] for r in res)[len(res)//2] if res else '-'}")
for r in lost[:12]:
    print("  loser:", r[0][-34:], round(r[1]), "s before the stamp, price", r[2], "size", r[3])

print("by time before the stamp:")
for lo, hi, name in ((-4 * 3600, -7200, "2-4 h before"), (-7200, -3600, "1-2 h before"), (-3600, -1800, "30-60 min before"), (-1800, -600, "10-30 min before"), (-600, 0, "last 10 min")):
    x = [r for r in res if lo <= r[1] < hi]
    l = [r for r in x if not r[4]]
    if x:
        print(f"  {name:18} fills {len(x):5} shares {sum(r[3] for r in x):8.0f}  on losers {len(l):3} ({len(l)/len(x):.1%})  matches {len({r[0] for r in x})} (loser matches {len({r[0] for r in l})})")

tb = {}
for lo, hi, name in ((-4 * 3600, -7200, "2-4h"), (-7200, -3600, "1-2h"), (-3600, -1800, "30-60min"), (-1800, -600, "10-30min"), (-600, 0, "last10min")):
    x = [r for r in res if lo <= r[1] < hi]
    tb[name] = {"fills": len(x), "on_losers": sum(1 for r in x if not r[4]), "matches": len({r[0] for r in x})}
(ROOT / "lab/results" / f"{time.strftime('%Y-%m-%d')}-tennis-resting-bid-adverse.json").write_text(json.dumps({"matches": len(evs), "by_time_before_stamp": tb}, indent=1))
