"""For the biggest 'lost in-band buy' clusters in the election scan: what did the price do around the losing buys? (market-level story)"""
import collections, json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
from polysweeper.collector import get_json, GAMMA, parse_ts  # noqa: E402
DATA = "https://data-api.polymarket.com"
slugs = sys.argv[1:]
for slug in slugs:
    r = get_json(f"{GAMMA}/events?slug={slug}")
    if not r:
        print(slug, "not found"); continue
    e = r[0]; end = parse_ts(e["endDate"])
    mk = {}
    for m in e["markets"]:
        try:
            px = [float(x) for x in json.loads(m["outcomePrices"])]
        except (KeyError, TypeError, ValueError):
            continue
        if sorted(px) == [0.0, 1.0]:
            mk[m["conditionId"]] = (px, m["question"])
    rows, off = [], 0
    while off <= 10000:
        page = get_json(f"{DATA}/trades?eventId={e['id']}&limit=500&offset={off}")
        if not isinstance(page, list) or not page:
            break
        rows += [t for t in page if t["timestamp"] >= end - 6 * 3600]
        if len(page) < 500 or min(t["timestamp"] for t in page) < end - 6 * 3600:
            break
        off += 500
    # biggest losing market
    lost = collections.Counter(); lostsh = collections.Counter()
    for t in rows:
        x = mk.get(t["conditionId"])
        if x and t["side"] == "BUY" and t["timestamp"] >= end and 0.96 <= float(t["price"]) < 0.995 and x[0][t["outcomeIndex"]] == 0.0:
            lost[t["conditionId"]] += 1; lostsh[t["conditionId"]] += float(t["size"])
    print(f"\n##### {slug}  (end date {e['endDate']}, closed {e.get('closedTime')})")
    for cid, n in lost.most_common(2):
        px, q = mk[cid]
        print(f"  market: {q[:90]} | final {px} | lost in-band fills {n} ({lostsh[cid]:.0f} sh)")
        # price path of the Yes token (idx 0) by 30-min bucket since end-6h; mark lost-fill buckets
        yes = [t for t in rows if t["conditionId"] == cid]
        b = collections.defaultdict(list); lb = collections.Counter()
        for t in yes:
            h = (t["timestamp"] - end) / 3600
            p = float(t["price"]) if t["outcomeIndex"] == 0 else 1 - float(t["price"])
            b[int(h * 2)].append(p)
            if t["side"] == "BUY" and t["timestamp"] >= end and 0.96 <= float(t["price"]) < 0.995 and px[t["outcomeIndex"]] == 0.0:
                lb[int(h * 2)] += 1
        line = []
        for k in sorted(b):
            xs = b[k]
            line.append(f"{k/2:+.1f}h:{min(xs):.2f}-{max(xs):.2f}" + (f"[LOST x{lb[k]}]" if lb[k] else ""))
        print("   Yes-price range per 30 min (hours vs end date):", " ".join(line[:44]))
