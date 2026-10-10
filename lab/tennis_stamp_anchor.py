"""Tennis match-over bid (T1), re-anchored on Polymarket's finished STAMP (ps-researcher, 2026-10-10). Read-only, public tape.

Why: the T1 model (tennis_t1_stress.py) set the moment the free score sites say "over" at stamp - 160 s, taken from the laptop feed race.
But the feed race measured the lead over Polymarket's Gamma `ended` flag, and the flag comes a median ~51 s AFTER the stamp
(`finishedTimestamp`). Measured on the 20 live final_bid matches of 10 Oct: 365Scores "final" -> stamp: median 25 s (p25 6, p75 50).
So a bid that joins when two sources say "over" arrives about at the stamp, not 160 s before it. This script recomputes the fill share
with the join time and the hold time measured from the STAMP, on all ATP/WTA singles of the last 14 days (needs
`python3 lab/tennis_decided_bids.py pull 14`; tape window = [stamp - 30 min, stamp + 15 min], prices >= 0.9).

  python3 lab/tennis_stamp_anchor.py  -> lab/results/2026-10-10-tennis-stamp-anchor.json
Fill rule (same as the stress test): a taker SELL print on the winner at 0.95 <= price <= B in (join, hold_until] fills us first (price
priority); h = share of the sold shares that reaches us (queue); fill when h * sold >= 5 shares.
"""
import collections, json, random, statistics, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.argv = sys.argv[:1] + ["x"]
sys.path.insert(0, str(ROOT / "lab"))
import tennis_decided_bids as T  # noqa: E402

data = []
for g in T.games():
    f = T.TAPE / f"{g['game']}.json"
    if f.exists():
        d = json.loads(f.read_text())
        if d["ok"]:
            data.append((g, sorted(d["trades"]), g["px"].index(1.0)))
print("matches", len(data), collections.Counter(g["sport"] for g, _, _ in data))


def fills(join_off, hold_off, B, h, sample=None):
    n = 0
    for g, tr, w in sample or data:
        lo, hi = g["fin"] + join_off, g["fin"] + hold_off
        if hi <= lo:
            continue
        sold = 0.0
        for t in tr:
            if t[1] == "SELL" and t[4] == w and 0.95 <= t[2] <= B + 1e-9 and lo < t[0] <= hi:
                sold += t[3] * h
                if sold >= 5:
                    n += 1
                    break
    return n


N = len(data)
out = {"matches": N, "grid": {}, "bins_cheap_sell_matches": {}, "loser_fills": {}}
JOINS = (-180, -120, -60, -30, -15, 0, 15, 30, 60, 120)
HOLDS = (0, 60, 120, 300, 900)
print("\nshare of matches with a fill (B=0.995, h=1.0). rows = join offset from the stamp (s), columns = hold until (s after the stamp)")
print("join\\hold " + "".join(f"{h:>8}" for h in HOLDS))
for j in JOINS:
    row = []
    for hd in HOLDS:
        k = fills(j, hd, 0.995, 1.0)
        out["grid"][f"B=0.995 h=1 join={j} hold={hd}"] = round(100 * k / N, 1) if hd > j else None
        row.append(f"{100 * k / N:7.1f}%" if hd > j else "      - ")
    print(f"{j:>8}  " + "".join(row))
for B, h in ((0.995, 0.5), (0.99, 1.0)):
    print(f"\nB={B} h={h}")
    for j in JOINS:
        row = []
        for hd in HOLDS:
            k = fills(j, hd, B, h)
            out["grid"][f"B={B} h={h} join={j} hold={hd}"] = round(100 * k / N, 1) if hd > j else None
            row.append(f"{100 * k / N:7.1f}%" if hd > j else "      - ")
        print(f"{j:>8}  " + "".join(row))

# when do the cheap sells happen, relative to the stamp? (share of matches with >=5 cheap shares sold in each window)
print("\nmatches with >=5 cheap (<=0.995) winner shares sold in each window relative to the stamp")
for lo, hi in ((-600, -300), (-300, -180), (-180, -120), (-120, -60), (-60, -30), (-30, 0), (0, 30), (30, 60), (60, 120), (120, 300), (300, 900)):
    k = 0
    for g, tr, w in data:
        s = sum(t[3] for t in tr if t[1] == "SELL" and t[4] == w and 0.95 <= t[2] <= 0.995 + 1e-9 and g["fin"] + lo < t[0] <= g["fin"] + hi)
        k += s >= 5
    out["bins_cheap_sell_matches"][f"{lo}..{hi}"] = round(100 * k / N, 1)
    print(f"  {lo:>5}..{hi:<4} {100 * k / N:5.1f}%")

# loser exposure: cheap sells of the LOSER's token at 0.95+ in the window (a bid on the wrong side would have been hit)
lost = collections.Counter()
for g, tr, w in data:
    for lo, hi, name in ((-300, -120, "-300..-120"), (-120, 0, "-120..0"), (0, 900, "0..900")):
        s = sum(t[3] for t in tr if t[1] == "SELL" and t[4] != w and 0.95 <= t[2] <= 0.995 + 1e-9 and g["fin"] + lo < t[0] <= g["fin"] + hi)
        lost[name] += s >= 5
out["loser_side_cheap_sells_matches"] = dict(lost)
print("\nmatches where the LOSER's token had >=5 shares sold at 0.95-0.995 (a bid on the loser would have filled):", dict(lost))

# expected share with the REAL lead distribution (365 'final' -> stamp, 20 live matches) and a pipeline delay
LEAD = [-3.4, 0.6, 46.2, 14.4, 98.4, 117.5, 73.8, -6.2, -1.0, 60.1, 27.0, 23.8, -3.8, 46.5, 44.8, 50.2, 40.9, 5.9, 13.4, 21.8]
print("\nexpected fill share with the live lead (365 final -> stamp, 20 matches) + pipeline delay D, B=0.995, hold until stamp+HOLD")
for D in (3, 15, 30):
    for hold in (0, 120, 900):
        ks = []
        for lead in LEAD:
            ks.append(100 * fills(-lead + D, hold, 0.995, 1.0) / N if hold > -lead + D else 0.0)
        v = statistics.mean(ks)
        out.setdefault("live_lead_expectation", {})[f"delay={D} hold={hold}"] = round(v, 1)
        print(f"  delay {D:>2} s hold {hold:>3} s: {v:5.1f}% of matches")
json.dump(out, open(ROOT / "lab/results/2026-10-10-tennis-stamp-anchor.json", "w"), indent=1)
