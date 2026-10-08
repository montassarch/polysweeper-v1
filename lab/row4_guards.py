"""Row 4 guard tests on the 32-day bid-side fills (see late_bids_moneyline.py, file ...-fills.json).
Each row: sport, game, seconds before Polymarket's 'finished' stamp, price, shares, on_loser.
A guard is a filter on (sport, seconds before the stamp, price). For each guard: bid-side fills, games with a fill,
fills on the loser, games with a loser fill, and the profit/loss of ONE 5-share resting bid per game that gets filled
(first fill of the game that passes the guard; price = that fill's price).
  python3 lab/row4_guards.py lab/results/2026-10-08-late-bids-moneyline-32d-fills.json"""
import collections, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
d = json.loads((ROOT / sys.argv[1]).read_text())
rows = [dict(zip(d["cols"], r)) for r in d["rows"]]
games_all = collections.defaultdict(list)
for r in rows: games_all[r["game"]].append(r)

def run(name, fn):
    sel = [r for r in rows if fn(r)]
    g = collections.defaultdict(list)
    for r in sel: g[r["game"]].append(r)
    loser_games = [k for k, v in g.items() if any(x["on_loser"] for x in v)]
    # one 5-share bid per game: the first (earliest in time = largest secs_before) passing fill
    pnl = 0.0; n = 0
    for k, v in g.items():
        f = max(v, key=lambda x: x["secs_before_stamp"])
        n += 1
        pnl += (-f["price"] * 5) if f["on_loser"] else ((1 - f["price"]) * 5)
    return dict(guard=name, fills=len(sel), losers=sum(r["on_loser"] for r in sel), games=len(g), loser_games=len(loser_games),
                bid_per_game_pnl_usd=round(pnl, 2), per_game=round(pnl / n, 4) if n else None)

out = []
G = [("all >=0.98", lambda r: True),
     ("price >= 0.99", lambda r: r["price"] >= 0.99),
     ("price 0.98-0.995", lambda r: r["price"] < 0.995),
     ("last 15 min", lambda r: r["secs_before_stamp"] <= 900),
     ("last 12 min", lambda r: r["secs_before_stamp"] <= 720),
     ("last 10 min", lambda r: r["secs_before_stamp"] <= 600),
     ("last 5 min", lambda r: r["secs_before_stamp"] <= 300),
     ("last 10 min and price < 0.995", lambda r: r["secs_before_stamp"] <= 600 and r["price"] < 0.995),
     ("NFL/NHL/NBA only", lambda r: r["sport"] in ("NFL", "NHL", "NBA")),
     ("no CFB", lambda r: r["sport"] != "CFB"),
     ("NFL/NHL/NBA, price < 0.995", lambda r: r["sport"] in ("NFL", "NHL", "NBA") and r["price"] < 0.995),
     ("last 10 min, no CFB", lambda r: r["secs_before_stamp"] <= 600 and r["sport"] != "CFB")]
for name, fn in G:
    o = run(name, fn); out.append(o); print(o)
(ROOT / "lab/results/2026-10-08-row4-guards.json").write_text(json.dumps(out, indent=1))
# loser fills by seconds before the stamp (all sports)
print("loser fills secs_before_stamp:", sorted(r["secs_before_stamp"] for r in rows if r["on_loser"]))
