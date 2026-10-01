"""Turn the big downloaded history (data/real/*.jsonl) into a tiny summary file
(data/backtest_summary.json) that the dashboard can show.

Usage: python -m polysweeper.backtest_summary
"""
from __future__ import annotations

import glob
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

from .analyze import BUCKETS, entry_of, result_of, window_minutes
from .collector import parse_ts

FOOTBALL = {"epl", "lal", "bun", "sea", "fl1", "ucl", "uel", "por", "ere"}
ESPORTS = {"cs2", "lol", "dota2", "val"}
TIMING = [(-1e9, 30, "0-30"), (30, 60, "30-60"), (60, 90, "60-90"), (90, 120, "90-120"),
          (120, 150, "120-150"), (150, 1e9, "150+")]


def load_rows(group):
    rows, starts, markets = [], [], 0
    for path in glob.glob("data/real/*.jsonl"):
        name = Path(path).stem
        if name not in group:
            continue
        for line in open(path):
            if not line.strip():
                continue
            r = json.loads(line)
            markets += 1
            g = parse_ts(r["game_start"]) or parse_ts(r["event_start"])
            if g:
                starts.append(g)
            closed = parse_ts(r["closed_time"])
            rate = r.get("fee_rate") or 0.05
            for tok in r["tokens"]:
                e = entry_of(tok["history"], 0.96, 0.995)
                if not e or not e[3]:
                    continue
                i, t, p, _ = e
                res = result_of(tok["final_price"])
                fee = rate * p * (1 - p)
                pnl = {"win": 1 - p - fee, "loss": -(p + fee), "split": 0.5 - p - fee}[res]
                rows.append({"p": p, "res": res, "pnl": pnl,
                             "mins": (closed - t) / 60 if closed else None,
                             "win_min": window_minutes(tok["history"], i, 0.995)})
    days = (max(starts) - min(starts)) / 86400 if starts else 0
    return rows, markets, days


def summarize(group):
    rows, markets, days = load_rows(group)
    out = {"markets": markets, "days": round(days, 1), "tokens": len(rows),
           "losses": sum(r["res"] == "loss" for r in rows),
           "ev_cents": round(100 * statistics.mean(r["pnl"] for r in rows), 2) if rows else None,
           "buckets": [], "timing": []}
    for lo, hi in BUCKETS:
        sub = [r for r in rows if lo <= r["p"] < hi or (hi == 0.995 and r["p"] == 0.995)]
        if sub:
            w = sum(r["res"] == "win" for r in sub)
            l = sum(r["res"] == "loss" for r in sub)
            out["buckets"].append({"label": f"{lo:.2f}-{hi:.3f}", "n": len(sub), "wins": w, "losses": l,
                                   "winrate": round(w / len(sub), 4),
                                   "avg_price": round(statistics.mean(r["p"] for r in sub), 4),
                                   "ev_cents": round(100 * statistics.mean(r["pnl"] for r in sub), 2)})
    for lo, hi, label in TIMING:
        sub = [r for r in rows if r["mins"] is not None and lo <= r["mins"] < hi]
        if sub:
            l = sum(r["res"] == "loss" for r in sub)
            out["timing"].append({"label": label, "n": len(sub), "losses": l,
                                  "loss_pct": round(100 * l / len(sub), 2),
                                  "ev_cents": round(100 * statistics.mean(r["pnl"] for r in sub), 2)})
    wins = [r["win_min"] for r in rows if r["res"] == "win"]
    if len(wins) >= 4:
        q = statistics.quantiles(wins, n=4)
        out["window_minutes"] = {"q1": round(q[0], 1), "median": round(q[1], 1), "q3": round(q[2], 1)}
    return out


def main():
    summary = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "note": "Mid prices, entry = first time price rose into 0.96-0.995, hold to payout. Optimistic.",
               "esports": summarize(ESPORTS), "football": summarize(FOOTBALL)}
    Path("data").mkdir(exist_ok=True)
    Path("data/backtest_summary.json").write_text(json.dumps(summary, indent=1))
    for k in ("esports", "football"):
        s = summary[k]
        print(f"{k}: {s['markets']} markets, {s['tokens']} tokens, {s['losses']} losses, EV {s['ev_cents']} cents/share")


if __name__ == "__main__":
    main()
