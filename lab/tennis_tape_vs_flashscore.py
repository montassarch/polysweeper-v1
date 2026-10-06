"""Tennis (ATP/WTA incl. challengers listed on Polymarket), last ~7 days: when did the winner's price first reach 0.97 / 0.99 / 0.995 on the public tape,
versus Flashscore's own final stamp (AO) and Polymarket's `finishedTimestamp`.

  python3 lab/tennis_tape_vs_flashscore.py            (needs lab/data/raw/flashscore/sport2_off*.txt from flashscore_fetch.py)
Negative numbers = earlier than the comparison clock.
"""
import collections, datetime, glob, json, re, statistics, sys, time, unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lab")); sys.path.insert(0, str(ROOT / "code"))
from flashscore_fetch import parse  # noqa: E402
from flashscore_ao_lag import same_player  # noqa: E402
from polysweeper.collector import get_json, GAMMA, parse_ts  # noqa: E402

DATA = "https://data-api.polymarket.com"
cutoff = (datetime.datetime.now(timezone.utc) - timedelta(days=7)).timestamp()
fs = {}
for p in sorted(glob.glob(str(ROOT / "lab/data/raw/flashscore/sport2_off*.txt"))):
    for m in parse(Path(p).read_text(encoding="utf8")):
        if m.get("AB") == "3" and m.get("AO", "").isdigit() and m.get("AC") == "3":     # AC=3: finished normally (no walkover/retirement codes)
            fs[m["AA"]] = m
fs = list(fs.values())
print("flashscore finished (normal) tennis matches:", len(fs))

evs = []
for sid in (10365, 10366):
    off = 0
    while True:
        page = get_json(f"{GAMMA}/events?series_id={sid}&closed=true&limit=100&offset={off}&order=startDate&ascending=false")
        if not isinstance(page, list) or not page:
            break
        stop = False
        for e in page:
            st = parse_ts(e["startTime"]) if e.get("startTime") else None
            if st is not None and st < cutoff:
                stop = True; continue
            evs.append(e)
        if stop or len(page) < 100:
            break
        off += 100
print("polymarket tennis events (7d):", len(evs))


def analyse(e):
    ml = [m for m in e.get("markets", []) if m.get("sportsMarketType") == "moneyline"]
    if not ml or not e.get("finishedTimestamp"):
        return None
    m = ml[0]
    try:
        outs = json.loads(m["outcomes"]); px = [float(x) for x in json.loads(m["outcomePrices"])]
    except (KeyError, ValueError, TypeError):
        return None
    if sorted(px) != [0.0, 1.0] or len(outs) != 2:
        return None
    win = px.index(1.0)
    cands = [f for f in fs if abs(int(f["AO"]) - parse_ts(e["finishedTimestamp"])) < 3 * 3600 and
             ((same_player(outs[0], f["AE"]) and same_player(outs[1], f["AF"])) or (same_player(outs[0], f["AF"]) and same_player(outs[1], f["AE"])))]
    if len(cands) != 1:
        return None
    rows, off = [], 0
    while off <= 5000:
        page = get_json(f"{DATA}/trades?market={m['conditionId']}&limit=500&offset={off}")
        if not isinstance(page, list) or not page:
            break
        rows += page
        if len(page) < 500 or min(t["timestamp"] for t in page) < parse_ts(e["finishedTimestamp"]) - 3 * 3600:
            break
        off += 500
    fin = parse_ts(e["finishedTimestamp"]); ao = int(cands[0]["AO"])
    firsts = {}
    for thr in (0.97, 0.99, 0.995):
        ts = [t["timestamp"] for t in rows if t["outcomeIndex"] == win and float(t["price"]) >= thr and t["timestamp"] > fin - 3600]
        firsts[thr] = min(ts) if ts else None
    # also: trades on the winner at < 0.95 after AO (a sign the market had not decided yet)
    late_cheap = sum(1 for t in rows if t["outcomeIndex"] == win and t["timestamp"] > ao and float(t["price"]) < 0.95 and t["side"] == "BUY")
    after = [[t["timestamp"] - ao, float(t["price"]), float(t["size"]), t["side"]] for t in rows
             if t["outcomeIndex"] == win and float(t["price"]) >= 0.96 and ao - 300 <= t["timestamp"] <= ao + 3600]
    return {"title": m["question"][:60], "ao_vs_finished": ao - fin, "fin": fin, "ao": ao, "after": after,
            **{f"first{int(thr*1000)}_vs_ao": (None if v is None else v - ao) for thr, v in firsts.items()},
            **{f"first{int(thr*1000)}_vs_finished": (None if v is None else v - fin) for thr, v in firsts.items()}, "late_cheap_buys_after_ao": late_cheap, "trades": len(rows)}


with ThreadPoolExecutor(max_workers=5) as pool:
    res = [r for r in pool.map(analyse, evs) if r]
print("matched events with tape + Flashscore:", len(res))
for k in ("ao_vs_finished", "first970_vs_ao", "first990_vs_ao", "first995_vs_ao", "first970_vs_finished", "first990_vs_finished", "first995_vs_finished"):
    v = sorted(r[k] for r in res if r.get(k) is not None)
    if v:
        print(f"{k:24} n={len(v):3} median {statistics.median(v):8.1f} p10 {v[len(v)//10]:8.1f} p90 {v[9*len(v)//10]:8.1f}  share<0: {sum(1 for x in v if x < 0)/len(v):.0%}")
print("matches where the winner still traded below 0.95 (BUY) after Flashscore's final stamp:", sum(1 for r in res if r["late_cheap_buys_after_ao"]), "of", len(res))
out = ROOT / "lab/results" / f"{datetime.date.today()}-tennis-tape-vs-flashscore.json"
slim = [{k: v for k, v in r.items() if k != "after"} for r in res]
out.write_text(json.dumps(slim, indent=1))

# supply left after Flashscore's final stamp: taker BUYS of the winner token at 0.96-0.998
print("\nWINNER taker BUYs after Flashscore's final stamp (AO), by window; n matches =", len(res))
for lo, hi, name in ((-300, 0, "300s BEFORE AO"), (0, 10, "0-10s"), (10, 30, "10-30s"), (30, 60, "30-60s"), (60, 300, "1-5min"), (300, 3600, "5-60min")):
    for plo, phi, pname in ((0.96, 0.995, "0.96-0.995"), (0.995, 0.9985, "0.995-0.998")):
        rs = [(r["title"], a) for r in res for a in r["after"] if a[3] == "BUY" and lo <= a[0] < hi and plo <= a[1] < phi]
        games = len({t for t, _ in rs})
        print(f"  {name:15} {pname:12} fills {len(rs):4} shares {sum(a[2] for _, a in rs):8.0f}  matches {games:3}/{len(res)}  fills of >=5 sh {sum(1 for _, a in rs if a[2] >= 5)}")
