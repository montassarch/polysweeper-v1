"""Check historical Polymarket football markets against ESPN results.

Usage: python -m polysweeper.football_check
Reports: how many markets matched, whether winners agree, and the winner's
price after the (estimated) final whistle. Mid prices; end time is estimated.
"""
from __future__ import annotations

import json
import re
import statistics
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .collector import parse_ts
from .dota_end_test import price_at
from .results_espn import LEAGUES, estimated_end, outcome, same_club, scoreboard

OFFSETS = [0, 2, 5, 10, 15, 30]
LO, HI = 0.96, 0.995
WIN_Q = re.compile(r"^Will (.+?) win on (\d{4}-\d{2}-\d{2})\?$")
DRAW_Q = re.compile(r"^Will (.+?) vs\.? (.+?) end in a draw\?$")


def find_match(league, kickoff_ts, teams):
    k = datetime.fromtimestamp(kickoff_ts, timezone.utc)
    seen = []
    for day in {(k - timedelta(hours=6)).date(), k.date(), (k + timedelta(hours=6)).date()}:
        for r in scoreboard(league, datetime(day.year, day.month, day.day)):
            try:
                rk = datetime.fromisoformat(r["kickoff"].replace("Z", "+00:00"))
            except (KeyError, ValueError):
                continue
            if abs((rk - k).total_seconds()) > 3 * 3600:
                continue
            if all(same_club(t, r["home"]) or same_club(t, r["away"]) for t in teams):
                if r not in seen:
                    seen.append(r)
    return seen[0] if len(seen) == 1 else None


def main():
    stats = Counter()
    rows = []
    for league in LEAGUES:
        path = Path(f"data/real/{league}.jsonl")
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            stats["markets"] += 1
            q = rec.get("question") or ""
            kick = parse_ts(rec.get("game_start")) or parse_ts(rec.get("event_start"))
            mw, md = WIN_Q.match(q), DRAW_Q.match(q)
            if not kick or not (mw or md):
                stats["question format not handled"] += 1
                continue
            teams = [mw.group(1)] if mw else [md.group(1), md.group(2)]
            r = find_match(league, kick, teams)
            if not r:
                stats["no unique ESPN match"] += 1
                continue
            res = outcome(r)
            if res is None:
                stats["ESPN not a normal full-time result"] += 1
                continue
            if mw:
                is_home, is_away = same_club(teams[0], r["home"]), same_club(teams[0], r["away"])
                if is_home == is_away:                 # fits both sides (e.g. PSG vs Paris FC) or neither: never guess
                    stats["team name fits both sides"] += 1
                    continue
                yes_should_win = (res == "home") if is_home else (res == "away")
            else:
                yes_should_win = (res == "draw")
            names = [t["outcome"].lower() for t in rec["tokens"]]
            if "yes" not in names:
                stats["outcome names not Yes/No"] += 1
                continue
            yes = rec["tokens"][names.index("yes")]
            if 0.01 < yes["final_price"] < 0.99:
                stats["Polymarket paid 50/50 or other"] += 1
                continue
            poly_yes_won = yes["final_price"] >= 0.99
            stats["matched"] += 1
            if poly_yes_won != yes_should_win:
                stats["DISAGREE"] += 1
                print("DISAGREE:", league, q, "| ESPN", r["home"], r["home_score"], "-", r["away_score"], r["away"], r["status"])
                continue
            stats["agree"] += 1
            winner_tok = yes if poly_yes_won else rec["tokens"][1 - names.index("yes")]
            end = estimated_end(r)
            if not end:
                continue
            e = end.timestamp()
            h = winner_tok["history"]
            prices = {k: price_at(h, e + k * 60) for k in OFFSETS}
            above = next((t for t, p in h if t >= e and p > HI), None)
            rows.append({"prices": prices, "to_above": (above - e) / 60 if above else None,
                         "closed": ((parse_ts(rec["closed_time"]) or e) - e) / 60})
    print("Football markets vs ESPN results:")
    for k, v in stats.most_common():
        print(f"  {k}: {v}")
    if not rows:
        return
    print(f"\nWinner's price N minutes after the ESTIMATED final whistle (n={len(rows)}, mid prices):")
    print(f"{'min':>5} {'<0.96':>7} {'0.96-0.995':>11} {'>0.995':>8} {'median':>8}")
    for k in OFFSETS:
        ps = [r["prices"][k] for r in rows if r["prices"][k] is not None]
        if ps:
            print(f"{k:>5} {sum(p < LO for p in ps):>7} {sum(LO <= p <= HI for p in ps):>11} {sum(p > HI for p in ps):>8} {statistics.median(ps):>8.3f}")
    ab = [r["to_above"] for r in rows if r["to_above"] is not None]
    if ab:
        print(f"Minutes from estimated end until price > {HI}: median {statistics.median(ab):.1f}")
    cl = [r["closed"] for r in rows]
    print(f"Minutes from estimated end until Polymarket closed/paid: median {statistics.median(cl):.0f}")
    print("\nCaveats: ESPN feed is unofficial; end time estimated (+/- several minutes); mid prices.")


if __name__ == "__main__":
    main()
