"""Backup study (market making), part 3: who already makes markets, how concentrated, what they earn.

Read-only, public Data API only. No orders, no wallets of ours.
1. Sample reward-paying markets per type (from lab/mm_scan.py's cache) and read recent trades twice:
   takerOnly=true (taker rows) and takerOnly=false (all rows). Maker rows = all rows minus taker rows.
2. Maker concentration per type: distinct maker wallets, top-1 / top-3 / top-10 share of maker dollars.
3. For the biggest maker wallets plus a random set of small ones: Data API v2 /user-stats (all time) and
   /user-pnl (30 days, hourly points) -> liquidity reward income, maker rebates, trading P&L per day, and
   /value (open positions value) as a capital stand-in.

Usage: py -3 lab/mm_makers.py   -> lab/results/2026-10-08-mm-makers.json
"""
import json, os, random, sys, time, urllib.request, collections, statistics, datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, "data", "raw", "mm")
UA = {"User-Agent": "polysweeper-research/0.1 (read-only data collection)"}
DATA = "https://data-api.polymarket.com"


def get(url, tries=4):
    err = None
    for i in range(tries):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60))
        except Exception as e:  # noqa
            err = e
            time.sleep(1.5 * (i + 1))
    print("FAILED", url[:110], err, file=sys.stderr)
    return None


def trades(cid, taker_only, pages=3):
    out = []
    for k in range(pages):
        d = get(f"{DATA}/trades?market={cid}&limit=500&offset={500 * k}&takerOnly={'true' if taker_only else 'false'}")
        if not d:
            break
        out += d
        if len(d) < 500:
            break
        time.sleep(0.1)
    return out


def main():
    ev = json.load(open(os.path.join(RAW, "gamma-open-markets.json"), encoding="utf-8"))
    rw = {r["condition_id"]: r for r in json.load(open(os.path.join(RAW, "rewards-current.json"), encoding="utf-8"))}
    sys.path.insert(0, ROOT)
    from mm_scan import mtype
    by = collections.defaultdict(list)
    for m in ev:
        r = rw.get(m["cid"])
        if not r or (r.get("total_daily_rate") or 0) <= 0 or m["vol24"] < 300:
            continue
        m["rate"] = r.get("total_daily_rate")
        by[mtype(m)].append(m)
    random.seed(11)
    sample = []
    for t, ms in by.items():
        ms.sort(key=lambda m: -m["rate"])
        pick = ms[:8] + random.sample(ms[8:], min(10, max(0, len(ms) - 8)))
        sample += [(t, m) for m in pick]
    print("markets sampled", len(sample), collections.Counter(t for t, _ in sample))
    maker_usd = collections.Counter()
    maker_mk = collections.defaultdict(set)
    per_type = collections.defaultdict(lambda: collections.Counter())
    per_type_mk = collections.defaultdict(int)
    per_market = []
    for t, m in sample:
        allr = trades(m["cid"], False)
        tk = trades(m["cid"], True)
        tkeys = set((x["transactionHash"], x["proxyWallet"], x["side"], round(x["size"], 4)) for x in tk)
        mk = [x for x in allr if (x["transactionHash"], x["proxyWallet"], x["side"], round(x["size"], 4)) not in tkeys]
        if not mk:
            continue
        c = collections.Counter()
        for x in mk:
            c[x["proxyWallet"]] += x["size"] * x["price"]
        tot = sum(c.values())
        span_h = (max(x["timestamp"] for x in allr) - min(x["timestamp"] for x in allr)) / 3600 if allr else 0
        per_market.append({"type": t, "q": m["q"][:70], "rate": m["rate"], "makers": len(c),
                           "top1": round(c.most_common(1)[0][1] / tot, 3), "maker_usd": round(tot),
                           "span_h": round(span_h, 1)})
        for w, u in c.items():
            maker_usd[w] += u
            maker_mk[w].add(m["cid"])
            per_type[t][w] += u
        per_type_mk[t] += 1
        time.sleep(0.1)
    conc = {}
    for t, c in per_type.items():
        tot = sum(c.values())
        vals = [u for _, u in c.most_common()]
        conc[t] = {"markets": per_type_mk[t], "distinct_makers": len(c), "maker_usd": round(tot),
                   "top1_share": round(sum(vals[:1]) / tot, 3), "top3_share": round(sum(vals[:3]) / tot, 3),
                   "top10_share": round(sum(vals[:10]) / tot, 3),
                   "median_makers_per_market": statistics.median([r["makers"] for r in per_market if r["type"] == t])}
    print(json.dumps(conc, indent=1))
    top = [w for w, _ in maker_usd.most_common(60)]
    rest = [w for w in maker_usd if w not in set(top)]
    small = random.sample(rest, min(40, len(rest)))
    now = time.time()
    wallets = []
    for w in top + small:
        st = get(f"{DATA}/v2/user-stats?user={w}")
        pn = get(f"{DATA}/v2/user-pnl?user={w}&interval=1m")
        val = get(f"{DATA}/value?user={w}")
        if not st or not pn:
            continue
        a = st["data"].get("all_time_pnl") or {}
        pts = (pn.get("data") or {}).get("points") or []
        if len(pts) < 2:
            continue
        p0, p1 = pts[0], pts[-1]
        days = max((p1["timestamp"] - p0["timestamp"]) / 86400, 1)
        f = lambda k: ((p1.get(k) or 0) - (p0.get(k) or 0)) / days
        joined = st["data"].get("join_date") or now
        wallets.append({"w": w, "group": "top" if w in top else "small", "maker_usd_sample": round(maker_usd[w]),
                        "markets_in_sample": len(maker_mk[w]),
                        "value_usd": round((val or [{}])[0].get("value") or 0) if isinstance(val, list) and val else 0,
                        "age_days": round((now - joined) / 86400),
                        "rew_day_30d": round(f("reward_income"), 2), "rebate_day_30d": round(f("maker_rebate"), 2),
                        "trade_pnl_day_30d": round(f("trade_pnl"), 2), "econ_pnl_day_30d": round(f("economic_pnl"), 2),
                        "volume_day_30d": round(f("volume_usdc")), "fees_paid_day_30d": round(f("fees_paid"), 2),
                        "yield_day_30d": round(f("yield_income"), 2),
                        "rew_all": round(a.get("reward_income") or 0), "rebate_all": round(a.get("maker_rebate") or 0),
                        "trade_pnl_all": round(a.get("trade_pnl") or 0), "econ_pnl_all": round(a.get("economic_pnl") or 0)})
        time.sleep(0.15)
    for g in ("top", "small"):
        ws = [x for x in wallets if x["group"] == g]
        if not ws:
            continue
        print(g, len(ws), "median rew/day", statistics.median([x["rew_day_30d"] for x in ws]),
              "median rebate/day", statistics.median([x["rebate_day_30d"] for x in ws]),
              "median trade pnl/day", statistics.median([x["trade_pnl_day_30d"] for x in ws]),
              "median value", statistics.median([x["value_usd"] for x in ws]))
    out = {"made": datetime.datetime.now(datetime.timezone.utc).isoformat(), "concentration": conc,
           "per_market": per_market, "wallets": sorted(wallets, key=lambda x: -x["rew_day_30d"])}
    json.dump(out, open(os.path.join(ROOT, "results", "2026-10-08-mm-makers.json"), "w"), indent=1)
    print("saved")


if __name__ == "__main__":
    main()
