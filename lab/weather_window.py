"""Read-only: daily temperature events whose local day may be over; what is still for sale at 0.95-0.998?"""
import json, urllib.request
UA = {"User-Agent": "ps-lab/1.0", "Content-Type": "application/json"}
g = lambda u: json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30))
import sys
day = sys.argv[1] if len(sys.argv) > 1 else "October 3"
evs = [e for e in g("https://gamma-api.polymarket.com/events?tag_slug=daily-temperature&closed=false&limit=200") if day + "?" in e["title"]]
for e in sorted(evs, key=lambda e: e["title"]):
    ms = [m for m in e["markets"] if m.get("clobTokenIds") and m.get("active") and not m.get("closed")]
    toks = [json.loads(m["clobTokenIds"]) for m in ms]
    B = {}
    for _ in range(3):
        try:
            req = urllib.request.Request("https://clob.polymarket.com/books", data=json.dumps([{"token_id": t} for tt in toks for t in tt]).encode(), headers=UA)
            B = {b["asset_id"]: b for b in json.load(urllib.request.urlopen(req, timeout=60))}; break
        except Exception: pass
    yes_ok = no_ok = 0.0; top = None
    for m, (y, n) in zip(ms, toks):
        ya = [(float(x["price"]), float(x["size"])) for x in B.get(y, {}).get("asks", [])]
        na = [(float(x["price"]), float(x["size"])) for x in B.get(n, {}).get("asks", [])]
        yb = max([float(x["price"]) for x in B.get(y, {}).get("bids", [])] or [0])
        if top is None or yb > top[1]: top = (m["groupItemTitle"], yb, min(ya)[0] if ya else None)
        yes_ok += sum(p * s for p, s in ya if 0.95 <= p <= 0.998)
        no_ok += sum(p * s for p, s in na if 0.95 <= p <= 0.998)
    print(f"{e['title'][:48]:48} top={top} $YES@.95-.998={yes_ok:7.0f} $NO@.95-.998={no_ok:7.0f} uma={ms[0].get('umaResolutionStatus') if ms else None}")
