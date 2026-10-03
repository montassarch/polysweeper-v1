"""Read-only: on resolved daily-temperature events, what did NO on 'dead' buckets (2+ below the winner, highest-temp)
trade at, and when? Uses gamma (closed events) + data-api trades."""
import json, sys, urllib.request, datetime as dt
UA = {"User-Agent": "ps-lab/1.0"}
g = lambda u: json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30))
day = sys.argv[1] if len(sys.argv) > 1 else "October 2"
evs = []
for off in (0, 100, 200):
    evs += g(f"https://gamma-api.polymarket.com/events?tag_slug=daily-temperature&closed=true&limit=100&offset={off}&order=endDate&ascending=false")
evs = [e for e in evs if e["title"].startswith("Highest") and day + "?" in e["title"]]
tot = {"n": 0, "usd": 0, "lo": 0, "buyers": {}}
for e in evs:
    ms = e["markets"]
    win = [i for i, m in enumerate(ms) if m.get("outcomePrices") and json.loads(m["outcomePrices"])[0] == "1"]
    if len(win) != 1: continue
    w = win[0]; bands = []
    for m in ms[: max(0, w - 1)]:
        tr = g(f"https://data-api.polymarket.com/trades?market={m['conditionId']}&limit=1000&takerOnly=false")
        nos = [t for t in tr if t["outcome"] == "No" and t["side"] == "BUY" and 0.95 <= t["price"] <= 0.998]
        for t in nos:
            tot["n"] += 1; tot["usd"] += t["size"] * t["price"]
            tot["buyers"][t["proxyWallet"]] = tot["buyers"].get(t["proxyWallet"], 0) + t["size"]
        if nos: bands.append((m["groupItemTitle"], len(nos), round(sum(t["size"] for t in nos)), round(min(t["price"] for t in nos), 3),
                             dt.datetime.utcfromtimestamp(min(t["timestamp"] for t in nos)).strftime("%m-%d %H:%M"),
                             dt.datetime.utcfromtimestamp(max(t["timestamp"] for t in nos)).strftime("%m-%d %H:%M")))
    print(e["title"][23:50], "winner", ms[w]["groupItemTitle"], bands[:3])
print("dead-bucket NO buys 0.95-0.998:", tot["n"], "usd", round(tot["usd"]), "distinct buyers", len(tot["buyers"]))
print("top buyers (shares):", sorted(tot["buyers"].items(), key=lambda x: -x[1])[:5])
