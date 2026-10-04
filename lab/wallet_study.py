"""Lab idea #10: learn from wallets that buy sports winners at 0.95+ (most with zero losses).

For each wallet: pull its public trades (Data API), keep BUYS at 0.95+, look up each market (Gamma)
for the result, payout time and, where Polymarket records it (tennis, US sports; not esports), the
moment the match finished. Then: when do they buy (during play / just after the end / later),
at what price, how much, and did any of it lose?

  cd code && py -3 ../lab/wallet_study.py      (or python3; needs code/ on the path for collector.py)
  -> lab/results/<date>-wallet-study.json and a printed summary
"""
import collections, json, statistics, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
from polysweeper.collector import get_json, GAMMA, parse_ts  # noqa: E402

DATA = "https://data-api.polymarket.com"
MAX_TRADES = 6000          # newest trades per wallet
SUMMARY = ROOT / "code/data/trades_study/summary.json"
# picked from the public trades study (top wallets buying at 0.99+), plus the one big loser for contrast
PICK = ["0x4dDC7068", "467j6yj", "a5533", "owlgorithm-beta", "antec", "InterzoneCo", "momo-0916",
        "FountainCleaner", "Kudri", "jiafanpomarke001"]
BUCKETS = [(-1e12, -300, "during play (5+ min before the end)"), (-300, 0, "last 5 min before the end"),
           (0, 60, "0-60 s after the end"), (60, 300, "1-5 min after"), (300, 1800, "5-30 min after"),
           (1800, 1e12, "30+ min after")]


def wallet_list():
    top = json.loads(SUMMARY.read_text())["top_wallets_099plus"]
    out = []
    for p in PICK:
        w = next((w for w in top if (w["name"] or "") == p or w["wallet"].lower().startswith(p.lower())), None)
        if w:
            out.append((p, w["wallet"]))
    return out


def trades_of(wallet):
    rows, off = [], 0
    while off < MAX_TRADES:
        page = get_json(f"{DATA}/trades?user={wallet}&limit=500&offset={off}&takerOnly=false")
        if not isinstance(page, list) or not page:
            break
        rows += [t for t in page if t.get("proxyWallet", "").lower() == wallet.lower()]
        if len(page) < 500:
            break
        off += 500
        time.sleep(0.2)
    return rows


def markets_for(cids):
    info, cids = {}, list(cids)
    chunks = [cids[i:i + 20] for i in range(0, len(cids), 20)]

    def one(chunk):
        q = "&".join("condition_ids=" + c for c in chunk)
        return get_json(f"{GAMMA}/markets?{q}&closed=true&limit=50") or []

    with ThreadPoolExecutor(max_workers=6) as pool:
        for ms in pool.map(one, chunks):
            for m in ms:
                ev = (m.get("events") or [{}])[0]
                try:
                    px = [float(x) for x in json.loads(m["outcomePrices"])]
                except (KeyError, ValueError, TypeError):
                    continue
                info[m["conditionId"]] = {
                    "final": px, "closed_ts": parse_ts(m.get("closedTime")),
                    "finished_ts": parse_ts(ev.get("finishedTimestamp")), "type": m.get("sportsMarketType"),
                    "series": ev.get("seriesSlug"), "title": m.get("question")}
    return info


def bucket(sec):
    for lo, hi, name in BUCKETS:
        if lo <= sec < hi:
            return name


def med(x):
    return round(statistics.median(x), 4) if x else None


def study(label, wallet):
    trades = [t for t in trades_of(wallet) if t.get("side") == "BUY" and float(t["price"]) >= 0.95]
    if not trades:
        return {"label": label, "wallet": wallet, "buys": 0}
    info = markets_for({t["conditionId"] for t in trades})
    s = {"label": label, "wallet": wallet, "buys": len(trades), "settled_buys": 0, "open_or_unknown": 0,
         "dollars": 0.0, "profit": 0.0, "lost_buys": 0, "lost_dollars": 0.0, "void_buys": 0,
         "first_trade": None, "last_trade": None, "market_types": collections.Counter(),
         "series": collections.Counter(), "timing": {}, "price_by_band": collections.Counter(),
         "mins_before_payout": [], "losses": []}
    timing = collections.defaultdict(lambda: {"buys": 0, "dollars": 0.0, "lost": 0, "prices": [], "shares": 0.0})
    tss = []
    for t in trades:
        p, size, ts = float(t["price"]), float(t["size"]), int(t["timestamp"])
        tss.append(ts)
        m = info.get(t["conditionId"])
        idx = t.get("outcomeIndex")
        if not m or idx is None or idx >= len(m["final"]):
            s["open_or_unknown"] += 1
            continue
        pay, cost = m["final"][idx], p * size
        void = sorted(m["final"]) != [0.0, 1.0]
        s["settled_buys"] += 1; s["dollars"] += cost; s["profit"] += size * pay - cost
        s["market_types"][m["type"]] += 1; s["series"][m["series"]] += 1
        s["price_by_band"]["0.95-0.98" if p < 0.98 else "0.98-0.99" if p < 0.99 else "0.99-0.995" if p < 0.995
                           else "0.995-0.999" if p < 0.999 else "0.999+"] += 1
        lost = (not void) and pay == 0
        if void:
            s["void_buys"] += 1
        if lost:
            s["lost_buys"] += 1; s["lost_dollars"] += cost
            s["losses"].append({"title": m["title"], "price": p, "size": size,
                                "sec_vs_end": ts - m["finished_ts"] if m["finished_ts"] else None})
        if m["closed_ts"]:
            s["mins_before_payout"].append((m["closed_ts"] - ts) / 60)
        if m["finished_ts"]:
            b = timing[bucket(ts - m["finished_ts"])]
            b["buys"] += 1; b["dollars"] += cost; b["lost"] += lost; b["prices"].append(p); b["shares"] += size
    s["first_trade"] = datetime.fromtimestamp(min(tss), timezone.utc).isoformat()[:16]
    s["last_trade"] = datetime.fromtimestamp(max(tss), timezone.utc).isoformat()[:16]
    s["timing"] = {name: {"buys": timing[name]["buys"], "dollars": round(timing[name]["dollars"]),
                          "shares": round(timing[name]["shares"]), "lost": timing[name]["lost"],
                          "median_price": med(timing[name]["prices"])}
                   for _, _, name in BUCKETS if name in timing}
    s["median_mins_before_payout"] = med(s.pop("mins_before_payout"))
    s["market_types"] = dict(s["market_types"].most_common(5)); s["series"] = dict(s["series"].most_common(6))
    s["price_by_band"] = dict(s["price_by_band"])
    for k in ("dollars", "profit", "lost_dollars"):
        s[k] = round(s[k], 2)
    s["losses"] = s["losses"][:15]
    return s


def main():
    out = []
    for label, wallet in wallet_list():
        r = study(label, wallet)
        out.append(r)
        print(f"\n== {label} ({wallet[:10]}): {r['buys']} buys at 0.95+, settled {r.get('settled_buys')}, "
              f"${r.get('dollars')}, profit ${r.get('profit')}, lost {r.get('lost_buys')} (${r.get('lost_dollars')}), "
              f"{r.get('first_trade')} .. {r.get('last_trade')}", flush=True)
        if r["buys"]:
            print("   prices:", r["price_by_band"], "| types:", r["market_types"], "| series:", r["series"])
            for name, b in r["timing"].items():
                print(f"   {name:38} buys {b['buys']:5}  shares {b['shares']:>8}  ${b['dollars']:>8}  lost {b['lost']}  median price {b['median_price']}")
    res = ROOT / "lab/results" / f"{datetime.now(timezone.utc).date()}-wallet-study.json"
    res.write_text(json.dumps(out, indent=1))
    print("\nsaved", res.relative_to(ROOT))


if __name__ == "__main__":
    main()
