"""T1 stress test (2026-10-09): tennis 'match is over' price-priority bid, on public trades of the last N days (pull first with
   python3 lab/tennis_decided_bids.py pull 7).  No feed-race joins exist in the repo, so the 'settle' moment is modelled as
   stamp - LEAD (feed race: median 160 s, p10 ~15 s ahead of Polymarket's finished stamp).  Bot joins at settle + DELAY.
   Bid on the WINNER at B; a taker SELL print on the winner at price <= B in [join, stamp) fills us first (price priority);
   HAIRCUT h = only that share of the sold shares reaches us (queue ahead).  Fill when h*sold >= 5.  Loser fills = 0 by
   construction (we bid the winner); the real loser risk is a wrong source score (8-10 of ~90 disagreed, almost all doubles)."""
import json, sys, collections
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.argv = sys.argv[:1] + ["x"]
sys.path.insert(0, str(ROOT / "lab"))
import tennis_decided_bids as T

data = []
for g in T.games():
    f = T.TAPE / f"{g['game']}.json"
    if f.exists():
        d = json.loads(f.read_text())
        if d["ok"]:
            data.append((g, d["trades"], g["px"].index(1.0)))
out = {"matches": len(data), "cells": {}}
for lead in (160, 60, 16):
    for B in (0.99, 0.995, 0.998):
        for delay in (0, 30, 60, 90):
            for h in (1.0, 0.5, 0.25):
                fills = 0; waits = []; nowin = 0
                for g, tr, w in data:
                    join = g["fin"] - lead + delay
                    if join >= g["fin"]:
                        nowin += 1; continue
                    sold = 0.0
                    for t in sorted(tr):
                        if t[1] == "SELL" and t[4] == w and 0.95 <= t[2] <= B + 1e-9 and join <= t[0] < g["fin"]:
                            sold += t[3] * h
                            if sold >= 5:
                                fills += 1; waits.append(t[0] - join); break
                key = f"lead={lead} B={B} delay={delay} h={h}"
                out["cells"][key] = {"fill_pct": round(100 * fills / len(data), 1), "fills": fills, "window_closed": nowin,
                                     "median_wait_s": sorted(waits)[len(waits) // 2] if waits else None,
                                     "profit_per_fill": round((1 - B) * 5, 3)}
p = ROOT / "lab/results/2026-10-09-tennis-t1-stress.json"
p.write_text(json.dumps(out, indent=1))
print("matches", len(data))
for lead in (160, 60, 16):
    print("lead", lead)
    for B in (0.99, 0.995, 0.998):
        for delay in (0, 30, 60, 90):
            print(f" B={B} d={delay:2d} " + "  ".join(f"h={h}:{out['cells'][f'lead={lead} B={B} delay={delay} h={h}']['fill_pct']:5.1f}%" for h in (1.0, 0.5, 0.25)))
