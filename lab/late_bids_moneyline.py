"""Row 4 measurement (read-only): on finished US moneyline games (last ~6 days), public-tape taker SELLs into bids at 0.98+
in the last 30 min before Polymarket's 'finished' stamp (= fills a resting buy at 0.98/0.99 would have competed for),
split winner/loser per game, plus a crude queue proxy: shares sold into >=P bids per game vs 5.
  python3 lab/late_bids_moneyline.py"""
import json, sys, time, collections, statistics
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
from polysweeper.collector import get_json, GAMMA, parse_ts  # noqa: E402
DATA = "https://data-api.polymarket.com"
ev = json.load(open(ROOT / "lab/data/raw/usports_events.json"))
sport = {e["game"]: e["sport"] for e in ev}
def game_info(g):
    r = get_json(f"{GAMMA}/events?slug={g}")
    if not r: return None
    e = r[0]
    if not e.get("finishedTimestamp"): return None
    ms = [m for m in e["markets"] if m.get("sportsMarketType") == "moneyline"]
    if len(ms) != 1: return None
    m = ms[0]
    try: px = [float(x) for x in json.loads(m["outcomePrices"])]
    except Exception: return None
    if sorted(px) != [0.0, 1.0]: return None          # void / unresolved
    return {"game": g, "sport": sport[g], "fin": parse_ts(e["finishedTimestamp"]), "cid": m["conditionId"], "px": px}
def tape(gi):
    rows, off = [], 0
    while off <= 10000:
        try: page = get_json(f"{DATA}/trades?market={gi['cid']}&limit=500&offset={off}")
        except Exception: break
        if not isinstance(page, list) or not page: break
        rows += page
        if min(t["timestamp"] for t in page) < gi["fin"] - 1800 - 3600 or len(page) < 500: break
        off += 500; time.sleep(0.1)
    gi["trades"] = [t for t in rows if gi["fin"] - 1800 <= t["timestamp"] <= gi["fin"] + 900]
    gi["ntape"] = len(rows); gi["maxoff"] = off
    return gi
with ThreadPoolExecutor(6) as p:
    infos = [x for x in p.map(game_info, sorted(sport)) if x]
    games = list(p.map(tape, infos))
print("games with 1 resolved moneyline:", len(games), collections.Counter(g["sport"] for g in games))
out = {"games": len(games), "by_sport": dict(collections.Counter(g["sport"] for g in games)), "window": "30 min before finished stamp"}
for lo, name in ((0.98, ">=0.98"), (0.99, ">=0.99")):
    stats = {"fills": 0, "shares": 0, "on_losers": 0, "loser_shares": 0, "games_with_fill": 0, "games_loser_fill": 0, "per_game_sold": []}
    ge5 = 0; pre = {"fills_before_end": 0, "loser_before_end": 0}
    for g in games:
        sold = 0; hit = False; lost = False
        for t in g["trades"]:
            p_ = float(t["price"])
            if t["side"] != "SELL" or p_ < lo or p_ >= 0.9995 or t["timestamp"] >= g["fin"]: continue   # before the stamp only
            win = g["px"][t["outcomeIndex"]] == 1.0
            s = float(t["size"]); stats["fills"] += 1; stats["shares"] += s; sold += s; hit = True
            if not win: stats["on_losers"] += 1; stats["loser_shares"] += s; lost = True
        stats["games_with_fill"] += hit; stats["games_loser_fill"] += lost
        stats["per_game_sold"].append(round(sold))
        ge5 += sold >= 5
    ps = sorted(stats.pop("per_game_sold"))
    stats["games_with_>=5_sold"] = ge5
    stats["sold_per_game_median"] = statistics.median(ps); stats["sold_per_game_p75"] = ps[int(.75 * len(ps))]; stats["sold_per_game_max"] = ps[-1]
    stats["shares"] = round(stats["shares"]); stats["loser_shares"] = round(stats["loser_shares"])
    out["sells_into_bids_" + name] = stats
    print(name, stats)
# per sport + per-game loser detail
out["by_sport_ge98"] = {}
for g in games:
    n = l = 0
    for t in g["trades"]:
        p_ = float(t["price"])
        if t["side"] == "SELL" and 0.98 <= p_ < 0.9995 and t["timestamp"] < g["fin"]:
            n += 1; l += g["px"][t["outcomeIndex"]] != 1.0
    d = out["by_sport_ge98"].setdefault(g["sport"], {"fills": 0, "losers": 0}); d["fills"] += n; d["losers"] += l
# the taker BUY side too (what bots hit asks at 0.98+ before end), for comparison
b = {"fills": 0, "on_losers": 0, "games": 0}
for g in games:
    h = False
    for t in g["trades"]:
        p_ = float(t["price"])
        if t["side"] == "BUY" and 0.98 <= p_ < 0.9995 and t["timestamp"] < g["fin"]:
            b["fills"] += 1; h = True; b["on_losers"] += g["px"][t["outcomeIndex"]] != 1.0
    b["games"] += h
out["taker_buys_ge98_before_end"] = b
out["tape_truncated_games"] = sum(1 for g in games if g["maxoff"] >= 10000)
print(out["by_sport_ge98"], b, out["tape_truncated_games"])
(ROOT / "lab/results/2026-10-07-late-bids-moneyline.json").write_text(json.dumps(out, indent=1))
# extra: timing buckets of SELL fills >=0.98 before stamp, price split, and the one losing taker BUY
bk = collections.Counter(); ps_ = collections.Counter(); lose = []
for g in games:
    for t in g["trades"]:
        p_ = float(t["price"]); d = g["fin"] - t["timestamp"]
        if 0.98 <= p_ < 0.9995 and d > 0:
            if t["side"] == "SELL":
                bk["0-5m" if d < 300 else "5-15m" if d < 900 else "15-30m"] += 1
                ps_["0.98-0.989" if p_ < 0.99 else "0.99-0.998" if p_ < 0.999 else "0.999"] += 1
            elif g["px"][t["outcomeIndex"]] != 1.0:
                lose.append((g["game"], round(d), p_, float(t["size"])))
out["sell_fills_by_time_to_end"] = dict(bk); out["sell_fills_by_price"] = dict(ps_); out["losing_taker_buys"] = lose
print(dict(bk), dict(ps_), lose)
(ROOT / "lab/results/2026-10-07-late-bids-moneyline.json").write_text(json.dumps(out, indent=1))
