"""Fill in the main game event (moneyline/spread/total...) for every game key found by usports_events.py."""
import json, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
from polysweeper.collector import get_json, GAMMA, parse_ts  # noqa: E402

P = ROOT / "lab/data/raw/usports_events.json"
ev = json.loads(P.read_text())
have = {e["slug"] for e in ev}
games = {}
for e in ev:
    games.setdefault(e["game"], e["sport"])
missing = [g for g in games if g not in have]
print("games", len(games), "main events missing", len(missing))


def fetch(g):
    r = get_json(f"{GAMMA}/events?slug={g}")
    if not r:
        return None
    e = r[0]
    return {"sport": games[g], "id": e["id"], "slug": e["slug"], "game": g,
            "start": parse_ts(e["startTime"]) if e.get("startTime") else None,
            "finished": parse_ts(e["finishedTimestamp"]) if e.get("finishedTimestamp") else None,
            "closed": parse_ts(e["closedTime"]) if e.get("closedTime") else None, "volume": e.get("volume"),
            "gameId": e.get("gameId"), "score": e.get("score"), "isclosed": e.get("closed"),
            "markets": [{"cid": m["conditionId"], "type": m.get("sportsMarketType"), "q": m.get("question"),
                         "final": m.get("outcomePrices"), "outcomes": m.get("outcomes")} for m in e.get("markets", [])]}


with ThreadPoolExecutor(max_workers=6) as pool:
    got = [x for x in pool.map(fetch, missing) if x]
print("fetched", len(got), "of", len(missing))
ev += got
P.write_text(json.dumps(ev))
print("events now", len(ev))
