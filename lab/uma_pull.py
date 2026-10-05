"""Pull recently closed markets from Gamma (read-only) for the UMA window study (#5)."""
import json, time, urllib.request, sys
UA = {"User-Agent": "polysweeper-research/0.1 (read-only data collection)"}
def get(url):
    for i in range(5):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60))
        except Exception as e:
            time.sleep(2 + i * 2)
    raise RuntimeError(url)
out = []
keep = ["id","question","conditionId","slug","closedTime","umaEndDate","resolvedBy","customLiveness",
        "umaResolutionStatus","umaResolutionStatuses","automaticallyResolved","feeType","feeSchedule",
        "outcomes","outcomePrices","volumeNum","clobTokenIds","negRisk","umaBond","umaReward","endDate",
        "gameStartTime","sportsMarketType","rewardsMinSize","rewardsMaxSpread","holdingRewardsEnabled"]
N = int(sys.argv[1]) if len(sys.argv) > 1 else 6000
for off in range(0, N, 500):
    d = get(f"https://gamma-api.polymarket.com/markets?closed=true&limit=500&offset={off}&order=closedTime&ascending=false")
    if not d: break
    for m in d:
        r = {k: m.get(k) for k in keep}
        ev = (m.get("events") or [{}])[0]
        r["event_slug"] = ev.get("slug"); r["event_title"] = ev.get("title")
        r["series"] = ev.get("seriesSlug") or (ev.get("series") or [{}])[0].get("slug") if ev else None
        out.append(r)
    print(off, d[-1].get("closedTime"), file=sys.stderr)
    time.sleep(0.4)
json.dump(out, open("/home/user/polysweeper-v1/lab/data/raw/uma/closed_markets.json", "w"))
print(len(out))
