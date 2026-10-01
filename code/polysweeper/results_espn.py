"""Football results from ESPN's public scoreboard feed (no key; unofficial, may change).

Gives: kickoff time, full-time status, score, winner, stoppage clock (e.g. "90'+5'").
Cached per league+date in data/results/espn/ so repeated runs don't re-download.
"""
from __future__ import annotations

import json
import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .collector import get_json

BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/{code}/scoreboard?dates={ymd}"
LEAGUES = {"epl": "eng.1", "lal": "esp.1", "bun": "ger.1", "sea": "ita.1", "fl1": "fra.1",
           "ucl": "uefa.champions", "uel": "uefa.europa", "por": "por.1", "ere": "ned.1"}
CACHE = Path("data/results/espn")


def scoreboard(league: str, day: datetime):
    code = LEAGUES[league]
    ymd = day.strftime("%Y%m%d")
    path = CACHE / f"{league}_{ymd}.json"
    if path.exists():
        return json.loads(path.read_text())
    data = get_json(BASE.format(code=code, ymd=ymd))
    time.sleep(0.3)
    results = []
    for e in (data or {}).get("events", []):
        try:
            comp = e["competitions"][0]
            st = e["status"]
            sides = {c["homeAway"]: c for c in comp["competitors"]}
            home, away = sides["home"], sides["away"]
        except (KeyError, IndexError):
            continue
        hs, as_ = home.get("score"), away.get("score")
        results.append({
            "kickoff": e.get("date"), "status": st["type"].get("name"), "completed": st["type"].get("completed"),
            "clock": st.get("displayClock"), "home": home["team"]["displayName"], "away": away["team"]["displayName"],
            "home_score": int(hs) if hs not in (None, "") else None, "away_score": int(as_) if as_ not in (None, "") else None,
        })
    if data is not None:
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(results))
    return results


def outcome(r):
    """'home', 'away', 'draw', or None if not a normal full-time result."""
    # Polymarket football markets settle on the 90-minute (regulation) result.
    # After extra time / penalties the feed shows the final score, not the 90-minute one: skip those.
    if not r.get("completed") or r.get("status") not in ("STATUS_FULL_TIME", "STATUS_FINAL"):
        return None
    if r["home_score"] is None or r["away_score"] is None:
        return None
    if r["home_score"] > r["away_score"]:
        return "home"
    if r["away_score"] > r["home_score"]:
        return "away"
    return "draw"


def estimated_end(r):
    """Kickoff + 45 + 15 (half time) + 45 + 2 (typical first-half stoppage) + second-half stoppage from the clock.
    Rough: +/- several minutes. Extra time/penalties are not handled (those matches are flagged by status)."""
    try:
        k = datetime.fromisoformat(r["kickoff"].replace("Z", "+00:00"))
    except (KeyError, ValueError, AttributeError):
        return None
    m = re.search(r"\+(\d+)", r.get("clock") or "")
    extra = int(m.group(1)) if m else 4
    return k + timedelta(minutes=45 + 15 + 45 + 2 + extra)


STOP = {"fc", "cf", "afc", "sc", "ac", "as", "ss", "ssc", "us", "rc", "rcd", "cd", "ud", "sv", "vfb", "vfl", "tsg",
        "fk", "sk", "bk", "if", "club", "de", "del", "la", "le", "calcio", "1909", "1899", "1846", "1900", "1904"}


def tokens(name: str):
    n = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    words = re.findall(r"[a-z0-9]+", n)
    return [w for w in words if w not in STOP] or words


def same_club(a: str, b: str) -> bool:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return False
    ja, jb = "".join(ta), "".join(tb)
    if ja == jb or (len(ja) >= 5 and len(jb) >= 5 and (ja in jb or jb in ja)):
        return True
    sa, sb = set(ta), set(tb)
    common = sa & sb
    return bool(common) and len(common) >= min(len(sa), len(sb)) and max(len(w) for w in common) >= 4
