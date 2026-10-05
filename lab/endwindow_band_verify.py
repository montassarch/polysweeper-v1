"""Gamma resolution + public trades for the end-window band hits (read-only)."""
import json, sys, time, datetime as dt
sys.path.insert(0, "/home/user/polysweeper-v1/code")
from polysweeper.collector import get_json, GAMMA
D = "/home/user/polysweeper-v1/code/data/shadow/"
ew = {}
for l in open(D + "events.jsonl"):
    if '"end_window"' in l:
        r = json.loads(l)
        if r.get("type") == "end_window" and r["max_shares_096_0995"] >= 5: ew[r["market_id"]] = r
ids = list(ew) + ["5253569"]
out = {}
fmt = lambda t: dt.datetime.utcfromtimestamp(t).strftime("%m-%d %H:%M:%S")
for m in ids:
    g = get_json(f"{GAMMA}/markets/{m}")
    outs = json.loads(g["outcomes"]); px = json.loads(g["outcomePrices"])
    r = ew.get(m)
    t0 = r["t0"] if r else None
    print(m, g["question"][:60], "| outcomes", outs, "prices", px, "closed", g.get("closed"), "closedTime", g.get("closedTime"),
          "uma", g.get("umaResolutionStatus"), "start", g.get("gameStartTime") or g.get("startTime"))
    if r: print("   t0", fmt(t0), "watched winner idx", r["winner_idx"], "score", r["score_at_start"])
    cond = g["conditionId"]
    trades = []
    for off in range(0, 3000, 500):
        b = get_json(f"https://data-api.polymarket.com/trades?market={cond}&limit=500&offset={off}&takerOnly=false")
        trades += b
        if len(b) < 500: break
        time.sleep(0.3)
    out[m] = {"gamma": {k: g.get(k) for k in ("question", "outcomes", "outcomePrices", "closed", "closedTime", "umaResolutionStatus", "gameStartTime", "events")},
              "trades": trades, "t0": t0}
    # when did each outcome first trade at >=0.999 / band trades after t0
    if t0:
        widx = r["samples"][-1][5]
        wname = outs[widx]
        aft = [t for t in trades if t["timestamp"] >= t0 - 1800]
        aft.sort(key=lambda t: t["timestamp"])
        print("   trades n", len(trades), "since t0-30min", len(aft))
        last = None
        for t in aft:
            p = t["price"] if t["outcome"] == wname else round(1 - t["price"], 3)
            key = (round(p, 2))
            if last is None or abs(p - last) >= 0.03 or (p >= 0.99 and last < 0.99):
                print(f"     {round(t['timestamp']-t0):>6}s winner-equiv {p:.3f} {t['side']} {t['outcome']} {t['size']}")
                last = p
        band = [t for t in aft if t["outcome"] == wname and t["timestamp"] >= t0 and 0.96 <= t["price"] <= 0.995 and t["side"] == "BUY"]
        print("   band BUYs on watched side after t0:", [(round(t["timestamp"]-t0), t["price"], t["size"]) for t in band][:10])
    time.sleep(0.3)
json.dump(out, open("/home/user/polysweeper-v1/lab/data/raw/endwindow_band_verify.json", "w"))
