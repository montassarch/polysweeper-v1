"""Same after-the-official-end supply, split by market type: MONEYLINE only (full-game winner) vs spreads/totals vs everything else.
The after-end LOSING buys found on the tape (31 of 2,281 fills) were all in totals (extra innings), half-time/quarter markets and props; none in a full-game moneyline."""
import collections, json, statistics, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
ev = {e["id"]: e for e in json.loads((ROOT / "lab/data/raw/usports_events.json").read_text())}
end = {}
for f in ("espn_official_end_cache.json", "mlb_official_end_cache.json"):
    for k, v in json.loads((ROOT / "lab/data/raw" / f).read_text()).items():
        if v:
            end[k] = v["end"]
games = collections.defaultdict(set); days = collections.defaultdict(set)
rows = []
for f in (ROOT / "lab/data/raw/usports_tape").glob("*.json"):
    e = ev.get(f.stem)
    if not e or e["slug"] != e["game"] or e["game"] not in end:
        continue
    games[e["sport"]].add(e["game"]); days[e["sport"]].add(time.strftime("%m-%d", time.gmtime(end[e["game"]])))
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
        dt = t["timestamp"] - end[e["game"]]
        if not x or t["side"] != "BUY" or dt < 0 or dt > 1800 or not (0.96 <= float(t["price"]) < 0.995) or float(t["size"]) < 5:
            continue
        px, typ = x
        if px[t["outcomeIndex"]] != 1.0:
            continue
        grp = "moneyline" if typ == "moneyline" else "spreads/totals" if typ in ("spreads", "totals") else "other"
        rows.append({"sport": e["sport"], "game": e["game"], "dt": dt, "grp": grp, "p": float(t["price"])})
out = {}
for sport in ("MLB", "NHL", "NFL", "CFB", "WNBA", "NBA"):
    g = len(games[sport])
    if not g:
        continue
    print(f"{sport}: {g} games, {len(days[sport])} game days. Fills of >=5 sh on the winner at 0.96-0.995, at or after X s from the official end:")
    for X in (5, 10, 30):
        cells = []
        for grp in ("moneyline", "spreads/totals", "other"):
            rs = [r for r in rows if r["sport"] == sport and r["grp"] == grp and r["dt"] >= X]
            cells.append(f"{grp}: {len(rs)/g:.2f}/game ({len({r['game'] for r in rs})}/{g} games)")
            out.setdefault(sport, {}).setdefault(grp, {})[X] = {"fills_per_game": round(len(rs) / g, 2), "games_with_fill": len({r["game"] for r in rs}), "games": g}
        print(f"   X>={X:2d}s  " + " | ".join(cells))
(ROOT / "lab/results" / f"{time.strftime('%Y-%m-%d')}-usports-moneyline-only.json").write_text(json.dumps(out, indent=1))
