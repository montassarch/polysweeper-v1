"""Measure: when a token's price first entered the sweep window, how often did it win?

Usage: python -m polysweeper.analyze data/real/*.jsonl [--lo 0.96 --hi 0.995]

Uses MID prices from history, so it is optimistic about what you could buy.
It answers the key question first: is the win rate in each price bucket higher
than the price itself (after fees)?
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

BUCKETS = [(0.96, 0.97), (0.97, 0.98), (0.98, 0.99), (0.99, 0.995)]


def result_of(final: float) -> str:
    if final >= 0.99:
        return "win"
    if final <= 0.01:
        return "loss"
    return "split"


def entry_of(hist, lo, hi):
    """First history point inside [lo, hi]; returns (index, time, price, from_below)."""
    for i, (t, p) in enumerate(hist):
        if lo <= p <= hi:
            return i, t, p, any(q < lo for _, q in hist[:i])
    return None


def window_minutes(hist, i, hi):
    t0 = hist[i][0]
    for t, p in hist[i + 1:]:
        if p > hi:
            return (t - t0) / 60.0
    return (hist[-1][0] - t0) / 60.0


def analyze(paths, lo=0.96, hi=0.995):
    rows = []
    markets = 0
    for path in paths:
        for line in Path(path).read_text().splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            markets += 1
            rate = rec.get("fee_rate") or 0.05
            for tok in rec["tokens"]:
                e = entry_of(tok["history"], lo, hi)
                if not e:
                    continue
                i, t, p, from_below = e
                res = result_of(tok["final_price"])
                fee = rate * p * (1 - p)
                pnl = {"win": 1 - p - fee, "loss": -(p + fee), "split": 0.5 - p - fee}[res]
                rows.append({"league": rec["league"], "p": p, "res": res, "pnl": pnl,
                             "from_below": from_below,
                             "win_min": window_minutes(tok["history"], i, hi)})
    return markets, rows


def summarize(rows, title):
    lines = [f"--- {title}  (n={len(rows)})"]
    lines.append(f"{'bucket':<12}{'n':>5}{'win':>5}{'loss':>6}{'split':>6}{'winrate':>9}{'avg price':>10}{'EV/share':>10}")
    for lo, hi in BUCKETS:
        sub = [r for r in rows if lo <= r["p"] < hi or (hi == 0.995 and r["p"] == 0.995)]
        if not sub:
            continue
        w = sum(r["res"] == "win" for r in sub)
        l = sum(r["res"] == "loss" for r in sub)
        s = len(sub) - w - l
        avg_p = statistics.mean(r["p"] for r in sub)
        ev = statistics.mean(r["pnl"] for r in sub)
        lines.append(f"{lo:.2f}-{hi:.3f}  {len(sub):>5}{w:>5}{l:>6}{s:>6}{w/len(sub):>9.3f}{avg_p:>10.3f}{ev:>+10.4f}")
    if rows:
        ev_all = statistics.mean(r["pnl"] for r in rows)
        lines.append(f"ALL: avg EV per share {ev_all:+.4f}  | losses {sum(r['res']=='loss' for r in rows)}, splits {sum(r['res']=='split' for r in rows)}")
    return "\n".join(lines)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--lo", type=float, default=0.96)
    ap.add_argument("--hi", type=float, default=0.995)
    a = ap.parse_args(argv[1:])
    markets, rows = analyze(a.paths, a.lo, a.hi)
    print(f"markets read: {markets}; tokens that ever entered {a.lo}-{a.hi}: {len(rows)}\n")
    print(summarize(rows, "ALL"))
    print()
    print(summarize([r for r in rows if r["from_below"]], "entered from BELOW (price rose into the window, e.g. during the game)"))
    print()
    print(summarize([r for r in rows if not r["from_below"]], "already high at first data point (pre-game heavy favourite)"))
    by = defaultdict(list)
    for r in rows:
        by[r["league"]].append(r)
    print("\nBy league:")
    for lg, rs in sorted(by.items()):
        w = sum(x["res"] == "win" for x in rs)
        print(f"  {lg:<8} n={len(rs):<4} win={w:<4} loss={sum(x['res']=='loss' for x in rs):<3} split={sum(x['res']=='split' for x in rs):<3} EV/share {statistics.mean(x['pnl'] for x in rs):+.4f}")
    wins = [r["win_min"] for r in rows if r["from_below"] and r["res"] == "win"]
    if wins:
        q = statistics.quantiles(wins, n=4) if len(wins) >= 4 else [min(wins), statistics.median(wins), max(wins)]
        print(f"\nWinners that entered from below: minutes spent between {a.lo} and {a.hi} before reaching >{a.hi}: "
              f"median {statistics.median(wins):.1f}, quartiles {', '.join(f'{x:.1f}' for x in q)}")
    print("\nCaveat: mid prices, not real asks; no depth data. Optimistic. Verify in shadow mode.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
