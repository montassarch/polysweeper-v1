"""Same wallet, split into TAKER buys (it hit an ask) and MAKER buys (its resting bid got hit), at price >= 0.95."""
import collections, json, statistics, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lab"))
from mktinfo import lookup  # noqa: E402
from wallet_usports import group, bucket, BUCKETS, med  # noqa: E402

NAME = sys.argv[1] if len(sys.argv) > 1 else "4ddc"
trades = [json.loads(l) for l in (ROOT / f"lab/data/raw/wallets/{NAME}.jsonl").read_text().splitlines() if l.strip()]
key = lambda t: (t["transactionHash"], t["asset"], t["side"], round(float(t["size"]), 4), round(float(t["price"]), 4))
takers = {key(json.loads(l)) for l in (ROOT / f"lab/data/raw/wallets/{NAME}_takeronly.jsonl").read_text().splitlines() if l.strip()}
buys = [t for t in trades if t["side"] == "BUY" and float(t["price"]) >= 0.95]
info = lookup([t["conditionId"] for t in buys])
rows = []
for t in buys:
    m = info.get(t["conditionId"])
    if not m or not m["final"]:
        continue
    p, size, ts, idx = float(t["price"]), float(t["size"]), int(t["timestamp"]), t["outcomeIndex"]
    pay = m["final"][idx]
    settled = m["closed"] and sorted(m["final"]) in ([0.0, 1.0], [0.5, 0.5])
    rows.append({"grp": group(m["series"]), "type": m["type"], "price": p, "size": size, "ts": ts, "settled": settled, "taker": key(t) in takers,
                 "lost": settled and pay == 0.0, "win": settled and pay == 1.0,
                 "dt": (ts - m["finished_ts"]) if m["finished_ts"] else None, "title": t["title"]})
US = ("MLB", "NFL", "CFB", "NHL", "NBA", "WNBA", "NCAAB")
print("buys>=0.95 matched:", len(rows), " taker:", sum(r["taker"] for r in rows), " maker:", sum(not r["taker"] for r in rows))
for who in (True, False):
    rs = [r for r in rows if r["taker"] == who and r["settled"]]
    print(f"\n=== {'TAKER (hit an ask)' if who else 'MAKER (resting bid filled)'}: settled buys {len(rs)}, lost {sum(r['lost'] for r in rs)}, shares {sum(r['size'] for r in rs):.0f}, median size {med([r['size'] for r in rs])}, median price {med([r['price'] for r in rs])}")
    print(" by sport:")
    for g, n in collections.Counter(r["grp"] for r in rs).most_common(9):
        x = [r for r in rs if r["grp"] == g]
        print(f"   {g:16} n={n:4} lost {sum(r['lost'] for r in x)} median size {med([r['size'] for r in x])} median price {med([r['price'] for r in x])}")
    print(" by timing vs Polymarket's 'finished' stamp (all sports with a stamp):")
    for lo, hi, name in BUCKETS:
        x = [r for r in rs if r["dt"] is not None and lo <= r["dt"] < hi]
        if x:
            print(f"   {name:20} n={len(x):4} shares {sum(r['size'] for r in x):7.0f} lost {sum(r['lost'] for r in x)} median price {med([r['price'] for r in x])}")
    print(" US sports only:")
    for lo, hi, name in BUCKETS:
        x = [r for r in rs if r["grp"] in US and r["dt"] is not None and lo <= r["dt"] < hi]
        if x:
            print(f"   {name:20} n={len(x):4} shares {sum(r['size'] for r in x):7.0f} lost {sum(r['lost'] for r in x)} median price {med([r['price'] for r in x])}")
print("\nLOSSES (all):")
for r in rows:
    if r["lost"]:
        print("  ", "taker" if r["taker"] else "maker", r["grp"], r["type"], r["price"], r["size"], "dt", r["dt"], r["title"][:60])

summary = {}
for who in (True, False):
    rs = [r for r in rows if r["taker"] == who and r["settled"]]
    summary["taker" if who else "maker"] = {"settled_buys": len(rs), "lost": sum(r["lost"] for r in rs), "shares": round(sum(r["size"] for r in rs)),
                                            "median_size": med([r["size"] for r in rs]), "by_timing_vs_polymarket_stamp": {name: {"buys": len(x), "lost": sum(r["lost"] for r in x)} for lo, hi, name in BUCKETS
                                            for x in [[r for r in rs if r["dt"] is not None and lo <= r["dt"] < hi]] if x}}
(ROOT / "lab/results" / f"{time.strftime('%Y-%m-%d')}-wallet-4ddc-taker-maker.json").write_text(json.dumps(summary, indent=1))
