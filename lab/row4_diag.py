"""Row 4 long-history diagnostics (read-only): who are the loser fills, and where is the cheap supply in time?
Needs lab/data/raw/row4h/fills.json (lab/row4_history.py join).   STATE_DELTA=45 reads the game state 45 s earlier.
  python3 lab/row4_diag.py   -> prints, writes lab/results/2026-10-09-row4-history-diag.json
"""
import collections, json, os
from pathlib import Path

import row4_rules as R

ROOT = Path(__file__).resolve().parent.parent
rows = [r for r in R.ROWS if r["ok"]]
out = {}

# 1. loser games at 0.98+ with no gate: state at the first/last loser fill
lg = collections.defaultdict(list)
for x in rows:
    if x["on_loser"] and 0.98 <= x["price"] < 0.9995:
        lg[x["game"]].append(x)
tab = []
for g, xs in lg.items():
    xs.sort(key=lambda r: r["sb"], reverse=True)
    a = xs[0]
    b = xs[-1]
    st = lambda x: (x.get("period"), x.get("clock"), x.get("lead"), x.get("to_end"))
    tab.append({"game": g, "sport": a["sport"], "day": a["day"], "val": a["val"], "fills": len(xs), "first": [a["price"], a["sb"]] + list(st(a)),
                "last": [b["price"], b["sb"]] + list(st(b)), "has_state": "period" in a})
tab.sort(key=lambda t: (t["sport"], t["day"]))
out["loser_games"] = tab
print("loser games (0.98+, last 30 min, no gate):", len(tab), dict(collections.Counter(t["sport"] for t in tab)))
for t in tab:
    print(f"  {t['sport']:5s} {t['game']:34s} val {t['val']:.2f} fills {t['fills']:3d} first(p,sb,per,clock,lead,to_end) {t['first']} last {t['last']}")

# 2. base rates by sport: games with a fill at 0.98+ and 0.98-0.995, loser games
base = {}
for sport in R.REG:
    for name, lo, hi in (("0.98-0.9995", 0.98, 0.9995), ("0.98-0.995", 0.98, 0.995), ("0.95-0.98", 0.95, 0.98)):
        sel = [x for x in rows if x["sport"] == sport and lo <= x["price"] < hi]
        s = R.stat(sel)
        base.setdefault(sport, {})[name] = s
out["base_rates"] = base
print("\nbase rates (fills in the last 30 min before the stamp, no gate):")
for sport, d in base.items():
    for name, s in d.items():
        print(f"  {sport:5s} {name:12s} fills {s['fills']:6d} games {s['games']:5d} loser games {s['loser_games']:3d}  ub95/game {s['ub95_per_game']}")

# 3. were the loser fills made while the bought side was ahead?
L = [x for x in rows if x["on_loser"] and "period" in x and x["price"] >= 0.98]
out["loser_fill_state"] = {"loser_fills_with_state": len(L), "ahead": sum(1 for x in L if x["lead"] >= 1), "tied": sum(1 for x in L if x["lead"] == 0),
                           "behind": sum(1 for x in L if x["lead"] < 0), "games": len({x["game"] for x in L}),
                           "games_ahead_at_every_fill": len({g for g in {x["game"] for x in L} if all(y["lead"] >= 1 for y in L if y["game"] == g)})}
print("\nloser fills with state:", out["loser_fill_state"])

# 4. timing of cheap fills (0.98-0.995) relative to the ESPN last play: share after the last play
cheap = [x for x in rows if 0.98 <= x["price"] < 0.995 and "to_end" in x]
tim = collections.defaultdict(collections.Counter)
for x in cheap:
    te = -x["to_end"]                    # seconds after the last play (negative = before)
    b = "before >120s" if te < -120 else "before 30-120s" if te < -30 else "before 0-30s" if te < 0 else "after 0-30s" if te < 30 else "after 30-60s" if te < 60 else "after 60-120s" if te < 120 else "after >120s"
    tim[x["sport"]][b] += 1
out["cheap_fill_timing_vs_last_play"] = {k: dict(v) for k, v in tim.items()}
print("\ncheap fills (0.98-0.995) by time vs ESPN last play:")
for sport, c in tim.items():
    tot = sum(c.values())
    print(f"  {sport:5s} n={tot}", {k: round(v / tot, 2) for k, v in sorted(c.items())})

(ROOT / "lab/results/2026-10-09-row4-history-diag.json").write_text(json.dumps(out, indent=1))
