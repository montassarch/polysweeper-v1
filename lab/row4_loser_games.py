"""Row 4 loser review (2026-10-08): the 32-day late-bids test found games where the side that LOST traded at 0.98+ inside the
last 30 min before Polymarket's 'finished' stamp. For each such game: the loser token's price path (seconds before the stamp),
how long it sat at 0.98+, how fast it collapsed, and the final score, so a guard (time, price, sport) can be tested.
  python3 lab/row4_loser_games.py lab/results/2026-10-08-late-bids-moneyline-32d.json
Reads the game list from the result file (keys sell_fills_on_losers and losing taker buys re-derived), re-pulls those tapes only."""
import collections, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
from polysweeper.collector import get_json, GAMMA, parse_ts  # noqa: E402
DATA = "https://data-api.polymarket.com"
res = json.loads((ROOT / sys.argv[1]).read_text())
games = {x[1] for x in res.get("sell_fills_on_losers", [])}
games |= {x[0] for x in res.get("losing_taker_buys", [])}
print("games with a loser trade at 0.98+ in the last 30 min:", len(games))
out = []
for g in sorted(games):
    e = (get_json(f"{GAMMA}/events?slug={g}") or [None])[0]
    if not e: continue
    fin = parse_ts(e["finishedTimestamp"])
    m = [x for x in e["markets"] if x.get("sportsMarketType") == "moneyline"][0]
    px = [float(v) for v in json.loads(m["outcomePrices"])]
    outcomes = json.loads(m["outcomes"])
    loser_idx = px.index(0.0)
    rows, off = [], 0
    while off <= 10000:
        pg = get_json(f"{DATA}/trades?market={m['conditionId']}&limit=500&offset={off}")
        if not isinstance(pg, list) or not pg: break
        rows += pg
        if min(t["timestamp"] for t in pg) < fin - 3600 or len(pg) < 500: break
        off += 500
    # price of the loser token, seen from trades on either side (taker SELL/BUY of the loser token, or the winner token at 1-p)
    path = []
    for t in rows:
        if not (fin - 1800 <= t["timestamp"] <= fin + 60): continue
        p = float(t["price"]); idx = t["outcomeIndex"]
        pl = p if idx == loser_idx else 1 - p
        path.append((fin - t["timestamp"], pl, float(t["size"])))
    path.sort(reverse=True)
    hi = [(s, p) for s, p, _ in path if p >= 0.98]
    first98 = max((s for s, _ in hi), default=None); last98 = min((s for s, _ in hi), default=None)
    peak = max(path, key=lambda x: x[1]) if path else None
    # price 5 min / 2 min / 1 min after the last 0.98+ print
    after = {}
    if last98 is not None:
        for d in (60, 120, 300):
            later = [p for s, p, _ in path if s <= last98 - d]
            after[f"{d}s_later_min_price"] = round(min(later), 3) if later else None
    out.append({"game": g, "loser": outcomes[loser_idx], "score": e.get("score"), "sport": g.split("-")[0],
                "first_098_s_before_end": first98, "last_098_s_before_end": last98, "peak": [round(peak[1], 3), peak[0]] if peak else None, **after,
                "n_trades_098": len(hi)})
for o in out: print(o)
(ROOT / "lab/results/2026-10-08-row4-loser-games.json").write_text(json.dumps(out, indent=1))
