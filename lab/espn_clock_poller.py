"""ESPN game-clock poller for US sports (read-only, public ESPN scoreboard, no key, no orders).

Why: the row-4 test (lab/queue_late.py) knows Polymarket's period and score but NOT the game clock, so a live rule such as
"last period and 60 seconds or less on the clock" cannot be checked against the laptop's pretend fills. This script writes the
clock, period, score and ball/outs state of every live US game every few seconds, so the rule can be replayed on queue_late's fills
afterwards (join by sport + start time + final score, as lab/row4_history.py does).

  python3 lab/espn_clock_poller.py [hours=72] [interval_s=6]     (stop with Ctrl-C; Windows: py lab\\espn_clock_poller.py)
Output (local, git-ignored): lab/data/raw/espn_clock/<utc date>.jsonl, one line per live game per poll:
  {"t": unix, "sp": "NHL", "id": espn event id, "start": unix, "a": away abbr, "h": home abbr, "as": away score, "hs": home score,
   "p": period, "c": clock seconds left in the period (null for MLB), "d": detail text, "st": "in"|"post", "poss": team id with the ball (football),
   "dn": down, "dist": distance, "outs": outs (MLB), "top": 1 if top of the inning (MLB)}
Politeness: one request per sport per poll (CFB twice: FBS and FCS groups), ~7 requests every 6 s while games are live, otherwise one
slow check a minute. Standard library only.
"""
import json, sys, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
from polysweeper.collector import get_json  # noqa: E402

BASE = "https://site.api.espn.com/apis/site/v2/sports"
FEEDS = [("MLB", "baseball/mlb", ""), ("NHL", "hockey/nhl", ""), ("NFL", "football/nfl", ""), ("CFB", "football/college-football", "&groups=80"),
         ("CFB", "football/college-football", "&groups=81"), ("NBA", "basketball/nba", ""), ("WNBA", "basketball/wnba", "")]
OUT = ROOT / "lab/data/raw/espn_clock"


def clock_s(v):
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def rows_for(sport, board, now):
    out = []
    for e in board.get("events", []):
        st = (e.get("status") or {}).get("type") or {}
        state = st.get("state")
        if state not in ("in", "post"):
            continue
        comp = e["competitions"][0]
        cs = {c["homeAway"]: c for c in comp["competitors"]}
        try:
            start = int(datetime.fromisoformat(e["date"].replace("Z", "+00:00")).timestamp())
        except Exception:  # noqa: BLE001
            start = None
        sit = comp.get("situation") or {}
        r = {"t": int(now), "sp": sport, "id": e["id"], "start": start,
             "a": cs["away"]["team"].get("abbreviation"), "h": cs["home"]["team"].get("abbreviation"),
             "as": cs["away"].get("score"), "hs": cs["home"].get("score"),
             "p": (e.get("status") or {}).get("period"), "c": clock_s((e.get("status") or {}).get("clock")),
             "d": st.get("detail"), "st": state}
        if sport in ("NFL", "CFB"):
            r.update(poss=(sit.get("possession")), dn=sit.get("down"), dist=sit.get("distance"))
        if sport == "MLB":
            r.update(outs=sit.get("outs"), top=1 if "top" in (st.get("detail") or "").lower() else 0)
        out.append(r)
    return out


def main(hours=72.0, interval=6.0):
    OUT.mkdir(parents=True, exist_ok=True)
    end = time.time() + hours * 3600
    last = {}
    live_seen = 0.0
    while time.time() < end:
        now = time.time()
        wrote = 0
        any_live = False
        for sport, path, extra in FEEDS:
            try:
                board = get_json(f"{BASE}/{path}/scoreboard?limit=400{extra}") or {}
            except Exception as exc:  # noqa: BLE001
                print("poll error", sport, repr(exc)[:100], flush=True)
                continue
            for r in rows_for(sport, board, now):
                any_live = any_live or r["st"] == "in"
                key = (r["sp"], r["id"])
                sig = (r["as"], r["hs"], r["p"], r["c"], r["st"], r.get("outs"), r.get("top"), r.get("poss"), r.get("dn"))
                if last.get(key) == sig:
                    continue
                last[key] = sig
                with open(OUT / f"{datetime.now(timezone.utc):%Y-%m-%d}.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps(r) + "\n")
                wrote += 1
        if any_live:
            live_seen = now
        # slow down when nothing has been live for 15 minutes
        wait = interval if now - live_seen < 900 else 60.0
        time.sleep(max(1.0, wait - (time.time() - now)))


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 72.0, float(sys.argv[2]) if len(sys.argv) > 2 else 6.0)
