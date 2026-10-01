"""Summarise shadow-mode results: python -m polysweeper.shadow_report"""
from __future__ import annotations

import json
from pathlib import Path

PATH = Path("data/shadow/trades.jsonl")


def main():
    if not PATH.exists():
        print("no shadow data yet")
        return
    entries, settled, thin, bad = {}, {}, [], []
    for line in PATH.read_text().splitlines():
        r = json.loads(line)
        if r["type"] == "entry":
            entries[r["key"]] = r
        elif r["type"] == "settled":
            settled[r["key"]] = r
        elif r["type"] == "skip_thin":
            thin.append(r)
        elif r["type"] == "skip_bad_book":
            bad.append(r)
    print(f"entries: {len(entries)} | settled: {len(settled)} | skipped because the book was too thin: {len(thin)}"
          f" | skipped because the book looked fake: {len(bad)}")
    groups = [("CONFIRMED RESULT rule", lambda r: r.get("rule") == "confirmed"),
              ("PRICE ONLY rule, match flagged ended", lambda r: r.get("rule", "price_only") == "price_only" and r["event_ended_flag"] is True),
              ("PRICE ONLY rule, match still in play", lambda r: r.get("rule", "price_only") == "price_only" and r["event_ended_flag"] is not True)]
    for label, test in groups:
        keys = [k for k, r in entries.items() if test(r)]
        done = [k for k in keys if k in settled]
        wins = sum(settled[k]["result"] == "win" for k in done)
        losses = sum(settled[k]["result"] == "loss" for k in done)
        splits = len(done) - wins - losses
        pnl = sum(settled[k]["pnl"] for k in done)
        avg_fill = sum(entries[k]["vwap"] for k in keys) / len(keys) if keys else 0
        print(f"  {label}: entries {len(keys)}, settled {len(done)} (win {wins}, loss {losses}, 50/50 {splits}), "
              f"fake P&L ${pnl:+.2f}, avg fill {avg_fill:.3f}")
    if thin:
        print("  thin-book skips: the price looked right but fewer than the minimum shares were for sale at that price")


if __name__ == "__main__":
    main()
