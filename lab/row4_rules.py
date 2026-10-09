"""Row 4: test LIVE-READABLE gates for resting buy bids at 0.98+ in US games on the long history built by lab/row4_history.py.

A gate may only use what a bot sees live: sport, period, game clock, lead of the side it would buy, who has the ball, inning/outs, the
price level. It may NOT use the stamp, the last play or who finally won (those are used only to LABEL the fill: loser or not).
Counting unit: fills AND games (a game is one coin toss: all fills in one game lose together).
  python3 lab/row4_rules.py            -> prints tables, writes lab/results/2026-10-09-row4-history-rules.json
"""
import collections, datetime, json, math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = json.loads((ROOT / "lab/data/raw/row4h/fills.json").read_text())
ROWS, GAMES = D["rows"], D["games"]
import os
DELTA = int(os.environ.get("STATE_DELTA", "0"))        # 0 = state at the fill second; 45 = state as it was 45 s earlier (safety for early ESPN stamps)
for _r in ROWS:
    _s = _r.get(f"s{DELTA}")
    if _s:
        _r.update(_s)
REG = {"CFB": 4, "NFL": 4, "NHL": 3, "WNBA": 4, "NBA": 4, "MLB": 9}
TIMED = ("CFB", "NFL", "NHL", "WNBA", "NBA")


def cp_upper(k, n, alpha=0.05):
    """one-sided Clopper-Pearson upper bound for k events in n trials"""
    if n == 0:
        return None
    if k == 0:
        return 1 - alpha ** (1.0 / n)
    lo, hi = k / n, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        cdf = sum(math.comb(n, i) * mid ** i * (1 - mid) ** (n - i) for i in range(k + 1))   # P(X<=k | p=mid)
        if cdf > alpha:
            lo = mid
        else:
            hi = mid
    return hi


def stat(sel, label=""):
    games = {x["game"] for x in sel}
    lg = {x["game"] for x in sel if x["on_loser"]}
    n_g = len(games)
    return {"fills": len(sel), "games": n_g, "loser_fills": sum(x["on_loser"] for x in sel), "loser_games": len(lg),
            "ub95_per_game": round(cp_upper(len(lg), n_g), 4) if n_g else None,
            "shares": round(sum(x["shares"] for x in sel))}


def buyer_team(x):
    return x["home_id"] if x["buyer_home"] else x["away_id"]


def late(x, X):
    """last regulation period (or overtime) and game clock <= X seconds"""
    if "period" not in x:
        return False
    if x["sport"] == "MLB":
        return False
    if x["period"] > REG[x["sport"]] and x["sport"] in ("CFB", "NFL"):
        return False                                        # football overtime is not "decided" while the other team still has a possession
    if x["sport"] == "NHL":
        # ESPN's NHL clock COUNTS UP from 0:00 (elapsed in the period); remaining = 1200 - clock in periods 1-3
        if x["period"] > 3:
            return True                                     # overtime: sudden death, a lead of 1+ means the game is over; shootout: undecided until the end
        return x["period"] == 3 and x["clock"] is not None and (1200 - x["clock"]) <= X
    return x["period"] >= REG[x["sport"]] and x["clock"] is not None and x["clock"] <= X


def mlb_outs_left_for_trailing(x):
    """outs the trailing team still has before the game ends in regulation (9 innings), given the state after the last play.
    ESPN: period = inning, ex = [top flag, outs after the play, scoring flag]. Extra innings: counted as 3 more outs for each side."""
    inn = x["period"]
    top, outs = x["ex"][0], x["ex"][1]
    if outs is None:
        return None
    outs = min(outs, 3)
    buyer_is_home = x["buyer_home"]
    trailing_home = not buyer_is_home
    final_inn = max(9, inn)
    # outs of the trailing team still to be recorded
    if trailing_home:
        # home bats in the bottom halves: this half still to come if top, partly gone if bottom
        left = (3 if top else 3 - outs) + 3 * (final_inn - inn)
        # if the home team trails, the game ends when the bottom of the final inning ends
    else:
        left = ((3 - outs) if top else 0) + 3 * (final_inn - inn)
        # away team trails: it bats in the top halves; the top of the current inning is the current half if top
        if not top:
            left += 0
    return left


def mlb_over(x):
    if x["sport"] != "MLB" or "period" not in x or x["lead"] < 1 or x["period"] < 9:
        return False
    top, outs = x["ex"][0], x["ex"][1]
    if outs is None:
        return False
    if top == 1:
        return outs >= 3 and bool(x["buyer_home"])          # top of 9th+ ended and the home team leads: no bottom half
    return bool(x["buyer_home"]) or outs >= 3               # bottom half: home leads (walk-off) or the half ended with the away team ahead


def gates():
    G = {}
    G["all fills (no gate)"] = lambda x: True
    # --- timed sports (clock) ---
    for X in (30, 60, 90, 120, 180, 300, 600):
        G[f"T{X}: last period/OT, clock<={X}s, buyer ahead"] = (lambda X: lambda x: x["sport"] in TIMED and late(x, X) and x["lead"] >= 1)(X)
    for X in (60, 120, 300):
        for L in (3, 5, 9, 10, 15):
            G[f"T{X}L{L}: ...clock<={X}s, lead>={L}"] = (lambda X, L: lambda x: x["sport"] in TIMED and late(x, X) and x["lead"] >= L)(X, L)
    # football: buyer's side has the ball (victory formation proxy)
    for X in (120, 300):
        G[f"FB{X}: football, clock<={X}s, buyer ahead AND has the ball"] = (lambda X: lambda x: x["sport"] in ("CFB", "NFL") and late(x, X) and x["lead"] >= 1 and x["ex"][0] == buyer_team(x))(X)
    # --- MLB ---
    for inn in (7, 8, 9):
        G[f"MLB inn>={inn}, buyer ahead"] = (lambda inn: lambda x: x["sport"] == "MLB" and "period" in x and x["period"] >= inn and x["lead"] >= 1)(inn)
    for inn, L in ((9, 2), (9, 3), (9, 4), (8, 3), (8, 4)):
        G[f"MLB inn>={inn}, lead>={L}"] = (lambda inn, L: lambda x: x["sport"] == "MLB" and "period" in x and x["period"] >= inn and x["lead"] >= L)(inn, L)
    # --- "decided" states: nothing left to play (cannot be reversed except by a review / untimed play) ---
    G["D1 timed: last period/OT, clock<=1s, buyer ahead"] = lambda x: x["sport"] in TIMED and late(x, 1) and x["lead"] >= 1
    G["D1b timed: last period/OT, clock<=5s, buyer ahead"] = lambda x: x["sport"] in TIMED and late(x, 5) and x["lead"] >= 1
    G["D2 MLB: game over (final out / walk-off) by ESPN state"] = mlb_over
    for k in (3, 6):
        G[f"MLB trailing team has <= {k} outs left, buyer ahead"] = (lambda k: lambda x: x["sport"] == "MLB" and "period" in x and x["lead"] >= 1 and (mlb_outs_left_for_trailing(x) or 99) <= k)(k)
    return G


def table(rows, G, price_lo=0.98, price_hi=0.9995, only_sports=None, min_state=True):
    out = {}
    for name, fn in G.items():
        sel = []
        for x in rows:
            if not (price_lo <= x["price"] < price_hi):
                continue
            if only_sports and x["sport"] not in only_sports:
                continue
            if name != "all fills (no gate)" and "period" not in x:
                continue
            try:
                if fn(x):
                    sel.append(x)
            except (TypeError, KeyError, IndexError):
                continue
        out[name] = stat(sel)
    return out


def show(title, tab):
    print("\n==", title)
    print(f"{'gate':64s} {'fills':>6s} {'games':>6s} {'loserF':>6s} {'loserG':>6s} {'ub95/g':>7s}")
    for k, v in tab.items():
        print(f"{k:64s} {v['fills']:6d} {v['games']:6d} {v['loser_fills']:6d} {v['loser_games']:6d} {str(v['ub95_per_game']):>7s}")


BANDS = [(0.95, 0.96), (0.96, 0.97), (0.97, 0.98), (0.98, 0.99), (0.99, 0.995), (0.995, 0.9995)]


def band_table(rows, fn, only_sports=None):
    out = {}
    for lo, hi in BANDS:
        sel = [x for x in rows if lo <= x["price"] < hi and (not only_sports or x["sport"] in only_sports) and "period" in x and _safe(fn, x)]
        out[f"{lo}-{hi}"] = stat(sel)
    return out


def _safe(fn, x):
    try:
        return bool(fn(x))
    except (TypeError, KeyError, IndexError):
        return False


def split_table(rows, fn, only_sports=None, cut="2026-03-01"):
    a = [x for x in rows if x["day"] < cut and (not only_sports or x["sport"] in only_sports) and "period" in x and _safe(fn, x) and 0.98 <= x["price"] < 0.9995]
    b = [x for x in rows if x["day"] >= cut and (not only_sports or x["sport"] in only_sports) and "period" in x and _safe(fn, x) and 0.98 <= x["price"] < 0.9995]
    return {"before " + cut: stat(a), "from " + cut: stat(b)}


def supply_table(rows, fn, sports, lo=0.98, hi=0.995):
    """how much cheap supply (taker sells into bids priced lo..hi) a gate leaves, per game and per active day of that sport"""
    sel = [x for x in rows if x["sport"] in sports and lo <= x["price"] < hi and "period" in x and _safe(fn, x)]
    games_all = [g for g in GAMES.values() if g["sport"] in sports and g["espn"]]
    days = {datetime.datetime.fromtimestamp(g["fin"], datetime.timezone.utc).strftime("%Y-%m-%d") for g in games_all}
    by_game = collections.defaultdict(float)
    for x in sel:
        by_game[x["game"]] += x["shares"]
    sh = sorted(by_game.values())
    return {"matched_games": len(games_all), "games_with_cheap_fill": len(by_game), "share_of_games": round(len(by_game) / max(1, len(games_all)), 3),
            "fills": len(sel), "fills_per_active_day": round(len(sel) / max(1, len(days)), 2), "games_per_active_day": round(len(by_game) / max(1, len(days)), 2),
            "active_days": len(days), "median_shares_per_game": (sh[len(sh) // 2] if sh else 0), "p25_shares": (sh[len(sh) // 4] if sh else 0),
            "games_with_ge5_shares": sum(1 for v in sh if v >= 5), "loser_games": len({x["game"] for x in sel if x["on_loser"]})}


if __name__ == "__main__":
    ok_rows = [r for r in ROWS if r["ok"]]
    print("fills", len(ROWS), "complete tape", len(ok_rows), "with state", sum(1 for r in ok_rows if "period" in r),
          "games", len(GAMES), "matched", sum(1 for g in GAMES.values() if g["espn"]))
    G = gates()
    result = {"coverage": {"fills": len(ROWS), "with_state": sum(1 for r in ok_rows if "period" in r), "games_with_fills": len(GAMES),
                           "games_matched_espn": sum(1 for g in GAMES.values() if g["espn"]),
                           "by_sport": {s: [sum(1 for g in GAMES.values() if g["sport"] == s), sum(1 for g in GAMES.values() if g["sport"] == s and g["espn"])] for s in REG}}}
    for sport in ("CFB", "NFL", "NBA", "WNBA", "NHL", "MLB"):
        t = table(ok_rows, G, only_sports=[sport])
        t = {k: v for k, v in t.items() if v["fills"]}
        result[sport] = t
        show(f"{sport} (fills >=0.98, 0.98 <= price < 0.9995)", t)
    # price ladder and time split for the main candidate gates
    cand = {"T60": gates()["T60: last period/OT, clock<=60s, buyer ahead"], "T120": gates()["T120: last period/OT, clock<=120s, buyer ahead"],
            "D1 clock<=1s": gates()["D1 timed: last period/OT, clock<=1s, buyer ahead"], "D1b clock<=5s": gates()["D1b timed: last period/OT, clock<=5s, buyer ahead"],
            "MLB game over": mlb_over}
    result["bands"], result["split"] = {}, {}
    for name, fn in cand.items():
        for sports in (["CFB", "NFL"], ["NBA", "WNBA"], ["NHL"], ["MLB"]):
            if name.startswith("MLB") != (sports == ["MLB"]):
                continue
            key = name + " | " + "/".join(sports)
            result["bands"][key] = band_table(ok_rows, fn, sports)
            result["split"][key] = split_table(ok_rows, fn, sports)
            print("\n--", key)
            for b, v in result["bands"][key].items():
                print(f"   {b:13s} fills {v['fills']:5d} games {v['games']:4d} loserF {v['loser_fills']:3d} loserG {v['loser_games']:3d}")
            print("   split:", {k: (v['fills'], v['games'], v['loser_games']) for k, v in result["split"][key].items()})
    result["supply"] = {}
    for name, fn in cand.items():
        for sports in (["CFB", "NFL"], ["NBA", "WNBA"], ["NHL"], ["MLB"]):
            if name.startswith("MLB") != (sports == ["MLB"]):
                continue
            key = name + " | " + "/".join(sports)
            result["supply"][key] = supply_table(ok_rows, fn, sports)
            print("supply", key, result["supply"][key])
    # loser fills: was the bought side still ahead when it filled? (the flip came later) -- all gates off
    L = [x for x in ok_rows if x["on_loser"] and "period" in x]
    result["loser_fill_state"] = {"loser_fills_with_state": len(L), "bought_side_ahead": sum(1 for x in L if x["lead"] >= 1),
                                  "tied": sum(1 for x in L if x["lead"] == 0), "behind": sum(1 for x in L if x["lead"] < 0)}
    print("loser fills, state at the fill:", result["loser_fill_state"])
    (ROOT / f"lab/results/2026-10-09-row4-history-rules{'-d45' if DELTA else ''}.json").write_text(json.dumps(result, indent=1))
