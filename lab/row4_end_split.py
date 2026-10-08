"""Row 4: when, relative to the REAL end of the game (ESPN's last play), do resting-bid fills at 0.98+ happen, and when do they lose?

Needs lab/data/raw/row4_plays_cache.json + row4_espn_cache.json (made by lab/row4_clock.py) and the fills file from
lab/late_bids_moneyline.py. Output: lab/results/2026-10-08-row4-end-split.json
  python3 lab/row4_end_split.py
Findings it reproduces (2026-10-08, 32 days, ESPN-matched games): all loser fills were >= 16 real minutes before the end;
0 losers in 2,291 fills in the last 15 real minutes (424 games) and 0 in 2,153 fills after the last play; with the clock rule
"last regulation period/overtime and <= 60 s left" 0 losers in 1,679 fills (202 games), 537 of them before the end.
"""
import bisect, collections, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
plays = json.loads((ROOT / "lab/data/raw/row4_plays_cache.json").read_text())
ev = {e["game"]: e for e in json.loads((ROOT / "lab/data/raw/usports_events.json").read_text()) if e["slug"] == e["game"]}
fills = json.loads((ROOT / "lab/results/2026-10-08-late-bids-moneyline-32d-fills.json").read_text())
rows = [dict(zip(fills["cols"], r)) for r in fills["rows"]]
REG = {"CFB": 4, "NFL": 4, "WNBA": 4, "NBA": 4}
endt = {g: pl[-1][0] for g, pl in plays.items() if pl}
out = {}

# 1. stamp vs last ESPN play
lag = collections.defaultdict(list)
for g, t in endt.items():
    lag[ev[g]["sport"]].append(ev[g]["finished"] - t)
out["stamp_minus_last_play_seconds_median"] = {s: round(sorted(v)[len(v) // 2]) for s, v in lag.items()}

# 2. before / after the last play
pre = [r for r in rows if r["game"] in endt and ev[r["game"]]["finished"] - r["secs_before_stamp"] < endt[r["game"]]]
post = [r for r in rows if r["game"] in endt and ev[r["game"]]["finished"] - r["secs_before_stamp"] >= endt[r["game"]]]
def st(sel):
    return {"fills": len(sel), "games": len({r["game"] for r in sel}), "loser_fills": sum(r["on_loser"] for r in sel), "loser_games": len({r["game"] for r in sel if r["on_loser"]}),
            "shares": round(sum(r["shares"] for r in sel))}
out["before_last_play"] = st(pre)
out["after_last_play"] = st(post)
bands = [(0.98, 0.99), (0.99, 0.995), (0.995, 0.999), (0.999, 1.0)]
out["after_last_play_by_price"] = {f"{lo}-{hi}": st([r for r in post if lo <= r["price"] < hi]) for lo, hi in bands}
out["before_last_play_by_price"] = {f"{lo}-{hi}": st([r for r in pre if lo <= r["price"] < hi]) for lo, hi in bands}

# 3. hazard by real minutes before the last play (pre-end fills)
def mins(r):
    return (endt[r["game"]] - (ev[r["game"]]["finished"] - r["secs_before_stamp"])) / 60.0
buckets = [("0-5", 0, 5), ("5-10", 5, 10), ("10-15", 10, 15), ("15-20", 15, 20), ("20-25", 20, 25), ("25+", 25, 1e9)]
out["by_real_minutes_before_end"] = {n: st([r for r in pre if lo <= mins(r) < hi]) for n, lo, hi in buckets}
out["by_real_minutes_before_end_cheap_0.98_0.995"] = {n: st([r for r in pre if lo <= mins(r) < hi and r["price"] < 0.995]) for n, lo, hi in buckets}

# 4. clock rule: last regulation period or overtime, <= X seconds left
def state(g, t):
    pl = plays[g]
    i = bisect.bisect_right([p[0] for p in pl], t) - 1
    return pl[i] if i >= 0 else None
clock = {}
for X in (30, 60, 90, 120, 180, 300):
    sel = []
    for r in rows:
        g = r["game"]; s = r["sport"]
        if s not in REG or g not in endt:
            continue
        t = ev[g]["finished"] - r["secs_before_stamp"]
        sp = state(g, t)
        if not sp or sp[1] is None or sp[2] is None:
            continue
        if sp[1] > REG[s] or (sp[1] == REG[s] and sp[2] <= X):
            sel.append({**r, "pre": t < endt[g]})
    clock[f"clock<={X}s"] = {"all": st(sel), "before_last_play": st([r for r in sel if r["pre"]]),
                              "before_last_play_cheap_0.98_0.995": st([r for r in sel if r["pre"] and r["price"] < 0.995]),
                              "after_last_play_cheap_0.98_0.995": st([r for r in sel if not r["pre"] and r["price"] < 0.995])}
out["clock_rule_football_basketball"] = clock
(ROOT / "lab/results/2026-10-08-row4-end-split.json").write_text(json.dumps(out, indent=1))
print(json.dumps({k: out[k] for k in ("stamp_minus_last_play_seconds_median", "before_last_play", "after_last_play", "by_real_minutes_before_end")}, indent=1))
print(json.dumps(out["clock_rule_football_basketball"]["clock<=60s"], indent=1))
