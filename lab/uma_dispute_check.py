"""For disputed markets (last 10 days, non-sports tags) check whether the eventual LOSER was ever priced >= 0.95
in the last 7 days before resolution (sign that a proposal for the loser was believed, then overturned).
Also: taker side of 0.985-0.998 winner trades in the UMA window for markets that had them. Read-only."""
import json, time, urllib.request, datetime as dt, collections
UA = {"User-Agent": "polysweeper-research/0.1 (read-only data collection)"}
def get(u):
    for i in range(4):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60))
        except Exception: time.sleep(2 + 2 * i)
    return []
def ts(s): return dt.datetime.fromisoformat(s.replace(" ", "T") + (":00" if s.endswith("+00") else "")).timestamp()
ms = json.load(open("/home/user/polysweeper-v1/lab/data/raw/uma/tag_markets.json")) + json.load(open("/home/user/polysweeper-v1/lab/data/raw/uma/tag_markets-mentions.json"))
by = {m["conditionId"]: m for m in ms}
def trades(cid, since):
    out = []
    for off in range(0, 3000, 500):
        d = get(f"https://data-api.polymarket.com/trades?market={cid}&limit=500&offset={off}")
        out += d or []
        if not d or len(d) < 500 or d[-1]["timestamp"] < since: break
        time.sleep(0.2)
    return out
res = {"disputed": [], "band_side": collections.Counter(), "band_side_shares": collections.Counter()}
for m in by.values():
    s = m.get("umaResolutionStatuses") or "[]"; s = json.loads(s) if isinstance(s, str) else s
    if "disputed" not in s or not m.get("outcomePrices"): continue
    op = json.loads(m["outcomePrices"]); outs = json.loads(m["outcomes"])
    if "1" not in op: res["disputed"].append({"q": m["question"][:70], "note": "no 0/1 result", "op": op}); continue
    win = outs[op.index("1")]; close = ts(m["closedTime"])
    t = [x for x in trades(m["conditionId"], close - 7 * 86400) if x["timestamp"] >= close - 7 * 86400]
    lp = [(1 - x["price"]) if x["outcome"] == win else x["price"] for x in t]
    res["disputed"].append({"q": m["question"][:70], "vol": round(m.get("volumeNum") or 0), "n": len(t),
                            "max_loser_px_7d": round(max(lp), 3) if lp else None, "statuses": len(s)})
    time.sleep(0.2)
for f in ["/home/user/polysweeper-v1/lab/results/2026-10-05-uma-window.json", "/home/user/polysweeper-v1/lab/results/2026-10-05-uma-window-mentions.json"]:
    for r in json.load(open(f))["rows"]:
        if r["n_band"] == 0: continue
        m = next((x for x in by.values() if x["question"][:90] == r["q"] and x["closedTime"] == r["close"]), None)
        if not m: continue
        close = ts(m["closedTime"]); prop = close - r["live"]; win = r["winner"]
        for x in trades(m["conditionId"], prop - 60):
            if not (prop - 60 <= x["timestamp"] <= close + 60): continue
            wp = x["price"] if x["outcome"] == win else 1 - x["price"]
            if 0.985 <= wp <= 0.998:
                # taker bought winner (BUY winner or SELL loser? SELL loser = taker sold loser -> a resting loser bid; equiv winner ask lifted? no)
                kind = "taker_buys_winner(ask_was_there)" if (x["side"] == "BUY") == (x["outcome"] == win) else "taker_sells_winner(bid_got_filled)"
                res["band_side"][kind] += 1; res["band_side_shares"][kind] += round(x["size"])
        time.sleep(0.2)
json.dump(res, open("/home/user/polysweeper-v1/lab/results/2026-10-05-uma-dispute-check.json", "w"), indent=1)
for d in res["disputed"]: print(d)
print(dict(res["band_side"]), dict(res["band_side_shares"]))
