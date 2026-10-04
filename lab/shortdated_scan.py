"""Read-only: negRisk events ending within 72h: YES-basket gaps after fees, and cheap 'near-certain NO' legs."""
import json, sys, urllib.request, datetime as dt
UA = {"User-Agent": "ps-lab/1.0", "Content-Type": "application/json"}
g = lambda u: json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30))
now = dt.datetime.now(dt.timezone.utc)
lo = now.strftime("%Y-%m-%dT%H:%M:%SZ"); hi = (now + dt.timedelta(hours=72)).strftime("%Y-%m-%dT%H:%M:%SZ")
evs = []
for off in range(0, 3000, 100):
    try: p = g(f"https://gamma-api.polymarket.com/events?closed=false&limit=100&offset={off}&end_date_min={lo}&end_date_max={hi}")
    except Exception: break
    evs += p
    if len(p) < 100: break
nr = [e for e in evs if e.get("negRisk") and not e.get("negRiskAugmented")]
print("events ending <72h:", len(evs), "negRisk non-aug:", len(nr))
from collections import Counter
print("tags:", Counter(t["label"] for e in nr for t in (e.get("tags") or [])).most_common(8))
res = []
for e in nr:
    ms = [m for m in e["markets"] if m.get("clobTokenIds")]
    if any(not m.get("active") or m.get("closed") for m in ms): continue
    toks = [json.loads(m["clobTokenIds"]) for m in ms]
    req = urllib.request.Request("https://clob.polymarket.com/books", data=json.dumps([{"token_id": t} for tt in toks for t in tt]).encode(), headers=UA)
    B = None
    for _ in range(3):
        try: B = {b["asset_id"]: b for b in json.load(urllib.request.urlopen(req, timeout=60))}; break
        except Exception: pass
    if B is None: continue
    s = f = 0; d = 1e9; ok = True
    for m, (y, n) in zip(ms, toks):
        a = [(float(x["price"]), float(x["size"])) for x in B.get(y, {}).get("asks", [])]
        if not a: ok = False; break
        p, z = min(a); r = (m.get("feeSchedule") or {}).get("rate") or 0
        s += p; f += r * p * (1 - p); d = min(d, z)
    if ok: res.append((round(1 - s - f, 4), ",".join(t["label"] for t in (e.get("tags") or [])[:3]), round(s, 3), round(d, 1), len(ms), e["title"][:55], (ms[0].get("feeSchedule") or {}).get("rate")))
res.sort(reverse=True)
print("fully quoted:", len(res), " gross sum<1:", sum(1 for r in res if r[2] < 1), " net>0:", sum(1 for r in res if r[0] > 0))
for r in res[:12]: print(r)
