"""Slow-arena: after the market's own 'decided' moment (first print >= 0.95 on the winner after the polls closed), how many shares were bought in 0.96-0.995, within 10/30/60/120 min?

  python3 lab/slowarena_lockproxy.py <events.json> <t_close_unix> <label> [only_yes=1]
Per decided market (winner = Yes token pays). Reports per-event the shares in-band 0-10, 10-30, 30-60, 60-120 min after the decided moment, and the totals.
"""
import collections, json, statistics, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
evf, tclose, label = sys.argv[1], float(sys.argv[2]), sys.argv[3]
events = json.loads(Path(evf).read_text())
W = [(0, 600, "0-10m"), (600, 1800, "10-30m"), (1800, 3600, "30-60m"), (3600, 7200, "60-120m"), (7200, 14400, "2-4h")]
tot = collections.defaultdict(lambda: [0, 0.0]); n_mk = 0; n_with50 = 0; per = []
for e in events:
    f = ROOT / f"lab/data/raw/slowarena/{e['id']}.json"
    if not f.exists():
        continue
    tape = json.loads(f.read_text())
    for m in e["markets"]:
        try:
            yes = float(json.loads(m["final"])[0])
        except (TypeError, ValueError):
            continue
        if yes < 0.9:
            continue                                   # the winner token of a market where Yes wins
        rows = sorted([t for t in tape if t["conditionId"] == m["cid"] and t["timestamp"] >= tclose], key=lambda t: t["timestamp"])
        first = next((t["timestamp"] for t in rows if t["outcomeIndex"] == 0 and float(t["price"]) >= 0.95), None)
        if first is None:
            continue
        n_mk += 1
        got = {}
        for lo, hi, name in W:
            rs = [t for t in rows if t["side"] == "BUY" and t["outcomeIndex"] == 0 and 0.96 <= float(t["price"]) < 0.995 and first + lo <= t["timestamp"] < first + hi]
            got[name] = (len(rs), sum(float(t["size"]) for t in rs))
            tot[name][0] += len(rs); tot[name][1] += got[name][1]
        if got["0-10m"][1] >= 50:
            n_with50 += 1
        per.append((e["slug"][:40], m["q"][:50], round((first - tclose) / 60), got))
print(f"=== {label}: decided Yes-winner markets {n_mk}; markets with >=50 shares in-band within 10 min of the decided moment: {n_with50}")
for lo, hi, name in W:
    print(f"   {name:8} fills {tot[name][0]:5}  shares {tot[name][1]:9.0f}")
print("  biggest markets by in-band shares in the first hour after decided:")
for s, q, mins, got in sorted(per, key=lambda x: -(x[3]['0-10m'][1] + x[3]['10-30m'][1] + x[3]['30-60m'][1]))[:6]:
    print(f"   {s:40} {q:50} decided {mins:4d} min after close | " + ", ".join(f"{k}:{v[0]}f/{v[1]:.0f}sh" for k, v in got.items()))
