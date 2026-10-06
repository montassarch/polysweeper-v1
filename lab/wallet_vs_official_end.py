"""The best wallet's TAKER buys at >= 0.95, timed against the OFFICIAL end (MLB Stats API / ESPN), by sport."""
import collections, json, re, statistics, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lab"))
from mktinfo import lookup  # noqa: E402

espn = json.loads((ROOT / "lab/data/raw/espn_official_end_cache.json").read_text())
mlb = json.loads((ROOT / "lab/data/raw/mlb_official_end_cache.json").read_text())
end = {}
for k, v in list(espn.items()) + list(mlb.items()):
    if v:
        end[k] = v["end"]
trades = [json.loads(l) for l in (ROOT / "lab/data/raw/wallets/4ddc.jsonl").read_text().splitlines() if l.strip()]
key = lambda t: (t["transactionHash"], t["asset"], t["side"], round(float(t["size"]), 4), round(float(t["price"]), 4))
takers = {key(json.loads(l)) for l in (ROOT / "lab/data/raw/wallets/4ddc_takeronly.jsonl").read_text().splitlines() if l.strip()}
buys = [t for t in trades if t["side"] == "BUY" and float(t["price"]) >= 0.95 and t["eventSlug"] in end]
info = lookup([t["conditionId"] for t in buys])
print("wallet buys>=0.95 in games with an official end time:", len(buys))
B = [(-1e9, -1800, "30+ min before"), (-1800, -300, "5-30 min before"), (-300, -60, "1-5 min before"), (-60, 0, "last minute before"),
     (0, 10, "0-10 s after"), (10, 30, "10-30 s after"), (30, 120, "30 s-2 min after"), (120, 1e9, "2+ min after")]
for who, label in ((True, "TAKER"), (False, "MAKER")):
    print(f"\n{label} buys by seconds from the OFFICIAL end (all sports below):")
    for sport_prefix in ("mlb", "nfl", "cfb", "nhl", "wnba", "nba", "ALL"):
        rs = [t for t in buys if (key(t) in takers) == who and (sport_prefix == "ALL" or t["eventSlug"].startswith(sport_prefix + "-"))]
        if not rs:
            continue
        cells = []
        for lo, hi, name in B:
            x = [t for t in rs if lo <= t["timestamp"] - end[t["eventSlug"]] < hi]
            if x:
                cells.append(f"{name}: {len(x)}")
        lost = sum(1 for t in rs if (info.get(t["conditionId"]) or {}).get("final") and info[t["conditionId"]]["final"][t["outcomeIndex"]] == 0.0)
        print(f"  {sport_prefix:5} n={len(rs):3} lost {lost} | " + "; ".join(cells))
tk = [t for t in buys if key(t) in takers and 0 <= t["timestamp"] - end[t["eventSlug"]] < 300]
print("\nTAKER buys 0-300 s after the official end:", len(tk), "median s", statistics.median([t["timestamp"] - end[t["eventSlug"]] for t in tk]) if tk else None,
      "median size", statistics.median([float(t["size"]) for t in tk]) if tk else None, "median price", statistics.median([float(t["price"]) for t in tk]) if tk else None)

table = {}
for who, label in ((True, "taker"), (False, "maker")):
    for sp in ("mlb", "nfl", "cfb", "nhl", "wnba", "nba", "ALL"):
        rs = [t for t in buys if (key(t) in takers) == who and (sp == "ALL" or t["eventSlug"].startswith(sp + "-"))]
        if rs:
            table.setdefault(label, {})[sp] = {name: len([t for t in rs if lo <= t["timestamp"] - end[t["eventSlug"]] < hi]) for lo, hi, name in B}
(ROOT / "lab/results" / f"{time.strftime('%Y-%m-%d')}-wallet-4ddc-vs-official-end.json").write_text(json.dumps(table, indent=1))
