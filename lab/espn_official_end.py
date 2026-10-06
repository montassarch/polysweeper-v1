"""NFL / CFB / NHL / WNBA / NBA: official end time (ESPN 'End of Game' play wallclock) vs Polymarket's `finished` stamp,
and ask-hits on the winner (public tape, all wallets) in windows around the official end.

  python3 lab/espn_official_end.py
ESPN's wallclock is when the data entry was made (football: the last snap), so it can sit up to ~30 s before the true final whistle.
"""
import collections, json, statistics, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
from polysweeper.collector import get_json  # noqa: E402

BASE = "https://site.api.espn.com/apis/site/v2/sports"
PATH = {"NFL": "football/nfl", "CFB": "football/college-football", "NHL": "hockey/nhl", "WNBA": "basketball/wnba", "NBA": "basketball/nba"}
ev = [e for e in json.loads((ROOT / "lab/data/raw/usports_events.json").read_text()) if e["sport"] in PATH and e["slug"] == e["game"] and e.get("finished") and e.get("score") and e.get("start")]
cache_p = ROOT / "lab/data/raw/espn_official_end_cache.json"
cache = json.loads(cache_p.read_text()) if cache_p.exists() else {}
_sb = {}


def scoreboard(sport, date):
    k = (sport, date)
    if k not in _sb:
        extra = "&groups=80" if sport == "CFB" else ""
        s = get_json(f"{BASE}/{PATH[sport]}/scoreboard?dates={date}&limit=400{extra}") or {}
        _sb[k] = s.get("events", [])
    return _sb[k]


def end_wallclock(sport, eid):
    s = get_json(f"{BASE}/{PATH[sport]}/summary?event={eid}") or {}
    plays = s.get("plays") or []
    if not plays:
        for d in (s.get("drives", {}).get("previous") or []) + ([s["drives"]["current"]] if s.get("drives", {}).get("current") else []):
            plays += d.get("plays", [])
    wc = [p["wallclock"] for p in plays if p.get("wallclock")]
    eog = [p["wallclock"] for p in plays if p.get("wallclock") and "end" in ((p.get("type") or {}).get("text") or "").lower() and "game" in ((p.get("type") or {}).get("text") or "").lower()]
    pick = (eog or wc or [None])[-1]
    return datetime.fromisoformat(pick.replace("Z", "+00:00")).timestamp() if pick else None


def find(e):
    if e["slug"] in cache:
        return cache[e["slug"]]
    try:
        a, h = [int(x) for x in e["score"].split("-")]
    except ValueError:
        cache[e["slug"]] = None; return None
    d0 = datetime.fromtimestamp(e["start"], timezone.utc)
    res = None
    for dd in (d0, d0 - timedelta(days=1)):
        for g in scoreboard(e["sport"], dd.strftime("%Y%m%d")):
            comp = g["competitions"][0]
            cs = {c["homeAway"]: c for c in comp["competitors"]}
            try:
                sa, sh = int(cs["away"]["score"]), int(cs["home"]["score"])
            except (KeyError, ValueError):
                continue
            gt = datetime.fromisoformat(g["date"].replace("Z", "+00:00")).timestamp()
            if (sa, sh) == (a, h) and abs(gt - e["start"]) < 2700 and g["status"]["type"]["completed"]:
                w = end_wallclock(e["sport"], g["id"])
                if w:
                    res = {"end": w, "espn": g["id"]}
                break
        if res:
            break
    cache[e["slug"]] = res
    return res


with ThreadPoolExecutor(max_workers=4) as pool:
    res = list(pool.map(find, ev))
cache_p.write_text(json.dumps(cache))
ok = [(e, r) for e, r in zip(ev, res) if r]
print("games with stamp and score:", len(ev), "matched to ESPN:", len(ok), dict(collections.Counter(e["sport"] for e, _ in ok)))
for sport in PATH:
    lag = sorted(e["finished"] - r["end"] for e, r in ok if e["sport"] == sport)
    if lag:
        print(f"  {sport:5} n={len(lag):3} Polymarket stamp minus ESPN end (s): median {statistics.median(lag):7.1f}  p10 {lag[len(lag)//10]:7.1f}  p90 {lag[9*len(lag)//10]:7.1f}  min {lag[0]:7.1f} max {lag[-1]:7.1f}")
rows, games = [], {}
for e, r in ok:
    f = ROOT / f"lab/data/raw/usports_tape/{e['id']}.json"
    if not f.exists():
        continue
    games[e["game"]] = (e["sport"], time.strftime("%m-%d", time.gmtime(r["end"])))
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
        if sorted(px) != [0.0, 1.0] or t["side"] != "BUY":
            continue
        rows.append({"game": e["game"], "sport": e["sport"], "dt": t["timestamp"] - r["end"], "p": float(t["price"]), "size": float(t["size"]),
                     "winner": px[t["outcomeIndex"]] == 1.0, "type": typ})
WIN = [(-120, 0, "-120..0s"), (0, 10, "0-10s"), (10, 30, "10-30s"), (30, 60, "30-60s"), (60, 120, "1-2min"), (120, 300, "2-5min"), (300, 1800, "5-30min")]
for sport in PATH:
    gs = [g for g, v in games.items() if v[0] == sport]
    if not gs:
        continue
    nd = len({games[g][1] for g in gs})
    print(f"\n#### {sport}: {len(gs)} games over {nd} days. ASK-HITS on the WINNER at 0.96-0.995 by seconds from the ESPN end:")
    for a, b, name in WIN:
        rs = [r for r in rows if r["sport"] == sport and r["winner"] and 0.96 <= r["p"] < 0.995 and a <= r["dt"] < b]
        r2 = [r for r in rs if r["p"] >= 0.99]
        print(f"   {name:9} fills {len(rs):4} shares {sum(r['size'] for r in rs):8.0f} games {len({r['game'] for r in rs}):3}/{len(gs)}  (at 0.99+: {len(r2)})  median size {statistics.median([r['size'] for r in rs]) if rs else '-'}")
    lost = [r for r in rows if r["sport"] == sport and not r["winner"] and 0.96 <= r["p"] < 0.995 and r["dt"] >= 15]
    print("   loser-token buys at 0.96-0.995 >=15 s after the ESPN end:", len(lost))

print("\n\n=== REACTION BUDGET (ESPN end): ask-hits on the winner at 0.99-0.995 and 0.96-0.995 at or after X seconds, per game and per game-day ===")
def fee(p, n=5, rate=0.03):
    return n * rate * p * (1 - p)
RESULT = {}
for sport in PATH:
    gs = [g for g, v in games.items() if v[0] == sport]
    if not gs:
        continue
    nd = len({games[g][1] for g in gs})
    print(f"\n{sport}: {len(gs)} games, {nd} game days, {len(gs)/nd:.1f} games/day in this sample")
    for X in (0, 5, 10, 20, 30, 60):
        for band, lo, hi in (("0.96-0.995", 0.96, 0.995), ("0.99-0.995", 0.99, 0.995)):
            rs = [r for r in rows if r["sport"] == sport and r["winner"] and X <= r["dt"] < 1800 and lo <= r["p"] < hi and r["size"] >= 5]
            prof = sum(5 * (1 - r["p"]) - fee(r["p"]) for r in rs)
            RESULT.setdefault(sport, {}).setdefault(band, {})[X] = {"games": len(gs), "days": nd, "fills": len(rs), "fills_per_game": round(len(rs) / len(gs), 2),
                                                                    "games_with_fill": len({r["game"] for r in rs}), "profit_5sh_per_day": round(prof / nd, 2)}
            print(f"   X={X:2d}s {band}: fills(>=5sh) {len(rs):4} = {len(rs)/len(gs):4.2f}/game, {len(rs)/nd:5.1f}/day; games with a fill {len({r['game'] for r in rs}):3}/{len(gs)}; 5-share profit if we got every one ${prof/nd:5.2f}/day")

lagsum = {}
for sport in PATH:
    lag = sorted(e["finished"] - r["end"] for e, r in ok if e["sport"] == sport)
    if lag:
        lagsum[sport] = {"n": len(lag), "median_s": statistics.median(lag), "p10": lag[len(lag) // 10], "p90": lag[9 * len(lag) // 10]}
(ROOT / "lab/results" / f"{time.strftime('%Y-%m-%d')}-espn-official-end.json").write_text(json.dumps({"stamp_minus_official_end": lagsum, "reaction_budget": RESULT}, indent=1))
