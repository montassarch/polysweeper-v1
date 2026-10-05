"""#5 UMA waiting period: for recently resolved non-sports, non-crypto markets, look at public trades
in the window between the probable UMA proposal (closedTime - liveness) and final resolution (closedTime).
Read-only. Output: lab/results/2026-10-05-uma-window.json"""
import json, time, urllib.request, sys, collections, datetime as dt
UA = {"User-Agent": "polysweeper-research/0.1 (read-only data collection)"}
RAW = "/home/user/polysweeper-v1/lab/data/raw/uma/"
def get(url):
    for i in range(5):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60))
        except Exception:
            time.sleep(2 + 2 * i)
    return None
def ts(s):
    s = s.replace(" ", "T").replace("+00", "+00:00") if "+00:00" not in s else s
    if s.endswith("Z"): s = s[:-1] + "+00:00"
    return dt.datetime.fromisoformat(s).timestamp()
TAGS = sys.argv[2].split(",") if len(sys.argv) > 2 else ["politics", "economy", "tech", "geopolitics", "world", "finance", "elections", "awards", "weather", "pop-culture", "movies", "music", "business"]
since = time.time() - 10 * 86400
mk = {}
for t in TAGS:
    for off in range(0, 600, 100):
        d = get(f"https://gamma-api.polymarket.com/events?closed=true&tag_slug={t}&limit=100&offset={off}&order=closedTime&ascending=false")
        if not d: break
        stop = False
        for e in d:
            for m in e.get("markets", []):
                ct = m.get("closedTime")
                if not ct or ts(ct) < since: continue
                if m.get("conditionId") in mk: continue
                m["_tag"] = t; m["_event"] = e.get("slug")
                mk[m["conditionId"]] = m
            if e.get("closedTime") and ts(e["closedTime"]) < since: stop = True
        time.sleep(0.3)
        if stop: break
print("markets", len(mk), file=sys.stderr)
json.dump(list(mk.values()), open(RAW + "tag_markets" + (sys.argv[3] if len(sys.argv) > 3 else "") + ".json", "w"))
# status patterns (disputes)
pat = collections.Counter(); disp = []
for m in mk.values():
    s = m.get("umaResolutionStatuses") or "[]"
    s = json.loads(s) if isinstance(s, str) else s
    pat[tuple(s)] += 1
    if "disputed" in s: disp.append((m["_tag"], m["question"][:80], s, m.get("outcomePrices")))
res = {"n_markets": len(mk), "status_patterns": {"|".join(k): v for k, v in pat.most_common(12)}, "disputed": disp}
# trades study on markets with volume
cand = [m for m in mk.values() if (m.get("volumeNum") or 0) >= 2000 and m.get("outcomePrices")]
cand.sort(key=lambda m: -(m.get("volumeNum") or 0))
cand = cand[:int(sys.argv[1]) if len(sys.argv) > 1 else 250]
rows = []
for m in cand:
    op = json.loads(m["outcomePrices"]); outs = json.loads(m["outcomes"])
    if "1" not in op: continue
    win = outs[op.index("1")]
    live = m.get("customLiveness") or 7200
    close = ts(m["closedTime"]); prop = close - live
    end = ts(m["endDate"]) if m.get("endDate") else None
    trades = []
    for off in range(0, 3000, 500):
        d = get(f"https://data-api.polymarket.com/trades?market={m['conditionId']}&limit=500&offset={off}&takerOnly=false")
        if not d: break
        trades += d
        if len(d) < 500 or d[-1]["timestamp"] < prop - 6 * 3600: break
        time.sleep(0.25)
    # winner-side buys price-equivalent: BUY winner at p, or SELL loser at q (=winner at 1-q)
    def wp(t):
        return t["price"] if t["outcome"] == win else 1 - t["price"]
    w = [t for t in trades if prop - 60 <= t["timestamp"] <= close + 60]
    pre = [t for t in trades if prop - 6 * 3600 <= t["timestamp"] < prop - 60]
    band = [t for t in w if 0.985 <= wp(t) <= 0.998]
    rows.append({
        "tag": m["_tag"], "q": m["question"][:90], "vol": round(m.get("volumeNum") or 0), "live": live,
        "winner": win, "close": m["closedTime"], "end_to_close_h": round((close - end) / 3600, 2) if end else None,
        "n_window": len(w), "n_band": len(band),
        "band_shares": round(sum(t["size"] for t in band)),
        "band_usd_profit": round(sum(t["size"] * (1 - wp(t)) for t in band), 2),
        "min_wp_window": round(min((wp(t) for t in w), default=1), 4),
        "loser_buys_window_over_0.01": sum(1 for t in w if 1 - wp(t) > 0.01),
        "band_minutes_after_prop": sorted(round((t["timestamp"] - prop) / 60, 1) for t in band)[:8],
        "n_pre6h": len(pre), "min_wp_pre": round(min((wp(t) for t in pre), default=1), 4),
        "hit_cap": len(trades) >= 3000,
    })
    time.sleep(0.2)
res["rows"] = rows
json.dump(res, open("/home/user/polysweeper-v1/lab/results/2026-10-05-uma-window" + (sys.argv[3] if len(sys.argv) > 3 else "") + ".json", "w"), indent=1)
print("done", len(rows))
