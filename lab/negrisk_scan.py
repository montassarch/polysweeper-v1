"""Read-only scan: complete-set (YES+NO) and negRisk basket gaps on live books."""
import json, sys, time, urllib.request
UA = {"User-Agent": "ps-lab/1.0", "Content-Type": "application/json"}
def get(u):
    return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30))
def books(tids):
    out = {}
    for i in range(0, len(tids), 400):
        req = urllib.request.Request("https://clob.polymarket.com/books", data=json.dumps([{"token_id": t} for t in tids[i:i+400]]).encode(), headers=UA)
        for b in json.load(urllib.request.urlopen(req, timeout=60)):
            out[b["asset_id"]] = b
    return out
def best_ask(b):
    a = [(float(x["price"]), float(x["size"])) for x in (b or {}).get("asks", [])]
    return min(a) if a else (None, 0)
def best_bid(b):
    a = [(float(x["price"]), float(x["size"])) for x in (b or {}).get("bids", [])]
    return max(a) if a else (None, 0)
evs, off = [], 0
while True:
    try:
        page = get(f"https://gamma-api.polymarket.com/events?closed=false&active=true&limit=100&offset={off}")
    except Exception as ex:
        print("stop at offset", off, ex, file=sys.stderr); break
    evs += page; off += 100
    if len(page) < 100 or off > 20000: break
rows = []
for e in evs:
    ms = [m for m in e.get("markets", []) if m.get("active") and not m.get("closed") and m.get("clobTokenIds") and m.get("enableOrderBook")]
    for m in ms:
        m["_t"] = json.loads(m["clobTokenIds"])
    rows.append((e, ms))
tids = [t for e, ms in rows for m in ms for t in m["_t"]]
print("events", len(evs), "tokens", len(tids), file=sys.stderr)
B = books(tids)
cs, yb, nb = [], [], []
for e, ms in rows:
    for m in ms:
        ya, ys = best_ask(B.get(m["_t"][0])); na, ns = best_ask(B.get(m["_t"][1]))
        if ya and na: cs.append((round(ya+na, 4), min(ys, ns), m["question"][:60], (m.get("feeSchedule") or {}).get("rate")))
    if e.get("negRisk") and len(ms) >= 2:
        allm = e.get("markets", [])
        y = [best_ask(B.get(m["_t"][0])) for m in ms]
        n = [best_ask(B.get(m["_t"][1])) for m in ms]
        info = dict(title=e["title"][:60], n=len(ms), total=len(allm), aug=e.get("negRiskAugmented"),
                    other=sum(1 for m in ms if m.get("negRiskOther")),
                    rate=max(((m.get("feeSchedule") or {}).get("rate") or 0) for m in ms))
        if all(p for p, s in y):
            yb.append(dict(info, sum=round(sum(p for p, s in y), 4), depth=min(s for p, s in y)))
        if all(p for p, s in n):
            nb.append(dict(info, sum=round(sum(p for p, s in n), 4), payout=len(ms)-1, depth=min(s for p, s in n)))
mir=[]
for e, ms in rows:
    for m in ms:
        ya,_=best_ask(B.get(m["_t"][0])); nbid,_=best_bid(B.get(m["_t"][1]))
        if ya and nbid: mir.append(round(ya-(1-nbid),4))
print("mirror check YESask-(1-NObid): zero share", sum(1 for x in mir if abs(x)<1e-9)/max(1,len(mir)), len(mir))
cs.sort()
print("complete sets with both asks:", len(cs), " min sums:", cs[:5])
print("count sum<1:", sum(1 for c in cs if c[0] < 1), " sum==1:", sum(1 for c in cs if c[0] == 1))
yb.sort(key=lambda r: r["sum"])
print("\nnegRisk YES baskets fully quoted:", len(yb), " sum<1:", sum(1 for r in yb if r["sum"] < 1))
for r in [r for r in yb if not r["aug"]][:10]: print(r)
print("non-augmented sum<1:", sum(1 for r in yb if r["sum"]<1 and not r["aug"]))
nb.sort(key=lambda r: r["sum"] - r["payout"])
print("\nnegRisk NO baskets:", len(nb), " sum<payout:", sum(1 for r in nb if r["sum"] < r["payout"]))
for r in [r for r in nb if not r["aug"]][:6]: print(r)
json.dump(dict(t=time.time(), cs=cs[:50], yb=yb[:50], nb=nb[:50]), open("/home/user/polysweeper-v1/lab/data/raw/negrisk_scan_%d.json" % time.time(), "w"))
