"""Read-only: US 'Highest temperature' events for one day. NO buys at 0.95-0.998 on buckets below the winner,
made on the event day 15:00-23:59 UTC (11:00-19:59 EDT), by distance below the winner and by hour."""
import json, sys, time, urllib.request, datetime as dt
from collections import defaultdict
UA = {"User-Agent": "ps-lab/1.0"}
def g(u):
    for i in range(5):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30))
        except Exception as ex:
            time.sleep(2 + 3 * i)
    return []
day, iso = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else ("October 2", "2026-10-02")
evs = []
for off in (0, 100, 200, 300):
    evs += g(f"https://gamma-api.polymarket.com/events?tag_slug=daily-temperature&closed=true&limit=100&offset={off}&order=endDate&ascending=false")
print("fetched", len(evs), file=sys.stderr)
evs = [e for e in evs if e["title"].startswith("Highest") and day + "?" in e["title"] and e["markets"][0].get("groupItemTitle", "").find("\u00b0F") >= 0]
d0 = dt.datetime.fromisoformat(iso).replace(tzinfo=dt.timezone.utc)
lo, hi = (d0 + dt.timedelta(hours=15)).timestamp(), (d0 + dt.timedelta(hours=24)).timestamp()
bydist = defaultdict(lambda: [0, 0.0, 0.0]); byhour = defaultdict(lambda: [0, 0.0]); wallets = defaultdict(float)
pmin = defaultdict(lambda: 1); wallets_l = defaultdict(float)
for e in evs:
    ms = e["markets"]
    win = [i for i, m in enumerate(ms) if m.get("outcomePrices") and json.loads(m["outcomePrices"])[0] == "1"]
    if len(win) != 1: continue
    w = win[0]
    for i, m in enumerate(ms[:w + 1]):
        time.sleep(0.4)
        tr = g(f"https://data-api.polymarket.com/trades?market={m['conditionId']}&limit=1000&takerOnly=true")
        for t in tr:
            if t["outcome"] == "No" and t["side"] == "BUY" and 0.95 <= t["price"] <= 0.998 and lo <= t["timestamp"] < hi:
                k = min(w - i, 3)
                if k == 0: wallets_l[t['proxyWallet']] += t['size']
                bydist[k][0] += 1; bydist[k][1] += t["size"]; bydist[k][2] += t["size"] * (1 - t["price"])
                pmin[k] = min(pmin[k], t["price"])
                byhour[dt.datetime.utcfromtimestamp(t["timestamp"]).hour][0] += 1; byhour[dt.datetime.utcfromtimestamp(t["timestamp"]).hour][1] += t["size"]
                wallets[t["proxyWallet"]] += t["size"]
print("US events:", len(evs))
for k in sorted(bydist): print(f"  {k}{'+' if k==3 else ''} buckets below winner: taker NO buys={bydist[k][0]} shares={bydist[k][1]:.0f} gross edge=${bydist[k][2]:.1f} min price={pmin[k]}")
print("  (0 = the WINNING bucket: these NO buys at 0.95+ LOST)")
print("  by UTC hour (buys, shares):", {h: (v[0], round(v[1])) for h, v in sorted(byhour.items())})
print("  distinct taker wallets:", len(wallets), " top5 share of volume:", round(sum(sorted(wallets.values())[-5:]) / max(1, sum(wallets.values())), 2))
