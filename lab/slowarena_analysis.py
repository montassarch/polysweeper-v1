"""Slow-arena sweep check (idea #21): in decided election markets, who bought at 0.96-0.995, how long did shares stay on offer, did any in-band buy lose?

  python3 lab/slowarena_analysis.py <events.json> <t_close_unix> [label]
events.json: [{id, slug, markets:[{cid, q, final(outcomePrices json str)}]}] (lab/data/raw/*.json); tapes in lab/data/raw/slowarena/<id>.json.
'Winner' of a market = its current Yes price >= 0.9 (Yes pays), <= 0.1 (No pays); anything in between = undecided and skipped.
t_close = when counting started (polls closed), unix seconds.
"""
import collections, json, statistics, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
evf, tclose = sys.argv[1], float(sys.argv[2])
label = sys.argv[3] if len(sys.argv) > 3 else ""
events = json.loads(Path(evf).read_text())
BANDS = [(0.96, 0.995, "0.96-0.995"), (0.995, 0.9995, "0.995-0.999"), (0.9995, 1.01, "0.9995+")]
tot = collections.Counter(); late_rows = []
per_event = []
for e in events:
    f = ROOT / f"lab/data/raw/slowarena/{e['id']}.json"
    if not f.exists():
        continue
    tape = json.loads(f.read_text())
    mk = {}
    for m in e["markets"]:
        try:
            yes = float(json.loads(m["final"])[0])
        except (TypeError, ValueError):
            continue
        if yes >= 0.9 or yes <= 0.1:
            mk[m["cid"]] = 1 if yes >= 0.9 else 0           # 1: Yes pays, 0: No pays
    if not mk:
        continue
    rows = []
    for t in tape:
        if t["conditionId"] not in mk or t["timestamp"] < tclose:
            continue
        yes_pays = mk[t["conditionId"]]
        pays = (t["outcomeIndex"] == 0) == (yes_pays == 1)
        rows.append({"p": float(t["price"]), "size": float(t["size"]), "dt": t["timestamp"] - tclose, "side": t["side"], "pays": pays, "w": t["proxyWallet"], "cid": t["conditionId"], "out": t["outcome"]})
    if not rows:
        continue
    # winner (Yes pays) markets: first time the Yes token traded >= 0.96 / 0.99
    first = {}
    for r in sorted(rows, key=lambda r: r["dt"]):
        if r["pays"] and r["p"] >= 0.96 and r["out"] in ("Yes",) and "first96" not in first.get(r["cid"], {}):
            first.setdefault(r["cid"], {})["first96"] = r["dt"]
    ev_rows = {}
    for lo, hi, name in BANDS:
        buys = [r for r in rows if r["side"] == "BUY" and lo <= r["p"] < hi]
        good = [r for r in buys if r["pays"]]; bad = [r for r in buys if not r["pays"]]
        ev_rows[name] = (len(good), len(bad), sum(r["size"] for r in good), sum(r["size"] for r in bad))
        tot[(name, "good")] += len(good); tot[(name, "bad")] += len(bad)
        tot[(name, "good_sh")] += sum(r["size"] for r in good); tot[(name, "bad_sh")] += sum(r["size"] for r in bad)
        for r in bad:
            late_rows.append((e["slug"][:40], name, r["p"], r["size"], r["dt"] / 60, r["out"], r["w"][:8]))
    b = [r for r in rows if r["side"] == "BUY" and 0.96 <= r["p"] < 0.995 and r["pays"]]
    per_event.append((e["slug"][:46], ev_rows["0.96-0.995"], ev_rows["0.995-0.999"], min((r["dt"] for r in b), default=None), max((r["dt"] for r in b), default=None)))
print(f"=== {label}: {len(per_event)} events with decided markets and trades after t_close ===")
for name in ("0.96-0.995", "0.995-0.999", "0.9995+"):
    print(f"  buys {name:12}: pay-off tokens {tot[(name,'good')]:5} fills / {tot[(name,'good_sh')]:9.0f} sh   WRONG-side tokens {tot[(name,'bad')]:4} fills / {tot[(name,'bad_sh')]:8.0f} sh")
print("  per event, in-band 0.96-0.995 buys (good fills, bad fills, good shares) | first/last in-band buy minutes after close:")
for slug, a, b, mn, mx in per_event:
    print(f"   {slug:46} {a[0]:3} {a[1]:2} {a[2]:7.0f} sh | {'' if mn is None else round(mn/60)} .. {'' if mx is None else round(mx/60)} min")
print("  WRONG-side in-band buys (any time after close):")
for r in sorted(late_rows, key=lambda r: r[4])[:40]:
    print("   ", r)
