"""MLB: official final-out time (MLB Stats API) vs Polymarket's `finished` stamp, and the ask-hits in between (public tape, all wallets).

  python3 lab/mlb_official_end.py
Writes lab/results/<date>-mlb-official-end.json
"""
import collections, json, re, statistics, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
from polysweeper.collector import get_json  # noqa: E402

MLB = "https://statsapi.mlb.com/api"
ev = [e for e in json.loads((ROOT / "lab/data/raw/usports_events.json").read_text()) if e["sport"] == "MLB" and e["slug"] == e["game"] and e.get("finished")]
sched = {}


def day_games(date):
    if date not in sched:
        s = get_json(f"{MLB}/v1/schedule?sportId=1&date={date}&hydrate=team") or {"dates": []}
        sched[date] = [(g["gamePk"], g["teams"]["away"]["team"].get("abbreviation", "").lower(), g["teams"]["home"]["team"].get("abbreviation", "").lower(), g["gameDate"])
                       for d in s["dates"] for g in d["games"]]
    return sched[date]


def official_end(e):
    m = re.match(r"^mlb-([a-z]+)-([a-z]+)-(\d{4}-\d{2}-\d{2})", e["slug"])
    if not m:
        return None
    away, home, date = m.groups()
    cands = [g for g in day_games(date) if g[1] == away and g[2] == home]
    if not cands:
        return None
    # doubleheaders: pick the game whose scheduled start is closest to the event start
    pk = min(cands, key=lambda g: abs(datetime.fromisoformat(g[3].replace("Z", "+00:00")).timestamp() - (e["start"] or 0)))[0]
    f = get_json(f"{MLB}/v1.1/game/{pk}/feed/live") or {}
    pl = [p for p in f.get("liveData", {}).get("plays", {}).get("allPlays", []) if p["about"].get("endTime")]
    if not pl or f.get("gameData", {}).get("status", {}).get("detailedState") not in ("Final", "Game Over", "Completed Early"):
        return None
    last = max(datetime.fromisoformat(p["about"]["endTime"].replace("Z", "+00:00")).timestamp() for p in pl)
    return {"pk": pk, "end": last, "innings": len(f["liveData"]["linescore"]["innings"])}


with ThreadPoolExecutor(max_workers=4) as pool:
    res = list(pool.map(official_end, ev))
ok = [(e, r) for e, r in zip(ev, res) if r]
print("MLB games with finished stamp:", len(ev), " matched to the official feed:", len(ok))
lag = sorted(e["finished"] - r["end"] for e, r in ok)
print("Polymarket stamp minus official last play end (s): median", statistics.median(lag), "p10", lag[len(lag) // 10], "p90", lag[9 * len(lag) // 10], "min", lag[0], "max", lag[-1])

# tape: ask-hits on the winner between the official end and a window after it
rows = []
for e, r in ok:
    f = ROOT / f"lab/data/raw/usports_tape/{e['id']}.json"
    if not f.exists():
        continue
    d = json.loads(f.read_text())
    fm = {}
    for m in e["markets"]:
        try:
            fm[m["cid"]] = ([float(x) for x in json.loads(m["final"])], m["type"])
        except (TypeError, ValueError):
            pass
    for t in d["trades"]:
        if t["conditionId"] not in fm:
            continue
        px, typ = fm[t["conditionId"]]
        if sorted(px) != [0.0, 1.0]:
            continue
        rows.append({"game": e["game"], "day": time.strftime("%m-%d", time.gmtime(r["end"])), "dt": t["timestamp"] - r["end"], "side": t["side"], "p": float(t["price"]),
                     "size": float(t["size"]), "wallet": t["proxyWallet"], "type": typ, "winner": px[t["outcomeIndex"]] == 1.0, "cid": t["conditionId"]})
G = len({r["game"] for r in rows})
print("games in tape:", G)
WIN = [(-120, 0, "-120..0s"), (0, 10, "0-10s"), (10, 30, "10-30s"), (30, 60, "30-60s"), (60, 120, "1-2min"), (120, 300, "2-5min"), (300, 1800, "5-30min")]
for label, lo, hi in (("0.96-0.995", 0.96, 0.995), ("0.99-0.995", 0.99, 0.995), ("0.995-0.9995 (late band)", 0.995, 0.9995)):
    print(f"\nASK-HITS on the WINNER, price {label} (by seconds from the OFFICIAL final out):")
    for a, b, name in WIN:
        rs = [r for r in rows if r["side"] == "BUY" and r["winner"] and lo <= r["p"] < hi and a <= r["dt"] < b]
        print(f"   {name:10} fills {len(rs):4} shares {sum(r['size'] for r in rs):8.0f} games {len({r['game'] for r in rs}):3}/{G}  markets {len({(r['game'], r['cid']) for r in rs}):3}  median size {statistics.median([r['size'] for r in rs]) if rs else '-'}")
print("\nSELL-side (resting bid fills) at 0.96-0.995 by window:")
for a, b, name in WIN:
    rs = [r for r in rows if r["side"] == "SELL" and r["winner"] and 0.96 <= r["p"] < 0.995 and a <= r["dt"] < b]
    print(f"   {name:10} fills {len(rs):4} shares {sum(r['size'] for r in rs):8.0f} games {len({r['game'] for r in rs}):3}")
# who buys in -120..60 at 0.96-0.995, and by market type
sel = [r for r in rows if r["side"] == "BUY" and r["winner"] and 0.96 <= r["p"] < 0.995 and -120 <= r["dt"] < 120]
print("\nask-hits -120..+120 s, 0.96-0.995: fills", len(sel), "shares", round(sum(r["size"] for r in sel)), "games", len({r["game"] for r in sel}), "per day", round(len(sel) / len({r["day"] for r in rows}), 1))
print(" by type:", collections.Counter(r["type"] for r in sel).most_common(6))
print(" top wallets:", [(w[:8], n, round(sum(r["size"] for r in sel if r["wallet"] == w))) for w, n in collections.Counter(r["wallet"] for r in sel).most_common(6)])
print(" losers bought in the same window (mirror/errors):", len([r for r in rows if r["side"] == "BUY" and not r["winner"] and 0.96 <= r["p"] < 0.995 and -120 <= r["dt"] < 120]))
out = ROOT / "lab/results" / f"{time.strftime('%Y-%m-%d')}-mlb-official-end.json"
out.write_text(json.dumps({"games": len(ok), "lag_median_s": statistics.median(lag), "lag_p10": lag[len(lag) // 10], "lag_p90": lag[9 * len(lag) // 10]}, indent=1))
