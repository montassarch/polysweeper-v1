"""Second opinion on live match results, for shadow mode.

Football (9 leagues): ESPN scoreboard.  Dota 2: OpenDota.  Other leagues: none yet.
Returns which outcome token is the CONFIRMED winner, or None with a reason.
Never guesses: unclear name matches, extra time, incomplete series => None.
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timezone

from . import results_espn as espn
from .collector import get_json, parse_ts
from .football_check import DRAW_Q, WIN_Q, find_match
from .results_opendota import URL as OPENDOTA_URL, build_series, same_team

DOTA_TITLE = re.compile(r"^Dota 2:\s*(.+?)\s+vs\.?\s+(.+?)\s*\(BO\d\)")


class Confirmer:
    def __init__(self, ttl: float = 60):
        self.ttl = ttl
        self._espn = {}
        self._dota = (0.0, [])

    # cached fetchers (refresh at most once per ttl seconds)
    def _board(self, league, day):
        key = (league, day.strftime("%Y%m%d"))
        t, data = self._espn.get(key, (0.0, None))
        if data is None or time.time() - t > self.ttl:
            data = espn.scoreboard(league, day, fresh=True)
            self._espn[key] = (time.time(), data)
        return data

    def _dota_series(self):
        t, series = self._dota
        if time.time() - t > self.ttl:
            series = build_series(get_json(OPENDOTA_URL) or [])
            self._dota = (time.time(), series)
        return series

    def winner_index(self, league, event, market, outcomes):
        if league in espn.LEAGUES:
            return self.football(league, event, market, outcomes)
        if league == "dota2":
            return self.dota(event, outcomes)
        return None, "no results source for this league yet"

    def football(self, league, event, market, outcomes, board=None):
        q = market.get("question") or ""
        kick = parse_ts(market.get("gameStartTime")) or parse_ts(event.get("startTime"))
        mw, md = WIN_Q.match(q), DRAW_Q.match(q)
        if not kick or not (mw or md):
            return None, "question format not handled"
        teams = [mw.group(1)] if mw else [md.group(1), md.group(2)]
        r = find_match(league, kick, teams, board=board or self._board)
        if not r:
            return None, "no unique ESPN match"
        res = espn.outcome(r)
        if res is None:
            return None, f"ESPN not a normal full-time result ({r.get('status')})"
        if mw:
            is_home, is_away = espn.same_club(teams[0], r["home"]), espn.same_club(teams[0], r["away"])
            if is_home == is_away:
                return None, "team name fits both sides"
            yes_wins = (res == "home") if is_home else (res == "away")
        else:
            yes_wins = res == "draw"
        names = [o.lower() for o in outcomes]
        if "yes" not in names or "no" not in names:
            return None, "outcomes are not Yes/No"
        return names.index("yes" if yes_wins else "no"), f"ESPN {r['home']} {r['home_score']}-{r['away_score']} {r['away']}"

    def dota(self, event, outcomes, series=None):
        m = DOTA_TITLE.match(event.get("title") or "")
        start = parse_ts(event.get("startTime"))
        if not m or not start:
            return None, "title format not handled"
        a, b = m.group(1), m.group(2)
        found = [s for s in (series if series is not None else self._dota_series())
                 if abs(s["start"] - start) <= 6 * 3600 and
                 ((same_team(a, s["teams"][0]) and same_team(b, s["teams"][1])) or
                  (same_team(a, s["teams"][1]) and same_team(b, s["teams"][0])))]
        if len(found) != 1:
            return None, "no complete OpenDota series yet" if not found else "ambiguous series"
        w = found[0]["winner"]
        idx = [i for i, o in enumerate(outcomes) if same_team(o, w)]
        if len(idx) != 1:
            return None, "winner name does not map to exactly one outcome"
        return idx[0], f"OpenDota series winner {w}"
