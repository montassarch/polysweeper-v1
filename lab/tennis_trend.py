"""Trend: how early does the market reach 0.99 on the tennis winner relative to Polymarket's own `finished` stamp, week by week through 2026?
(smaller number = sweepers are earlier = less left after the stamp.)  Sample ~90 matches per window from ATP/WTA events (public tape only).
  python3 lab/tennis_trend.py
"""
import collections, json, statistics, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
from polysweeper.collector import get_json, GAMMA, parse_ts  # noqa: E402

DATA = "https://data-api.polymarket.com"
WINDOWS = {"Apr 6-12": ("2026-04-06", "2026-04-12"), "Jun 1-7": ("2026-06-01", "2026-06-07"), "Jul 20-26": ("2026-07-20", "2026-07-26"),
           "Aug 17-23": ("2026-08-17", "2026-08-23"), "Sep 14-20": ("2026-09-14", "2026-09-20"), "Sep 28-Oct 4": ("2026-09-28", "2026-10-04")}
CACHE = ROOT / "lab/data/raw/tennis_trend_cache.json"
cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}


def ts(d):
    return datetime.fromisoformat(d).replace(tzinfo=timezone.utc).timestamp()


def events_in(a, b):
    out = []
    for sid in (10365, 10366):
        off = 0
        while off < 4000:
            page = get_json(f"{GAMMA}/events?series_id={sid}&closed=true&limit=100&offset={off}&order=startDate&ascending=false&start_date_max={b}T23:59:59Z&start_date_min={a}T00:00:00Z")
            if not isinstance(page, list) or not page:
                break
            out += page
            if len(page) < 100:
                break
            off += 100
    return out


def one(e):
    k = e["id"]
    if k in cache:
        return cache[k]
    r = None
    ml = [m for m in e.get("markets", []) if m.get("sportsMarketType") == "moneyline"]
    if ml and e.get("finishedTimestamp"):
        m = ml[0]
        try:
            px = [float(x) for x in json.loads(m["outcomePrices"])]
        except (KeyError, TypeError, ValueError):
            px = []
        if sorted(px) == [0.0, 1.0]:
            win, fin = px.index(1.0), parse_ts(e["finishedTimestamp"])
            rows, off = [], 0
            while off <= 4000:
                page = get_json(f"{DATA}/trades?market={m['conditionId']}&limit=500&offset={off}")
                if not isinstance(page, list) or not page:
                    break
                rows += page
                if len(page) < 500 or min(t["timestamp"] for t in page) < fin - 2 * 3600:
                    break
                off += 500
            w = [t for t in rows if t["outcomeIndex"] == win and t["timestamp"] > fin - 2 * 3600]
            f99 = min([t["timestamp"] for t in w if float(t["price"]) >= 0.99], default=None)
            f995 = min([t["timestamp"] for t in w if float(t["price"]) >= 0.995], default=None)
            after = [[t["timestamp"] - fin, float(t["price"]), float(t["size"])] for t in w if t["side"] == "BUY" and 0 <= t["timestamp"] - fin < 600 and 0.96 <= float(t["price"]) < 0.995]
            r = {"f99": None if f99 is None else f99 - fin, "f995": None if f995 is None else f995 - fin, "after": after, "n": len(rows)}
    cache[k] = r
    return r


out = {}
for wname, (a, b) in WINDOWS.items():
    evs = events_in(a, b)
    evs = [e for e in evs if e.get("finishedTimestamp")][:110]
    with ThreadPoolExecutor(max_workers=4) as pool:
        res = [r for r in pool.map(one, evs) if r and r["f99"] is not None]
    CACHE.write_text(json.dumps(cache))
    if not res:
        print(wname, "no data"); continue
    f99 = sorted(r["f99"] for r in res)
    f995 = sorted(r["f995"] for r in res if r["f995"] is not None)
    aft = sum(len([x for x in r["after"] if x[2] >= 5]) for r in res)
    withaft = sum(1 for r in res if any(x[2] >= 5 for x in r["after"]))
    row = {"matches": len(res), "median_first99_vs_stamp_s": statistics.median(f99), "share_99_after_stamp": round(sum(1 for x in f99 if x >= 0) / len(f99), 2),
           "median_first995_vs_stamp_s": statistics.median(f995) if f995 else None, "inband_fills_after_stamp_per_match": round(aft / len(res), 2), "matches_with_inband_after_stamp": round(withaft / len(res), 2)}
    out[wname] = row
    print(f"{wname:14} n={len(res):3}  first>=0.99 vs stamp: median {row['median_first99_vs_stamp_s']:7.0f}s, after the stamp in {row['share_99_after_stamp']:.0%} | first>=0.995 median {row['median_first995_vs_stamp_s']}s | in-band fills after stamp/match {row['inband_fills_after_stamp_per_match']} (matches with one: {row['matches_with_inband_after_stamp']:.0%})")
(ROOT / "lab/results" / f"{time.strftime('%Y-%m-%d')}-tennis-trend.json").write_text(json.dumps(out, indent=1))
