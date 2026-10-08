"""Row 4 guard idea: how sure was ESPN's own win-probability model when a bid-side fill (a resting buy) happened?

Input : lab/results/2026-10-08-late-bids-moneyline-32d-fills.json (every taker SELL at 0.98+ in the last 30 min of 1,049 US games,
        with the flag "on_loser") and lab/data/raw/usports_events.json (score, start time per game).
Method: match each game to ESPN by final score + start time (same idea as lab/espn_official_end.py), read ESPN's play-by-play
        wallclock + win probability, and for each fill take the win probability of the side the buyer held at that moment
        (the winner for a normal fill, the loser for a fill on the loser) = the last probability published before the fill.
Output: lab/results/2026-10-08-row4-wp.json (guard table: fills / games / loser fills kept for WP thresholds, per sport and price band).
  python3 lab/row4_espn_wp.py
Read-only public ESPN endpoints. ESPN clocks are data-entry times (up to ~30 s early), fine for a 10-minute window.
"""
import bisect, collections, json, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
from polysweeper.collector import get_json  # noqa: E402

BASE = "https://site.api.espn.com/apis/site/v2/sports"
PATH = {"NFL": "football/nfl", "CFB": "football/college-football", "NHL": "hockey/nhl", "WNBA": "basketball/wnba", "NBA": "basketball/nba", "MLB": "baseball/mlb"}
fills = json.loads((ROOT / "lab/results/2026-10-08-late-bids-moneyline-32d-fills.json").read_text())
cols = fills["cols"]
rows = [dict(zip(cols, r)) for r in fills["rows"]]
ev = {e["game"]: e for e in json.loads((ROOT / "lab/data/raw/usports_events.json").read_text()) if e["slug"] == e["game"]}
CACHE = ROOT / "lab/data/raw/row4_espn_cache.json"
cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
_sb = {}


def scoreboard(sport, date):
    k = (sport, date)
    if k not in _sb:
        extra = "&groups=80" if sport == "CFB" else ""
        s = get_json(f"{BASE}/{PATH[sport]}/scoreboard?dates={date}&limit=400{extra}") or {}
        _sb[k] = s.get("events", [])
    return _sb[k]


def load_game(g):
    """-> dict(plays=[(wallclock, home_wp)], teams={home:name, away:name}, final=(away, home)) or None"""
    if g in cache:
        return cache[g]
    e = ev.get(g)
    res = None
    if e and e.get("score") and e.get("start"):
        try:
            a, h = [int(x) for x in e["score"].split("-")]
        except ValueError:
            a = h = None
        if a is not None:
            d0 = datetime.fromtimestamp(e["start"], timezone.utc)
            for dd in (d0, d0 - timedelta(days=1)):
                for x in scoreboard(e["sport"], dd.strftime("%Y%m%d")):
                    comp = x["competitions"][0]
                    cs = {c["homeAway"]: c for c in comp["competitors"]}
                    try:
                        sa, sh = int(cs["away"]["score"]), int(cs["home"]["score"])
                    except (KeyError, ValueError):
                        continue
                    gt = datetime.fromisoformat(x["date"].replace("Z", "+00:00")).timestamp()
                    if (sa, sh) == (a, h) and abs(gt - e["start"]) < 2700 and x["status"]["type"]["completed"]:
                        s = get_json(f"{BASE}/{PATH[e['sport']]}/summary?event={x['id']}") or {}
                        plays = s.get("plays") or []
                        if not plays:
                            for d in (s.get("drives", {}).get("previous") or []):
                                plays += d.get("plays", [])
                        wc = {p["id"]: datetime.fromisoformat(p["wallclock"].replace("Z", "+00:00")).timestamp() for p in plays if p.get("id") and p.get("wallclock")}
                        wp = sorted((wc[w["playId"]], float(w["homeWinPercentage"])) for w in (s.get("winprobability") or [])
                                    if w.get("playId") in wc and w.get("homeWinPercentage") is not None)
                        res = {"espn": x["id"], "wp": wp, "home_won": sh > sa, "final": [sa, sh]}
                        break
                if res:
                    break
    cache[g] = res
    return res


games = sorted({r["game"] for r in rows})
with ThreadPoolExecutor(max_workers=4) as pool:
    list(pool.map(load_game, games))
CACHE.write_text(json.dumps(cache))
have = {g for g in games if cache.get(g) and cache[g]["wp"]}
print("games with fills:", len(games), "matched with a win-probability series:", len(have), dict(collections.Counter(g.split("-")[0].upper() for g in have)))

out_rows = []
for r in rows:
    c = cache.get(r["game"])
    if not c or not c["wp"]:
        continue
    t = ev[r["game"]]["finished"] - r["secs_before_stamp"]
    ts = [w[0] for w in c["wp"]]
    i = bisect.bisect_right(ts, t) - 1
    if i < 0:
        continue
    home_wp = c["wp"][i][1]
    winner_wp = home_wp if c["home_won"] else 1 - home_wp
    bought = 1 - winner_wp if r["on_loser"] else winner_wp
    out_rows.append({**r, "wp_bought": round(bought, 4), "wp_age_s": round(t - ts[i])})
print("fills with a win-probability reading:", len(out_rows), "of", len(rows))


def table(sel, name):
    t = {"name": name, "all": {"fills": len(sel), "games": len({r["game"] for r in sel}), "losers": sum(r["on_loser"] for r in sel)}}
    for thr in (0.9, 0.95, 0.98, 0.99, 0.995, 0.999):
        k = [r for r in sel if r["wp_bought"] >= thr]
        t[f"wp>={thr}"] = {"fills": len(k), "games": len({r["game"] for r in k}), "losers": sum(r["on_loser"] for r in k)}
    return t


res = {"matched_games": len(have), "fills_with_wp": len(out_rows)}
res["overall"] = table(out_rows, "all fills >=0.98")
res["cheap_0.98_0.995"] = table([r for r in out_rows if r["price"] < 0.995], "price 0.98-0.995")
res["by_sport"] = {s: table([r for r in out_rows if r["sport"] == s], s) for s in sorted({r["sport"] for r in out_rows})}
res["wp_of_loser_fills"] = sorted([(r["sport"], r["game"], r["secs_before_stamp"], r["price"], r["wp_bought"], r["wp_age_s"]) for r in out_rows if r["on_loser"]])
# median WP of the bought side by price band (normal fills): is the market price in line with ESPN?
bands = [(0.98, 0.985), (0.985, 0.99), (0.99, 0.995), (0.995, 0.999), (0.999, 1.0)]
res["median_wp_by_price"] = {}
for lo, hi in bands:
    v = sorted(r["wp_bought"] for r in out_rows if lo <= r["price"] < hi and not r["on_loser"])
    if v:
        res["median_wp_by_price"][f"{lo}-{hi}"] = {"n": len(v), "p10": v[len(v) // 10], "median": v[len(v) // 2], "p90": v[9 * len(v) // 10]}
(ROOT / "lab/results/2026-10-08-row4-wp.json").write_text(json.dumps(res, indent=1))
print(json.dumps({k: res[k] for k in ("overall", "cheap_0.98_0.995", "wp_of_loser_fills", "median_wp_by_price")}, indent=1))
