"""Backup study (market making), part 1: snapshot of the whole open Polymarket universe.

Read-only, standard library, public endpoints only. No orders, no wallets.
- Liquidity rewards per market (CLOB /rewards/markets/current): daily rate, max spread v (cents), min size.
- Gamma events (keyset): tags, fee schedule, clearBookOnStart, 24 h volume, end date.
- Books (CLOB POST /books) for a sample per market type: spread, depth near mid, total reward score (Q) of
  everyone already quoting, and what a small two-sided quote of ours would score.

Reward score (docs.polymarket.com/programs/liquidity-rewards): S = ((v - s)/v)^2 per share, s = distance from
the (size-cutoff adjusted) mid in cents; Q_one = bids on YES (+ asks on NO), Q_two = asks on YES (+ bids on NO).
Mid in [0.10, 0.90]: Q = max(min(Q1,Q2), max(Q1,Q2)/3); outside: Q = min(Q1,Q2). Our share = Q_ours/(Q_book+Q_ours).
The YES book already holds the mirrored NO orders, so one book per market is enough.
Approximations (stated in the note): book levels are treated as single orders (we cannot see individual orders,
levels below min size are dropped), one snapshot only.

Usage: py -3 lab/mm_scan.py            -> lab/results/2026-10-08-mm-scan.json (+ raw cache in lab/data/raw/mm/)
"""
import json, os, random, sys, time, urllib.request, datetime, collections, statistics

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, "data", "raw", "mm")
os.makedirs(RAW, exist_ok=True)
UA = {"User-Agent": "polysweeper-research/0.1 (read-only data collection)"}
NOW = datetime.datetime.now(datetime.timezone.utc)


def req(url, body=None, tries=5):
    for i in range(tries):
        try:
            h = dict(UA)
            data = None
            if body is not None:
                h["Content-Type"] = "application/json"
                data = json.dumps(body).encode()
            r = urllib.request.Request(url, headers=h, data=data)
            return json.load(urllib.request.urlopen(r, timeout=60))
        except Exception as e:  # noqa
            err = e
            time.sleep(1.5 * (i + 1))
    print("FAILED", url[:120], err, file=sys.stderr)
    return None


def cached(name, fn):
    p = os.path.join(RAW, name)
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < 6 * 3600:
        return json.load(open(p, encoding="utf-8"))
    d = fn()
    json.dump(d, open(p, "w", encoding="utf-8"))
    return d


def pull_rewards():
    out, cur = [], ""
    while True:
        d = req(f"https://clob.polymarket.com/rewards/markets/current?next_cursor={cur}")
        if not d:
            break
        out += d["data"]
        cur = d.get("next_cursor")
        if not cur or cur == "LTE=":
            break
        time.sleep(0.15)
    return out


def pull_events():
    out, cur = [], None
    while True:
        u = "https://gamma-api.polymarket.com/events/keyset?closed=false&limit=100"
        if cur:
            u += "&after_cursor=" + cur
        d = req(u)
        if not d:
            break
        for e in d.get("events", []):
            tags = [t.get("slug") for t in (e.get("tags") or [])]
            for m in e.get("markets") or []:
                if m.get("closed") or not m.get("enableOrderBook") or not m.get("acceptingOrders"):
                    continue
                try:
                    toks = json.loads(m.get("clobTokenIds") or "[]")
                except Exception:
                    toks = []
                if len(toks) != 2:
                    continue
                out.append({
                    "cid": m.get("conditionId"), "q": (m.get("question") or "")[:110], "tok": toks[0],
                    "ev": e.get("slug"), "evtitle": (e.get("title") or "")[:80], "tags": tags,
                    "negRisk": bool(m.get("negRisk")), "fee": m.get("feeSchedule"),
                    "clear": m.get("clearBookOnStart"), "hold": m.get("holdingRewardsEnabled"),
                    "vol24": float(m.get("volume24hr") or 0), "liq": float(m.get("liquidityClob") or 0),
                    "end": m.get("endDate"), "game": m.get("gameStartTime") or e.get("startTime"),
                    "smt": m.get("sportsMarketType"), "bb": m.get("bestBid"), "ba": m.get("bestAsk"),
                    "v": m.get("rewardsMaxSpread"), "mn": m.get("rewardsMinSize"), "tick": m.get("orderPriceMinTickSize"),
                })
        cur = d.get("next_cursor")
        if not cur or not d.get("events"):
            break
        time.sleep(0.12)
    return out


def days_to(end):
    try:
        t = datetime.datetime.fromisoformat(end.replace("Z", "+00:00"))
        return (t - NOW).total_seconds() / 86400
    except Exception:
        return None


def mtype(m):
    tags = set(m["tags"] or [])
    q = m["q"].lower()
    fee = m["fee"] or {}
    rate = fee.get("rate")
    reb = fee.get("rebateRate")
    sports = ("sports" in tags) or (rate == 0.05 and reb == 0.15) or bool(m["clear"]) or ("esports" in tags)
    if sports:
        dt = days_to(m["game"]) if m.get("game") else None
        if m["clear"] or (dt is not None and dt < 3):
            smt = (m.get("smt") or "").lower()
            if smt in ("moneyline", "") and (" vs" in q or "win" in q or "winner" in q) and "spread" not in q and "o/u" not in q:
                return "sports_game_moneyline"
            return "sports_game_lines_props"
        return "sports_futures"
    if "crypto" in tags or rate == 0.07:
        if "up or down" in q:
            return "crypto_updown"
        return "crypto_ladder_other"
    if "weather" in tags or "temperature" in q:
        return "weather"
    if ("stocks" in tags or "equities" in tags or "finance" in tags or "commodities" in tags or "forex" in tags) and (
            "close" in q or "up or down" in q or "above" in q or "finish" in q or "hit" in q):
        return "stock_finance_ladder"
    if "elections" in tags or "politics" in tags or "geopolitics" in tags or "world" in tags or "us-politics" in tags:
        dte = days_to(m["end"]) if m.get("end") else None
        if dte is not None and dte > 60:
            return "politics_long_dated"
        return "politics_short_dated"
    if "mentions" in tags or "culture" in tags or "pop-culture" in tags or "tech" in tags or "economy" in tags or "economics" in tags:
        return "culture_tech_econ_mentions"
    dte = days_to(m["end"]) if m.get("end") else None
    if dte is not None and dte > 60:
        return "other_long_dated"
    return "other"


def score_book(book, v, mn, tick):
    """Return dict with spread, depth, Q of the book and our score options."""
    bids = sorted(((float(x["price"]), float(x["size"])) for x in book.get("bids", [])), key=lambda t: -t[0])
    asks = sorted(((float(x["price"]), float(x["size"])) for x in book.get("asks", [])), key=lambda t: t[0])
    if not bids or not asks:
        return None
    bb, ba = bids[0][0], asks[0][0]
    # size-cutoff adjusted mid: best levels with at least min size
    abb = next((p for p, s in bids if s >= mn), bb)
    aba = next((p for p, s in asks if s >= mn), ba)
    mid = (abb + aba) / 2
    raw_mid = (bb + ba) / 2

    def S(p):
        s = abs(p - mid) * 100
        return ((v - s) / v) ** 2 if s < v else 0.0

    q1 = sum(S(p) * s for p, s in bids if s >= mn)
    q2 = sum(S(p) * s for p, s in asks if s >= mn)
    two_needed = mid < 0.10 or mid > 0.90
    qbook = min(q1, q2) if two_needed else max(min(q1, q2), max(q1, q2) / 3)

    def depth(c):
        return (sum(s * p for p, s in bids if mid - p <= c / 100 + 1e-9),
                sum(s * (1 - p) for p, s in asks if p - mid <= c / 100 + 1e-9))

    size = max(mn, 5)
    # option A: join the best bid and best ask (if inside v); option B: quote at v/2 from mid
    sa_b = S(bb) * size
    sa_a = S(ba) * size
    qa = min(sa_b, sa_a) if two_needed else max(min(sa_b, sa_a), max(sa_b, sa_a) / 3)
    sb = ((v - v / 2) / v) ** 2 * size
    cap_a = size * bb + size * (1 - ba)
    cap_b = size * max(mid - v / 200, 0.01) + size * max(1 - mid - v / 200, 0.01)
    return {"bb": bb, "ba": ba, "mid": round(mid, 4), "raw_mid": round(raw_mid, 4), "spread": round(ba - bb, 4),
            "d1": [round(x) for x in depth(1)], "d2": [round(x) for x in depth(2)], "d5": [round(x) for x in depth(5)],
            "q1": round(q1, 1), "q2": round(q2, 1), "qbook": round(qbook, 1), "size": size,
            "qA": round(qa, 2), "qB": round(sb, 2), "capA": round(cap_a, 2), "capB": round(cap_b, 2),
            "nb": len(bids), "na": len(asks)}


def main():
    t0 = time.time()
    rw = cached("rewards-current.json", pull_rewards)
    print("reward markets", len(rw), "total $/day", round(sum(r.get("total_daily_rate") or 0 for r in rw)), round(time.time() - t0), "s")
    ev = cached("gamma-open-markets.json", pull_events)
    print("open orderbook markets", len(ev), round(time.time() - t0), "s")
    rmap = {r["condition_id"]: r for r in rw}
    by = collections.defaultdict(list)
    for m in ev:
        r = rmap.get(m["cid"])
        m["rate"] = (r.get("total_daily_rate") or 0) if r else 0
        if r:
            m["v"] = r.get("rewards_max_spread")
            m["mn"] = r.get("rewards_min_size")
        m["type"] = mtype(m)
        by[m["type"]].append(m)
    seen = set(m["cid"] for m in ev)
    missing = [r for r in rw if r["condition_id"] not in seen]
    summary = {}
    for t, ms in sorted(by.items()):
        rated = [m for m in ms if m["rate"] > 0]
        fees = collections.Counter(json.dumps(m["fee"], sort_keys=True) if m["fee"] else "none" for m in ms)
        summary[t] = {"markets": len(ms), "with_rewards": len(rated),
                      "rewards_usd_day": round(sum(m["rate"] for m in rated)),
                      "median_rate": statistics.median([m["rate"] for m in rated]) if rated else 0,
                      "top_rate": max([m["rate"] for m in rated], default=0),
                      "vol24_usd": round(sum(m["vol24"] for m in ms)),
                      "median_vol24_rated": round(statistics.median([m["vol24"] for m in rated])) if rated else 0,
                      "clearBookOnStart": sum(1 for m in ms if m["clear"]),
                      "holdingRewards": sum(1 for m in ms if m["hold"]),
                      "fee_schedules": fees.most_common(3)}
    print(json.dumps(summary, indent=1))
    print("reward markets not in open gamma list", len(missing), round(sum(r.get("total_daily_rate") or 0 for r in missing)))

    # sample books: per type, top 40 by reward rate + 40 random rated + 20 random unrated
    random.seed(8)
    sample = []
    for t, ms in by.items():
        rated = sorted([m for m in ms if m["rate"] > 0], key=lambda m: -m["rate"])
        unrated = [m for m in ms if m["rate"] <= 0]
        pick = rated[:40] + random.sample(rated[40:], min(40, max(0, len(rated) - 40))) + random.sample(unrated, min(20, len(unrated)))
        sample += pick
    print("books to fetch", len(sample))
    books = {}
    for i in range(0, len(sample), 40):
        chunk = sample[i:i + 40]
        d = req("https://clob.polymarket.com/books", [{"token_id": m["tok"]} for m in chunk])
        for b in d or []:
            books[b.get("asset_id")] = b
        time.sleep(0.25)
    rows = []
    for m in sample:
        b = books.get(m["tok"])
        if not b:
            continue
        v = float(m["v"] or 0)
        mn = float(m["mn"] or 0)
        if v <= 0:
            v, mn = 4.5, 20  # unrated: score with a typical config only to compare books
        sc = score_book(b, v, mn, m.get("tick"))
        if not sc:
            rows.append({"type": m["type"], "q": m["q"], "rate": m["rate"], "empty_side": True, "vol24": m["vol24"]})
            continue
        shareA = sc["qA"] / (sc["qbook"] + sc["qA"]) if sc["qA"] > 0 else 0
        shareB = sc["qB"] / (sc["qbook"] + sc["qB"]) if sc["qB"] > 0 else 0
        fee = m["fee"] or {}
        p = sc["mid"]
        fee_pool = (fee.get("rate") or 0) * (1 - p) * m["vol24"] * (fee.get("rebateRate") or 0)  # vol24 ~ sum(price*shares)
        rows.append({"type": m["type"], "q": m["q"], "ev": m["ev"], "rate": m["rate"], "v": v, "mn": mn,
                     "vol24": round(m["vol24"]), "rebate_pool_day": round(fee_pool, 2), "clear": m["clear"],
                     "end_days": round(days_to(m["end"]), 1) if m.get("end") and days_to(m["end"]) is not None else None,
                     **sc, "usdA": round(shareA * m["rate"], 3), "usdB": round(shareB * m["rate"], 3),
                     "shareA": round(shareA, 4), "shareB": round(shareB, 4)})
    # per type book stats
    bt = {}
    for t in sorted(set(r["type"] for r in rows)):
        rs = [r for r in rows if r["type"] == t and not r.get("empty_side")]
        rr = [r for r in rs if r["rate"] > 0]
        allr = [r for r in rows if r["type"] == t]
        if not rs:
            continue
        med = lambda xs: round(statistics.median(xs), 4) if xs else None
        bt[t] = {"books": len(allr), "one_side_empty": len(allr) - len(rs),
                 "median_spread_c": med([r["spread"] * 100 for r in rs]),
                 "median_depth_2c_usd": med([sum(r["d2"]) for r in rs]),
                 "median_depth_5c_usd": med([sum(r["d5"]) for r in rs]),
                 "median_vol24": med([r["vol24"] for r in rs]),
                 "rated_books": len(rr),
                 "median_reward_rate": med([r["rate"] for r in rr]),
                 "median_qbook": med([r["qbook"] for r in rr]),
                 "median_our_usd_day_join_best": med([r["usdA"] for r in rr]),
                 "median_our_usd_day_half_v": med([r["usdB"] for r in rr]),
                 "sum_top10_usdA": round(sum(sorted([r["usdA"] for r in rr], reverse=True)[:10]), 2),
                 "median_capital_usd": med([r["capA"] for r in rr]),
                 "median_rebate_pool_day": med([r["rebate_pool_day"] for r in rs])}
    print(json.dumps(bt, indent=1))
    rows.sort(key=lambda r: -(r.get("usdA") or 0))
    out = {"made": NOW.isoformat(), "reward_markets": len(rw),
           "reward_usd_day_total": round(sum(r.get("total_daily_rate") or 0 for r in rw)),
           "reward_rate_hist": dict(collections.Counter(
               "<1" if (r.get("total_daily_rate") or 0) < 1 else "1-4.99" if r["total_daily_rate"] < 5 else "5-24.99" if r["total_daily_rate"] < 25
               else "25-99" if r["total_daily_rate"] < 100 else "100-999" if r["total_daily_rate"] < 1000 else "1000+" for r in rw)),
           "open_markets": len(ev), "by_type": summary, "books_by_type": bt,
           "top_sample_rows": rows[:40],
           "reward_rate_top20": sorted(([m["rate"], m["type"], m["q"][:70]] for m in ev if m["rate"] > 0), reverse=True)[:20]}
    json.dump(out, open(os.path.join(ROOT, "results", "2026-10-08-mm-scan.json"), "w"), indent=1)
    json.dump(rows, open(os.path.join(RAW, "scan-rows.json"), "w"))
    print("done", round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
