"""Slow-arena base rate: in resolved election markets (Polymarket tags elections / global-elections, 2026), how many BUYS at 0.96-0.995 happened after
the event's end date, and how many of those were on a token that LOST?   (decided = the market's own end date has passed; this is the loose version.)
  python3 lab/election_scan.py [from=2026-03-01] [to=2026-10-03]
Writes lab/results/<date>-election-scan.json (counts + every losing in-band buy).
"""
import collections, json, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
from polysweeper.collector import get_json, GAMMA, parse_ts  # noqa: E402

DATA = "https://data-api.polymarket.com"
lo = parse_ts((sys.argv[1] if len(sys.argv) > 1 else "2026-03-01") + "T00:00:00Z")
hi = parse_ts((sys.argv[2] if len(sys.argv) > 2 else "2026-10-03") + "T23:59:59Z")
CACHE = ROOT / "lab/data/raw/election_scan_cache.json"
cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
events = {}
for tag in ("global-elections", "elections"):
    off = 0
    while off <= 6000:
        page = get_json(f"{GAMMA}/events?tag_slug={tag}&closed=true&limit=100&offset={off}&order=endDate&ascending=false")
        if not isinstance(page, list) or not page:
            break
        for e in page:
            if e.get("endDate") and lo <= parse_ts(e["endDate"]) <= hi and e.get("markets"):
                events[e["id"]] = e
        if len(page) < 100:
            break
        off += 100
print("closed election events with end date in range:", len(events), flush=True)


def scan(e):
    if e["id"] in cache:
        return cache[e["id"]]
    end = parse_ts(e["endDate"])
    mk = {}
    for m in e["markets"]:
        try:
            px = [float(x) for x in json.loads(m["outcomePrices"])]
        except (KeyError, TypeError, ValueError):
            continue
        if sorted(px) == [0.0, 1.0]:
            mk[m["conditionId"]] = px
    if not mk:
        cache[e["id"]] = None
        return None
    rows, off = [], 0
    while off <= 10000:
        page = get_json(f"{DATA}/trades?eventId={e['id']}&limit=500&offset={off}")
        if not isinstance(page, list) or not page:
            break
        rows += [t for t in page if t["timestamp"] >= end]
        if len(page) < 500 or min(t["timestamp"] for t in page) < end:
            break
        off += 500
    good = bad = 0
    gsh = bsh = 0.0
    losers = []
    for t in rows:
        px = mk.get(t["conditionId"])
        if not px or t["side"] != "BUY" or not (0.96 <= float(t["price"]) < 0.995):
            continue
        if px[t["outcomeIndex"]] == 1.0:
            good += 1; gsh += float(t["size"])
        else:
            bad += 1; bsh += float(t["size"])
            losers.append({"event": e["slug"][:70], "market": t["title"][:60], "outcome": t["outcome"], "price": float(t["price"]), "size": float(t["size"]), "hours_after_end": round((t["timestamp"] - end) / 3600, 1)})
    r = {"slug": e["slug"], "end": end, "good": good, "bad": bad, "good_sh": round(gsh), "bad_sh": round(bsh), "losers": losers[:10]}
    cache[e["id"]] = r
    return r


t0 = time.time()
with ThreadPoolExecutor(max_workers=4) as pool:
    res = [r for r in pool.map(scan, list(events.values())) if r]
CACHE.write_text(json.dumps(cache))
good, bad = sum(r["good"] for r in res), sum(r["bad"] for r in res)
print(f"scanned {len(res)} events in {round(time.time()-t0)} s: in-band (0.96-0.995) buys after the end date: pay-off {good} ({sum(r['good_sh'] for r in res)} sh), LOST {bad} ({sum(r['bad_sh'] for r in res)} sh)")
for r in sorted([r for r in res if r["bad"]], key=lambda r: -r["bad"])[:25]:
    print(f"  {r['slug'][:60]:60} lost {r['bad']:3} fills / {r['bad_sh']:6} sh (good {r['good']})", [(x['outcome'][:14], x['price'], x['size'], x['hours_after_end']) for x in r["losers"][:2]])
(ROOT / "lab/results" / f"{time.strftime('%Y-%m-%d')}-election-scan.json").write_text(json.dumps({"events": len(res), "good": good, "bad": bad, "losing_events": [r for r in res if r["bad"]]}, indent=1))
