"""Backup study (market making): best-case reward income for a small budget, from the mm_scan snapshot.

Greedy fill of a $100 / $500 budget with minimum-size two-sided quotes (k = 1..5 units per market), picking the
best marginal reward $/day per marginal $ of capital. Upper bound: assumes the book stays as in the snapshot all
day and that we are never filled (no adverse selection). Read-only, no network.

Usage: py -3 lab/mm_budget.py     -> prints, and writes lab/results/2026-10-08-mm-budget.json
"""
import json, os, collections

ROOT = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(ROOT, "data", "raw", "mm", "scan-rows.json"), encoding="utf-8"))


def plan(budget, mode, keep):
    cands = [r for r in rows if not r.get("empty_side") and r.get("rate", 0) > 0 and keep(r)]
    used = 0.0
    k = collections.Counter()
    total = 0.0
    picks = []
    def gain(r, n):
        q1 = (r["qA"] if mode == "A" else r["qB"]) * n
        return r["rate"] * q1 / (r["qbook"] + q1) if q1 > 0 else 0.0
    def cap(r):
        return r["capA"] if mode == "A" else r["capB"]
    while True:
        best, bv = None, 0.0
        for i, r in enumerate(cands):
            if k[i] >= 5 or cap(r) <= 0:
                continue
            g = gain(r, k[i] + 1) - gain(r, k[i])
            if used + cap(r) > budget:
                continue
            if g / cap(r) > bv:
                bv, best = g / cap(r), i
        if best is None or bv <= 0:
            break
        r = cands[best]
        total += gain(r, k[best] + 1) - gain(r, k[best])
        k[best] += 1
        used += cap(r)
    for i, n in k.items():
        r = cands[i]
        picks.append({"q": r["q"][:60], "type": r["type"], "units": n, "usd_day": round(gain(r, n), 2),
                      "capital": round(cap(r) * n, 1), "rate": r["rate"], "qbook": r["qbook"], "mid": r["mid"],
                      "end_days": r.get("end_days")})
    picks.sort(key=lambda p: -p["usd_day"])
    return {"budget": budget, "mode": mode, "usd_day": round(total, 2), "capital_used": round(used, 1),
            "markets": len(picks), "types": dict(collections.Counter(p["type"] for p in picks)), "top": picks[:12]}


out = {}
filters = {
    "all": lambda r: True,
    "no_resolution_within_7d_no_sports_games": lambda r: (r.get("end_days") is None or r["end_days"] > 7)
    and not r["type"].startswith("sports_game"),
    "mid_0.10_0.90_and_7d": lambda r: 0.10 <= r["mid"] <= 0.90 and (r.get("end_days") is None or r["end_days"] > 7)
    and not r["type"].startswith("sports_game"),
}
for name, f in filters.items():
    for b in (100, 500):
        for mode in ("A", "B"):
            p = plan(b, mode, f)
            out[f"{name}:{b}:{mode}"] = p
            print(name, b, mode, p["usd_day"], "$/day on", p["capital_used"], "in", p["markets"], "markets", p["types"])
json.dump(out, open(os.path.join(ROOT, "results", "2026-10-08-mm-budget.json"), "w"), indent=1)
