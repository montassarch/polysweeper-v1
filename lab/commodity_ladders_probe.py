"""Quick probe (2026-10-08): do Pyth-settled commodity / FX ladders (gold, silver, WTI, natural gas, DXY, FX pairs) offer
more cheap safe fills than the stock ladders? Counts public BUY trades at 0.98-0.995 in the last 90 minutes before each
event's end and how many of them lost (no price model: pure outcome counts), plus shares and pool, per family.
  python3 lab/commodity_ladders_probe.py 2026-09-08 2026-10-09
Raw: lab/data/raw/commodity/ ; result: lab/results/2026-10-08-commodity-probe.json"""
import collections, json, re, statistics, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
from polysweeper.collector import get_json, GAMMA, parse_ts  # noqa: E402
DATA = "https://data-api.polymarket.com"
RAW = ROOT / "lab/data/raw/commodity"; RAW.mkdir(parents=True, exist_ok=True)
d0, d1 = sys.argv[1], sys.argv[2]
evs, off = [], 0
while True:
    page = get_json(f"{GAMMA}/events?tag_slug=pyth-finance&closed=true&end_date_min={d0}T00:00:00Z&end_date_max={d1}T00:00:00Z&limit=100&offset={off}&order=endDate&ascending=false") or []
    evs += page
    if len(page) < 100: break
    off += 100
def fam(e):
    tags = {t["slug"] for t in e.get("tags", [])}
    if "stocks" in tags: return None
    s = e["slug"]
    kind = "hit_week" if "-hit-week-of-" in s else "hit_month" if "hit-in-" in s else "closes_above" if "closes-above" in s or "close-above" in s else "updown" if "up-or-down" in s else "other"
    grp = "commodities" if "commodities" in tags else "fx" if ("forex" in tags or "fx" in tags) else "other"
    return grp + ":" + kind
evs = [(e, fam(e)) for e in evs]
evs = [(e, f) for e, f in evs if f and not f.endswith("updown") and not f.endswith("other")]
print("events", len(evs), collections.Counter(f for _, f in evs))
def pull(ef):
    e, f = ef
    rows, off = [], 0
    while off <= 15000:
        try:
            pg = get_json(f"{DATA}/trades?eventId={e['id']}&limit=500&offset={off}")
        except Exception:      # the Data API refuses deep offsets (HTTP 400): keep what we have
            break
        if not isinstance(pg, list) or not pg: break
        rows += pg
        if len(pg) < 500: break
        off += 500
    return e, f, rows
res = collections.defaultdict(lambda: dict(trades=0, shares=0.0, losers=0, loser_shares=0.0, gain=0.0, loss=0.0, events=0, mk=set()))
with ThreadPoolExecutor(4) as pool:
    for e, f, rows in pool.map(pull, evs):
        end = parse_ts(e["endDate"])
        fin = {}
        for m in e["markets"]:
            try: px = [float(x) for x in json.loads(m["outcomePrices"])]
            except Exception: continue
            if sorted(px) == [0.0, 1.0]: fin[m["conditionId"]] = px
        r = res[f]; r["events"] += 1
        for t in rows:
            if t["side"] != "BUY" or not (0.98 <= t["price"] <= 0.995) or not (end - 5400 <= t["timestamp"] <= end): continue
            px = fin.get(t["conditionId"])
            if px is None: continue
            won = px[t["outcomeIndex"]] == 1.0
            r["trades"] += 1; r["shares"] += t["size"]; r["mk"].add(t["conditionId"])
            if won: r["gain"] += (1 - t["price"]) * t["size"]
            else: r["losers"] += 1; r["loser_shares"] += t["size"]; r["loss"] += t["price"] * t["size"]
out = {f: dict(events=v["events"], trades=v["trades"], markets=len(v["mk"]), shares=round(v["shares"]), losers=v["losers"], loser_shares=round(v["loser_shares"]),
               gain_usd=round(v["gain"], 1), loss_usd=round(v["loss"], 1)) for f, v in res.items()}
print(json.dumps(out, indent=1))
(ROOT / "lab/results/2026-10-08-commodity-probe.json").write_text(json.dumps(out, indent=1))
