"""Dota 2 test of "buy AFTER the verified match end", using true end times from OpenDota.

Usage: python -m polysweeper.dota_end_test
Needs: data/real/dota2.jsonl (collector) and data/results/opendota_series.jsonl.
Prices are Polymarket MID prices (optimistic); no depth data.
"""
from __future__ import annotations

import bisect
import json
import re
import statistics
from pathlib import Path

from .collector import parse_ts
from .results_opendota import same_team

OFFSETS = [0, 1, 2, 3, 5, 10, 15, 30]          # minutes after the true end
LO, HI = 0.96, 0.995


def price_at(hist, t):
    """Last known price at or before time t (None if no data yet)."""
    times = [p[0] for p in hist]
    i = bisect.bisect_right(times, t) - 1
    return hist[i][1] if i >= 0 else None


def match_series(title, game_start, series):
    m = re.match(r"^Dota 2:\s*(.+?)\s+vs\.?\s+(.+?)\s*\(BO\d\)", title or "")
    if not m or not game_start:
        return None, None
    a, b = m.group(1), m.group(2)
    best = []
    for s in series:
        if abs(s["start"] - game_start) > 6 * 3600:
            continue
        t1, t2 = s["teams"]
        if (same_team(a, t1) and same_team(b, t2)) or (same_team(a, t2) and same_team(b, t1)):
            best.append(s)
    if len(best) != 1:
        return None, ("ambiguous" if best else "no match")
    return best[0], None


def main():
    series = [json.loads(l) for l in Path("data/results/opendota_series.jsonl").read_text().splitlines() if l.strip()]
    recs = [json.loads(l) for l in Path("data/real/dota2.jsonl").read_text().splitlines() if l.strip()]
    stats = {"markets": len(recs), "matched": 0, "no_match": 0, "ambiguous": 0, "agree": 0, "disagree": 0}
    rows = []
    for r in recs:
        gs = parse_ts(r["game_start"]) or parse_ts(r["event_start"])
        s, why = match_series(r["event_title"], gs, series)
        if not s:
            stats["ambiguous" if why == "ambiguous" else "no_match"] += 1
            continue
        stats["matched"] += 1
        poly_winner = next((t for t in r["tokens"] if t["final_price"] >= 0.99), None)
        if not poly_winner:
            continue
        if same_team(poly_winner["outcome"], s["winner"]):
            stats["agree"] += 1
        else:
            stats["disagree"] += 1
            continue
        closed = parse_ts(r["closed_time"])
        end = s["end"]
        row = {"title": r["event_title"], "end": end, "closed_min": (closed - end) / 60 if closed else None, "prices": {}}
        for k in OFFSETS:
            row["prices"][k] = price_at(poly_winner["history"], end + k * 60)
        # first time at/after end that price is above HI
        above = next((t for t, p in poly_winner["history"] if t >= end and p > HI), None)
        row["to_above_min"] = (above - end) / 60 if above else None
        # time spent inside the window after end
        row["in_window_min"] = sum(
            (min(poly_winner["history"][i + 1][0], above or 10**12) - max(poly_winner["history"][i][0], end)) / 60
            for i in range(len(poly_winner["history"]) - 1)
            if LO <= poly_winner["history"][i][1] <= HI and poly_winner["history"][i + 1][0] > end
            and (above is None or poly_winner["history"][i][0] < above))
        rows.append(row)
    print("Matching Polymarket Dota 2 markets to OpenDota series:")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    n = len(rows)
    print(f"\nUsable matches (winner agrees on both sources): {n}\n")
    if not n:
        return
    print("Price of the winner at N minutes after the TRUE END (mid price):")
    print(f"{'min':>5} {'n':>4} {'<0.96':>6} {'0.96-0.995':>11} {'>0.995':>7} {'median':>8}")
    for k in OFFSETS:
        ps = [r["prices"][k] for r in rows if r["prices"][k] is not None]
        if not ps:
            continue
        lo = sum(p < LO for p in ps); mid = sum(LO <= p <= HI for p in ps); hi = sum(p > HI for p in ps)
        print(f"{k:>5} {len(ps):>4} {lo:>6} {mid:>11} {hi:>7} {statistics.median(ps):>8.3f}")
    w = [r["in_window_min"] for r in rows]
    ab = [r["to_above_min"] for r in rows if r["to_above_min"] is not None]
    inwin = [x for x in w if x > 0.2]
    print(f"\nMatches where the winner sat inside {LO}-{HI} at some point AFTER the true end: {len(inwin)} of {n}")
    if inwin:
        q = statistics.quantiles(inwin, n=4) if len(inwin) >= 4 else [min(inwin), statistics.median(inwin), max(inwin)]
        print(f"  minutes inside the window after the end: median {statistics.median(inwin):.1f}, quartiles {q[0]:.1f}/{q[-1]:.1f}, max {max(inwin):.1f}")
    if ab:
        print(f"Minutes from true end until price exceeded {HI}: median {statistics.median(ab):.1f} (n={len(ab)})")
    cm = [r["closed_min"] for r in rows if r["closed_min"] is not None]
    if cm:
        print(f"Minutes from true end until Polymarket closed/paid: median {statistics.median(cm):.0f}, "
              f"quartiles {statistics.quantiles(cm, n=4)[0]:.0f}/{statistics.quantiles(cm, n=4)[-1]:.0f}")
    print("\nCaveat: mid prices; 'true end' = last game start + duration from OpenDota (small timing error possible).")


if __name__ == "__main__":
    main()
