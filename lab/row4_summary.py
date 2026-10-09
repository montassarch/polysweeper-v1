"""Compact table for the daily note: per sport, no gate vs live-readable gates (loser GAMES / games, 95% upper bound), cheap supply of the
decided gate. Reads lab/results/2026-10-09-row4-history-rules*.json written by lab/row4_rules.py (STATE_DELTA 0 and 45 variants).
  python3 lab/row4_summary.py"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for tag in ("", "-d45"):
    f = ROOT / f"lab/results/2026-10-09-row4-history-rules{tag}.json"
    if not f.exists():
        continue
    d = json.loads(f.read_text())
    print(f"\n=== state read at the fill second{' (45 s earlier)' if tag else ''} ===")
    gates = [("all fills (no gate)", "no gate"), ("T120: last period/OT, clock<=120s, buyer ahead", "T120"), ("T60: last period/OT, clock<=60s, buyer ahead", "T60"),
             ("D1b timed: last period/OT, clock<=5s, buyer ahead", "D1b"), ("D2 MLB: game over (final out / walk-off) by ESPN state", "MLB over"),
             ("MLB inn>=9, lead>=4", "inn9 lead4")]
    print(f"{'sport':6s}" + "".join(f"{lab:>20s}" for _, lab in gates))
    for sport in ("CFB", "NFL", "NBA", "WNBA", "NHL", "MLB"):
        row = f"{sport:6s}"
        for key, lab in gates:
            v = d.get(sport, {}).get(key)
            row += f"{(str(v['loser_games']) + '/' + str(v['games'])) if v else '-':>20s}"
        print(row)
    print("supply (cheap 0.98-0.995, >=5 shares per game):")
    for k, v in d.get("supply", {}).items():
        if v["matched_games"]:
            print(f"  {k:36s} games with supply {v['games_with_cheap_fill']:4d} of {v['matched_games']:4d} ({v['share_of_games']:.2f}), per active day {v['games_per_active_day']:.2f} games / {v['fills_per_active_day']:.1f} fills, median shares {v['median_shares_per_game']:.0f}, loser games {v['loser_games']}")
