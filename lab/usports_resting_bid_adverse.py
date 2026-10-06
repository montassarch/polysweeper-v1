"""Passive bids at 0.96-0.99: when a taker SELLS into such a bid (a maker 'BUY' fill), how often is the token a LOSER?  (public tape, US-sports main events, 15 days)
This is the adverse-selection rate a resting bid at 0.96-0.99 would face if it bid on every near-certain-looking token. Split by time vs the official end and by market type."""
import collections, json, statistics, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
ev = {e["id"]: e for e in json.loads((ROOT / "lab/data/raw/usports_events.json").read_text())}
end = {}
for f in ("espn_official_end_cache.json", "mlb_official_end_cache.json"):
    for k, v in json.loads((ROOT / "lab/data/raw" / f).read_text()).items():
        if v:
            end[k] = v["end"]
rows = []
for f in (ROOT / "lab/data/raw/usports_tape").glob("*.json"):
    e = ev.get(f.stem)
    if not e or e["slug"] != e["game"] or e["game"] not in end:
        continue
    d = json.loads(f.read_text())
    fm = {}
    for m in e["markets"]:
        try:
            px = [float(x) for x in json.loads(m["final"])]
        except (TypeError, ValueError):
            continue
        if sorted(px) == [0.0, 1.0]:
            fm[m["cid"]] = (px, m["type"])
    for t in d["trades"]:
        x = fm.get(t["conditionId"])
        if not x or t["side"] != "SELL":
            continue
        p = float(t["price"])
        if not (0.96 <= p <= 0.99):
            continue
        px, typ = x
        rows.append({"dt": t["timestamp"] - end[e["game"]], "typ": typ, "win": px[t["outcomeIndex"]] == 1.0, "s": float(t["size"]), "p": p, "sport": e["sport"], "game": e["game"]})
print("taker SELL fills at 0.96-0.99 (maker bids hit) in US-sports main events:", len(rows), "games", len({r['game'] for r in rows}))
def block(name, rs):
    if not rs:
        return
    lost = [r for r in rs if not r["win"]]
    pnl = sum(r["s"] * ((1 - r["p"]) if r["win"] else -r["p"]) for r in rs)       # the BIDDER's pnl, no fees (makers pay none)
    print(f"  {name:34} fills {len(rs):5} shares {sum(r['s'] for r in rs):8.0f}  on losers {len(lost):4} ({len(lost)/len(rs):.1%})  bidder pnl ${pnl:9.0f}")
for lo, hi, name in ((-1e9, -1800, "30+ min before the end"), (-1800, -300, "5-30 min before"), (-300, 0, "last 5 min before"), (0, 120, "0-2 min after"), (120, 1e9, "2+ min after")):
    block(name, [r for r in rows if lo <= r["dt"] < hi])
print(" by market type (all times):")
for typ, n in collections.Counter(r["typ"] for r in rows).most_common(8):
    block(str(typ), [r for r in rows if r["typ"] == typ])
print(" moneyline, last 30 min before the end by sport:")
for sp in ("MLB", "NHL", "NFL", "CFB", "WNBA", "NBA"):
    block(sp, [r for r in rows if r["sport"] == sp and r["typ"] == "moneyline" and -1800 <= r["dt"] < 0])

out = {}
for lo, hi, name in ((-1e9, -1800, "30+ min before"), (-1800, -300, "5-30 min before"), (-300, 0, "last 5 min"), (0, 120, "0-2 min after"), (120, 1e9, "2+ min after")):
    x = [r for r in rows if lo <= r["dt"] < hi]
    out[name] = {"fills": len(x), "shares": round(sum(r["s"] for r in x)), "on_losers": sum(1 for r in x if not r["win"])}
out["moneyline_last30"] = {sp: {"fills": len(x), "on_losers": sum(1 for r in x if not r["win"])} for sp in ("MLB", "NHL", "NFL", "CFB", "WNBA", "NBA")
                          for x in [[r for r in rows if r["sport"] == sp and r["typ"] == "moneyline" and -1800 <= r["dt"] < 0]]}
(ROOT / "lab/results" / f"{time.strftime('%Y-%m-%d')}-usports-resting-bid-adverse.json").write_text(json.dumps(out, indent=1))
