"""Backup study (market making): read the pretend-quote recorder's summary and turn it into plain numbers.

Per type and policy (A = join best, B = one tick behind): pretend reward $, fills, mark-to-market P&L of the fills,
peak capital; then the best $100 / $500 portfolio (greedy on (reward + P&L) per $ of peak capital, whole markets
only). Read-only, no network. Usage: py -3 lab/mm_recorder_report.py
"""
import collections, json, os

ROOT = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(ROOT, "results", "mm-recorder-summary.json"), encoding="utf-8"))
hrs = max(d["hours"], 0.01)
print("hours recorded", hrs, "markets", d["markets"])
agg = collections.defaultdict(lambda: collections.defaultdict(float))
for r in d["per_market"]:
    for p in ("A", "B"):
        x = r[p]
        a = agg[(r["type"], p)]
        a["markets"] += 1
        a["reward"] += x["reward"]
        a["mtm"] += x["mtm"]
        a["fills"] += x["fills"]
        a["cap"] += x["peak_cap"]
        a["worst"] += x["worst"]
for (t, p), a in sorted(agg.items()):
    print(f"{t:24s} {p} mkts {int(a['markets']):2d} reward/day {a['reward'] / hrs * 24:8.2f}  fills {int(a['fills']):4d}"
          f"  fill P&L/day {a['mtm'] / hrs * 24:8.2f}  peak cap {a['cap']:8.0f}  worst {a['worst']:7.2f}")
out = {"hours": hrs}
for p in ("A", "B"):
    ms = []
    for r in d["per_market"]:
        x = r[p]
        if x["peak_cap"] <= 0:
            continue
        ms.append((((x["reward"] + x["mtm"]) / hrs * 24) / x["peak_cap"], r, x))
    ms.sort(key=lambda z: -z[0])
    for budget in (100, 500):
        used, tot_r, tot_m, picks = 0.0, 0.0, 0.0, []
        for k, r, x in ms:
            if k <= 0 or used + x["peak_cap"] > budget:
                continue
            used += x["peak_cap"]
            tot_r += x["reward"] / hrs * 24
            tot_m += x["mtm"] / hrs * 24
            picks.append((r["type"], r["q"][:45], round(x["peak_cap"]), round(x["reward"] / hrs * 24, 2), round(x["mtm"] / hrs * 24, 2)))
        out[f"{p}:{budget}"] = {"reward_day": round(tot_r, 2), "fill_pnl_day": round(tot_m, 2), "capital": round(used), "picks": picks}
        print(p, budget, "reward/day", round(tot_r, 2), "fill P&L/day", round(tot_m, 2), "capital", round(used), "markets", len(picks))
json.dump(out, open(os.path.join(ROOT, "results", "2026-10-08-mm-recorder-report.json"), "w"), indent=1)
