"""List finished US-sports events (all families of each game) from Gamma since a cutoff, saved to lab/data/raw/usports_events.json.

  python3 lab/usports_events.py [days=15]
series ids: MLB 3, NFL 12185, CFB 12756, NHL 10346, NBA 10345, WNBA 10105
"""
import json, re, sys, time, urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
from polysweeper.collector import get_json, GAMMA, parse_ts  # noqa: E402

SERIES = {"MLB": 3, "NFL": 12185, "CFB": 12756, "NHL": 10346, "NBA": 10345, "WNBA": 10105}
OUT = ROOT / "lab/data/raw/usports_events.json"


def game_key(slug):
    m = re.match(r"^(.*?\d{4}-\d{2}-\d{2})", slug or "")
    return m.group(1) if m else slug


def main(days):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).timestamp()
    out = []
    for sport, sid in SERIES.items():
        # 2026-10-08: Gamma refuses offsets above ~2,500 ("use /events/keyset"), so page with the cursor instead
        cur, n = "", 0
        while True:
            url = f"{GAMMA}/events/keyset?series_id={sid}&closed=true&limit=100&order=startDate&ascending=false"
            if cur:
                url += "&after_cursor=" + urllib.parse.quote(cur)
            resp = get_json(url)
            page = resp.get("events") if isinstance(resp, dict) else None
            if not isinstance(page, list) or not page:
                break
            stop = False
            for e in page:
                st = parse_ts(e["startTime"]) if e.get("startTime") else None
                if st is not None and st < cutoff:
                    stop = True
                    continue
                out.append({"sport": sport, "id": e["id"], "slug": e["slug"], "game": game_key(e["slug"]), "start": st,
                            "finished": parse_ts(e["finishedTimestamp"]) if e.get("finishedTimestamp") else None,
                            "closed": parse_ts(e["closedTime"]) if e.get("closedTime") else None, "volume": e.get("volume"),
                            "gameId": e.get("gameId"), "score": e.get("score"),
                            "markets": [{"cid": m["conditionId"], "type": m.get("sportsMarketType"), "q": m.get("question"),
                                         "final": m.get("outcomePrices"), "outcomes": m.get("outcomes")} for m in e.get("markets", [])]})
                n += 1
            cur = resp.get("next_cursor") or ""
            if stop or len(page) < 100 or not cur:
                break
            time.sleep(0.2)
        print(sport, "events", n)
    OUT.write_text(json.dumps(out))
    print("saved", len(out), "events")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 15)
