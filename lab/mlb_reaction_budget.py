"""MLB: how much would a bot get if it learns of the final out X seconds after MLB's own last-play end time?
Upper bound = ask-hits on the winner (all wallets, public tape) that happened at least X s after the official end.
Re-uses the matching in mlb_official_end.py (imports it would re-run it, so this repeats the small part it needs).
"""
import json, re, statistics, sys, time, collections
from datetime import datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
from polysweeper.collector import get_json  # noqa: E402

MLB = "https://statsapi.mlb.com/api"
cache_p = ROOT / "lab/data/raw/mlb_official_end_cache.json"
cache = json.loads(cache_p.read_text()) if cache_p.exists() else {}
ev = [e for e in json.loads((ROOT / "lab/data/raw/usports_events.json").read_text()) if e["sport"] == "MLB" and e["slug"] == e["game"] and e.get("finished")]
sched = {}


def day_games(date):
    if date not in sched:
        s = get_json(f"{MLB}/v1/schedule?sportId=1&date={date}&hydrate=team") or {"dates": []}
        sched[date] = [(g["gamePk"], g["teams"]["away"]["team"].get("abbreviation", "").lower(), g["teams"]["home"]["team"].get("abbreviation", "").lower(), g["gameDate"], g.get("gameType"))
                       for d in s["dates"] for g in d["games"]]
    return sched[date]


def official(e):
    if e["slug"] in cache:
        return cache[e["slug"]]
    m = re.match(r"^mlb-([a-z]+)-([a-z]+)-(\d{4}-\d{2}-\d{2})", e["slug"])
    res = None
    if m:
        away, home, date = m.groups()
        c = [g for g in day_games(date) if g[1] == away and g[2] == home]
        if c:
            g = min(c, key=lambda g: abs(datetime.fromisoformat(g[3].replace("Z", "+00:00")).timestamp() - (e["start"] or 0)))
            f = get_json(f"{MLB}/v1.1/game/{g[0]}/feed/live") or {}
            pl = [p for p in f.get("liveData", {}).get("plays", {}).get("allPlays", []) if p["about"].get("endTime")]
            if pl and f.get("gameData", {}).get("status", {}).get("detailedState") in ("Final", "Game Over", "Completed Early"):
                res = {"end": max(datetime.fromisoformat(p["about"]["endTime"].replace("Z", "+00:00")).timestamp() for p in pl), "type": g[4], "pk": g[0]}
    cache[e["slug"]] = res
    return res


rows, games = [], {}
for e in ev:
    r = official(e)
    if not r:
        continue
    f = ROOT / f"lab/data/raw/usports_tape/{e['id']}.json"
    if not f.exists():
        continue
    games[e["game"]] = (time.strftime("%m-%d", time.gmtime(r["end"])), r["type"], e["finished"] - r["end"])
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
        if sorted(px) != [0.0, 1.0] or t["side"] != "BUY" or px[t["outcomeIndex"]] != 1.0:
            continue
        rows.append({"game": e["game"], "dt": t["timestamp"] - r["end"], "p": float(t["price"]), "size": float(t["size"]), "type": typ, "gt": r["type"]})
cache_p.write_text(json.dumps(cache))
print("games", len(games), "game types:", collections.Counter(g[1] for g in games.values()))
days = collections.Counter(g[0] for g in games.values()); print("games per day:", sorted(days.items()))


def fee(p, n=5, rate=0.03):
    return n * rate * p * (1 - p)


RESULT = {}
for gtype, label in (("ALL", "all 90 games"), ("D", "postseason (Division Series)"), ("F", "postseason Wild Card"), ("R", "regular season")):
    gs = {g for g, v in games.items() if gtype == "ALL" or v[1] == gtype}
    if not gs:
        continue
    nd = len({games[g][0] for g in gs})
    print(f"\n=== {label}: {len(gs)} games over {nd} days ===")
    for band, lo, hi in (("0.96-0.995", 0.96, 0.995), ("0.99-0.995", 0.99, 0.995)):
        print(f"  price {band}: reaction time X -> ask-hits at or after X s (upper bound for a bot that sees the final out at X s)")
        for X in (0, 3, 5, 8, 10, 15, 20, 30, 45):
            rs = [r for r in rows if r["game"] in gs and X <= r["dt"] < 1800 and lo <= r["p"] < hi]
            prof = sum(5 * (1 - r["p"]) - fee(r["p"]) for r in rs if r["size"] >= 5)
            RESULT.setdefault(label, {}).setdefault(band, {})[X] = {"games": len(gs), "days": nd, "fills": len(rs), "fills_per_day": round(len(rs) / nd, 1),
                                                                    "games_with_fill": len({r["game"] for r in rs}), "profit_5sh_per_day": round(prof / nd, 2)}
            print(f"     X={X:2d}s: fills {len(rs):4} ({len(rs)/nd:5.1f}/day)  games with a fill {len({r['game'] for r in rs}):3}/{len(gs)}  fills of >=5 sh {sum(1 for r in rs if r['size']>=5):4}  5-share profit if we got every one ~${prof/nd:5.2f}/day")

(ROOT / "lab/results" / f"{time.strftime('%Y-%m-%d')}-mlb-reaction-budget.json").write_text(json.dumps(RESULT, indent=1))
