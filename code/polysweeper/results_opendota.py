"""Dota 2 results from OpenDota (free, no key): exact game start + duration => true end time.

Usage: python -m polysweeper.results_opendota --days 70
Writes data/results/opendota_series.jsonl (one line per series).
Be polite: ~1 request per second.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

from .collector import get_json

URL = "https://api.opendota.com/api/proMatches"


def fetch_games(days: float, max_pages: int = 60):
    cutoff = time.time() - days * 86400
    games, last_id = [], None
    for _ in range(max_pages):
        page = get_json(URL + (f"?less_than_match_id={last_id}" if last_id else "")) or []
        if not page:
            break
        games += page
        last_id = page[-1]["match_id"]
        if page[-1]["start_time"] < cutoff:
            break
        time.sleep(1.0)
    return [g for g in games if g["start_time"] >= cutoff]


def build_series(games):
    """Group games into series; winner = most game wins; end = last game's end."""
    groups = {}
    for g in games:
        key = g.get("series_id") or f"single-{g['match_id']}"
        groups.setdefault(key, []).append(g)
    out = []
    for key, gs in groups.items():
        gs.sort(key=lambda g: g["start_time"])
        wins = {}
        names = {}
        for g in gs:
            r, d = g.get("radiant_name") or "", g.get("dire_name") or ""
            names[r], names[d] = 1, 1
            w = r if g.get("radiant_win") else d
            wins[w] = wins.get(w, 0) + 1
        if len(names) != 2 or "" in names:
            continue
        top = sorted(wins.items(), key=lambda kv: -kv[1])
        if len(top) > 1 and top[0][1] == top[1][1]:
            continue                       # tied series: skip, never guess
        need = {0: 1, 1: 2, 2: 3}.get(gs[0].get("series_type"))
        if need is None or top[0][1] < need:
            continue                       # incomplete series (e.g. 1 game of a best-of-3): skip, never guess
        out.append({"series_id": key, "series_type": gs[0].get("series_type"), "teams": list(names),
                    "winner": top[0][0], "games": len(gs), "wins": wins,
                    "start": gs[0]["start_time"],
                    "end": max(g["start_time"] + g["duration"] for g in gs),
                    "league": gs[0].get("league_name")})
    return out


def norm(name: str) -> str:
    n = re.sub(r"[^a-z0-9]+", "", (name or "").lower())
    for suf in ("esports", "gaming", "team", "club"):
        if n.endswith(suf) and len(n) > len(suf) + 2:
            n = n[: -len(suf)]
        if n.startswith(suf) and len(n) > len(suf) + 2:
            n = n[len(suf):]
    return n


def same_team(a: str, b: str) -> bool:
    x, y = norm(a), norm(b)
    return bool(x and y and (x == y or (len(x) >= 4 and len(y) >= 4 and (x in y or y in x))))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=float, default=70)
    a = ap.parse_args(argv)
    games = fetch_games(a.days)
    series = build_series(games)
    Path("data/results").mkdir(parents=True, exist_ok=True)
    Path("data/results/opendota_series.jsonl").write_text("\n".join(json.dumps(s) for s in series) + "\n")
    print(f"{len(games)} games -> {len(series)} usable series saved to data/results/opendota_series.jsonl")


if __name__ == "__main__":
    main()
