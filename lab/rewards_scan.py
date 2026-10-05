"""#8 maker side: list markets paying liquidity rewards (public CLOB endpoint) and estimate what a small
two-sided quote would earn given the current book (snapshot). Read-only.
Scoring (Polymarket docs, liquidity rewards): S(v,s) = ((v - s)/v)^2 * size, s = distance from mid in cents,
v = rewards_max_spread; mid in [0.10,0.90]: Q = max(min(Qbid,Qask), max(Qbid,Qask)/3); else Q = min(Qbid,Qask)."""
import json, time, urllib.request, sys, random, collections
UA = {"User-Agent": "polysweeper-research/0.1 (read-only data collection)", "Content-Type": "application/json"}
def req(url, body=None):
    for i in range(5):
        try:
            r = urllib.request.Request(url, headers=UA, data=json.dumps(body).encode() if body is not None else None)
            return json.load(urllib.request.urlopen(r, timeout=60))
        except Exception:
            time.sleep(2 + 2 * i)
    return None
allm, cur = [], ""
while True:
    d = req(f"https://clob.polymarket.com/rewards/markets/current?next_cursor={cur}")
    if not d: break
    allm += d["data"]; cur = d.get("next_cursor")
    if not cur or cur == "LTE=": break
    time.sleep(0.2)
rates = [m.get("total_daily_rate") or 0 for m in allm]
tot = sum(rates)
hist = collections.Counter()
for r in rates:
    hist["<1" if r < 1 else "1-4.99" if r < 5 else "5-24.99" if r < 25 else "25-99" if r < 100 else "100+"] += 1
print("reward markets", len(allm), "total $/day", round(tot), dict(hist))
top = sorted(allm, key=lambda m: -(m.get("total_daily_rate") or 0))
random.seed(5)
sample = top[:60] + random.sample(top[60:], min(140, len(top) - 60))
# need token ids: use CLOB market endpoint
out = []
for m in sample:
    mk = req(f"https://clob.polymarket.com/markets/{m['condition_id']}")
    if not mk or not mk.get("tokens"): continue
    tok = mk["tokens"][0]["token_id"]
    bk = req("https://clob.polymarket.com/books", [{"token_id": tok}])
    if not bk: continue
    b = bk[0]
    bids = [(float(x["price"]), float(x["size"])) for x in b.get("bids", [])]
    asks = [(float(x["price"]), float(x["size"])) for x in b.get("asks", [])]
    if not bids or not asks: continue
    bb, ba = max(p for p, _ in bids), min(p for p, _ in asks)
    mid = (bb + ba) / 2
    v = m["rewards_max_spread"]; mn = m["rewards_min_size"]
    def S(p, sz):
        s = abs(p - mid) * 100
        return ((v - s) / v) ** 2 * sz if s < v and sz >= mn else 0
    qb = sum(S(p, sz) for p, sz in bids); qa = sum(S(p, sz) for p, sz in asks)
    two = mid < 0.10 or mid > 0.90
    Qtot = min(qb, qa) if two else max(min(qb, qa), max(qb, qa) / 3)
    # our quote: min size (>= mn) both sides at half the max spread
    ours_sz = max(mn, 5)
    qo = ((v - v / 2) / v) ** 2 * ours_sz
    share = qo / (Qtot + qo) if Qtot + qo > 0 else 1
    out.append({"q": mk.get("question", "")[:70], "rate": m.get("total_daily_rate"), "v": v, "min": mn, "mid": round(mid, 3),
                "spread": round(ba - bb, 3), "Qbook": round(Qtot), "our_sz": ours_sz,
                "our_usd_day": round(share * (m.get("total_daily_rate") or 0), 4),
                "capital": round(ours_sz * (mid + (1 - mid)), 2)})
    time.sleep(0.15)
out.sort(key=lambda r: -r["our_usd_day"])
json.dump({"n": len(allm), "total_daily": tot, "hist": hist, "sample": out}, open("/home/user/polysweeper-v1/lab/results/2026-10-05-rewards-scan.json", "w"), indent=1)
for r in out[:15]: print(r)
ex = [r for r in out if r["mid"] > 0.97 or r["mid"] < 0.03]
print("extreme-mid markets in sample", len(ex), [ (r["q"][:40], r["rate"], r["our_usd_day"]) for r in ex[:8]])
print("median our $/day", sorted(r["our_usd_day"] for r in out)[len(out)//2], "sum top10", round(sum(r["our_usd_day"] for r in out[:10]),2))
