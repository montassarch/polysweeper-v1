"""Row 4: turn "the last 10 minutes before Polymarket's stamp" into game-clock rules, and test lead rules.

For every bid-side fill (taker SELL at 0.98+, last 30 min before the stamp) in a game that ESPN matched, find the game state at the
fill second from ESPN's play-by-play (wallclock, period, clock, scores): period, seconds left on the clock, and the lead of the side
the buyer held (the winner for a normal fill, the loser for a fill on the loser). Then count fills / games / loser fills that survive
simple rules. Needs lab/data/raw/row4_espn_cache.json (made by lab/row4_espn_wp.py).
  python3 lab/row4_clock.py   -> lab/results/2026-10-08-row4-clock.json
MLB: ESPN gives the inning and half (no clock): rule = inning >= 9. Football/basketball/hockey: last regulation period + clock.
"""
import bisect, collections, json, sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
from polysweeper.collector import get_json  # noqa: E402

BASE = "https://site.api.espn.com/apis/site/v2/sports"
PATH = {"CFB": "football/college-football", "NFL": "football/nfl", "NHL": "hockey/nhl", "WNBA": "basketball/wnba", "NBA": "basketball/nba", "MLB": "baseball/mlb"}
REG = {"CFB": 4, "NFL": 4, "NHL": 3, "WNBA": 4, "NBA": 4, "MLB": 9}
cache = json.loads((ROOT / "lab/data/raw/row4_espn_cache.json").read_text())
fills = json.loads((ROOT / "lab/results/2026-10-08-late-bids-moneyline-32d-fills.json").read_text())
rows = [dict(zip(fills["cols"], r)) for r in fills["rows"]]
ev = {e["game"]: e for e in json.loads((ROOT / "lab/data/raw/usports_events.json").read_text()) if e["slug"] == e["game"]}
PC = ROOT / "lab/data/raw/row4_plays_cache.json"
plays_cache = json.loads(PC.read_text()) if PC.exists() else {}


def clock_s(c):
    c = (c or {}).get("displayValue") if isinstance(c, dict) else c
    if not c:
        return None
    try:
        if ":" in c:
            m, s = c.split(":")
            return int(m) * 60 + float(s)
        return float(c)
    except ValueError:
        return None


def load(g):
    if g in plays_cache:
        return g
    c = cache.get(g)
    if not c:
        return g
    sport = ev[g]["sport"]
    s = get_json(f"{BASE}/{PATH[sport]}/summary?event={c['espn']}") or {}
    plays = s.get("plays") or []
    if not plays:
        for d in (s.get("drives", {}).get("previous") or []):
            plays += d.get("plays", [])
    out = []
    for p in plays:
        if not p.get("wallclock"):
            continue
        per = (p.get("period") or {}).get("number")
        out.append((datetime.fromisoformat(p["wallclock"].replace("Z", "+00:00")).timestamp(), per, clock_s(p.get("clock")),
                    p.get("homeScore"), p.get("awayScore")))
    out.sort(key=lambda x: x[0])
    plays_cache[g] = out
    return g


games = sorted({r["game"] for r in rows if cache.get(r["game"])})
with ThreadPoolExecutor(4) as pool:
    list(pool.map(load, games))
PC.write_text(json.dumps(plays_cache))
print("games with plays:", sum(1 for g in games if plays_cache.get(g)), "of", len(games))

recs = []
for r in rows:
    g = r["game"]
    pl = plays_cache.get(g)
    if not pl:
        continue
    t = ev[g]["finished"] - r["secs_before_stamp"]
    i = bisect.bisect_right([p[0] for p in pl], t) - 1
    if i < 0:
        continue
    _, per, clk, hs, as_ = pl[i]
    if per is None or hs is None or as_ is None:
        continue
    home_won = cache[g]["home_won"]
    # side held by the buyer: winner unless the fill is on the loser
    buyer_home = home_won != bool(r["on_loser"])
    lead = (hs - as_) if buyer_home else (as_ - hs)
    recs.append({**r, "period": per, "clock": clk, "lead": lead})
print("fills with a game state:", len(recs), "of", len(rows))


def stat(sel):
    return {"fills": len(sel), "games": len({x["game"] for x in sel}), "loser_fills": sum(x["on_loser"] for x in sel),
            "loser_games": len({x["game"] for x in sel if x["on_loser"]})}


out = {"state_of_loser_fills": [{k: x[k] for k in ("sport", "game", "secs_before_stamp", "price", "period", "clock", "lead")} for x in recs if x["on_loser"]]}
print("loser fills with state:")
for x in out["state_of_loser_fills"]:
    print("  ", x)

rules = {}
timed = [x for x in recs if x["sport"] in ("CFB", "NFL", "NHL", "WNBA", "NBA")]
for X in (600, 480, 300, 240, 180, 120):
    rules[f"timed sports: last regulation period or OT, clock <= {X}s"] = stat([x for x in timed if x["period"] > REG[x["sport"]] or (x["period"] == REG[x["sport"]] and x["clock"] is not None and x["clock"] <= X)])
rules["timed sports: any fill"] = stat(timed)
mlb = [x for x in recs if x["sport"] == "MLB"]
for inn in (9, 8):
    rules[f"MLB inning >= {inn}"] = stat([x for x in mlb if x["period"] >= inn])
rules["MLB any fill"] = stat(mlb)
# lead rules on top of 'last 5 min'
def late(x, X=300):
    return x["period"] > REG[x["sport"]] or (x["period"] == REG[x["sport"]] and x["clock"] is not None and x["clock"] <= X)
rules["timed, clock<=300s, lead>=1 (buyer's side ahead)"] = stat([x for x in timed if late(x) and x["lead"] >= 1])
rules["timed, clock<=300s, buyer's side behind or level"] = stat([x for x in timed if late(x) and x["lead"] <= 0])
for sport, lead_min in (("CFB", 9), ("NFL", 9), ("NHL", 2), ("WNBA", 10), ("NBA", 10)):
    sel = [x for x in timed if x["sport"] == sport]
    rules[f"{sport}: lead >= {lead_min}"] = stat([x for x in sel if x["lead"] >= lead_min])
    rules[f"{sport}: lead < {lead_min}"] = stat([x for x in sel if x["lead"] < lead_min])
    rules[f"{sport}: all fills"] = stat(sel)
rules["MLB: lead >= 3 runs"] = stat([x for x in mlb if x["lead"] >= 3])
rules["MLB: lead < 3 runs"] = stat([x for x in mlb if x["lead"] < 3])
out["rules"] = rules
for k, v in rules.items():
    print(f"{k:62s} {v}")
(ROOT / "lab/results/2026-10-08-row4-clock.json").write_text(json.dumps(out, indent=1))
