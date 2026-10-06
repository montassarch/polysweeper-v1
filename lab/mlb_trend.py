"""Trend: is the after-the-final-out supply in MLB (ask-hits on the winner at 0.96-0.995, public tape) shrinking over the season?

For sample weeks across 2026 (windows below): MLB schedule -> Polymarket main event (slug mlb-<away>-<home>-<date>) -> MLB official last-play end
-> tape by event id (newest first). Then fills per game in windows around the official final out.
  python3 lab/mlb_trend.py            (about 400 games, ~10 minutes; caches in lab/data/raw/mlb_trend_cache.json)
"""
import collections, json, statistics, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
from polysweeper.collector import get_json, GAMMA, parse_ts  # noqa: E402

MLB = "https://statsapi.mlb.com/api"
DATA = "https://data-api.polymarket.com"
WINDOWS = {"Apr 7-13": ("2026-04-07", "2026-04-13"), "Jun 9-15": ("2026-06-09", "2026-06-15"), "Jul 28-Aug 3": ("2026-07-28", "2026-08-03"),
           "Aug 25-31": ("2026-08-25", "2026-08-31"), "Sep 22-27": ("2026-09-22", "2026-09-27"), "Postseason Sep29-Oct5": ("2026-09-29", "2026-10-05")}
CACHE = ROOT / "lab/data/raw/mlb_trend_cache.json"
cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}


def days(a, b):
    d, end = datetime.fromisoformat(a), datetime.fromisoformat(b)
    while d <= end:
        yield d.strftime("%Y-%m-%d")
        d += timedelta(days=1)


def one(g):
    slug, pk, date = g
    if slug in cache:
        return cache[slug]
    r = None
    ev = get_json(f"{GAMMA}/events?slug={slug}")
    if ev and ev[0].get("finishedTimestamp"):
        e = ev[0]
        fin = parse_ts(e["finishedTimestamp"])
        f = get_json(f"{MLB}/v1.1/game/{pk}/feed/live?fields=liveData,plays,allPlays,about,endTime") or {}
        pl = [p["about"]["endTime"] for p in f.get("liveData", {}).get("plays", {}).get("allPlays", []) if p["about"].get("endTime")]
        if pl:
            end = max(datetime.fromisoformat(x.replace("Z", "+00:00")).timestamp() for x in pl)
            fm = {}
            for m in e["markets"]:
                try:
                    px = [float(x) for x in json.loads(m["outcomePrices"])]
                except (KeyError, TypeError, ValueError):
                    continue
                if sorted(px) == [0.0, 1.0]:
                    fm[m["conditionId"]] = px
            rows, off = [], 0
            while off <= 10000:
                page = get_json(f"{DATA}/trades?eventId={e['id']}&limit=500&offset={off}")
                if not isinstance(page, list) or not page:
                    break
                rows += page
                if len(page) < 500 or min(t["timestamp"] for t in page) < end - 300:
                    break
                off += 500
            fills = []
            for t in rows:
                px = fm.get(t["conditionId"])
                if not px or t["side"] != "BUY" or t["timestamp"] < end - 150 or t["timestamp"] > end + 900:
                    continue
                if px[t["outcomeIndex"]] == 1.0 and 0.96 <= float(t["price"]) < 0.995:
                    fills.append([round(t["timestamp"] - end, 1), float(t["price"]), float(t["size"])])
            r = {"end": end, "stamp_lag": fin - end, "fills": fills, "date": date}
    cache[slug] = r
    return r


games = []
for wname, (a, b) in WINDOWS.items():
    for d in days(a, b):
        s = get_json(f"{MLB}/v1/schedule?sportId=1&date={d}&hydrate=team") or {"dates": []}
        for x in s["dates"]:
            for g in x["games"]:
                if g["status"]["abstractGameState"] != "Final" or g.get("gameType") not in ("R", "F", "D", "L", "W"):
                    continue
                ab, hb = g["teams"]["away"]["team"].get("abbreviation", "").lower(), g["teams"]["home"]["team"].get("abbreviation", "").lower()
                games.append((wname, (f"mlb-{ab}-{hb}-{g.get('officialDate', d)}", g["gamePk"], d)))
print("games in the sample windows:", collections.Counter(w for w, _ in games))
t0 = time.time()
with ThreadPoolExecutor(max_workers=4) as pool:
    res = list(pool.map(lambda wg: one(wg[1]), games))
CACHE.write_text(json.dumps(cache))
print("done in", round(time.time() - t0), "s")
out = {}
for wname in WINDOWS:
    rs = [r for (w, _), r in zip(games, res) if w == wname and r]
    if not rs:
        print(wname, "no games matched"); continue
    nd = len({r["date"] for r in rs})
    row = {"games": len(rs), "days": nd, "stamp_lag_median_s": round(statistics.median(r["stamp_lag"] for r in rs), 1)}
    for lo, hi, name in ((-120, 0, "before_end_120s"), (0, 10, "0-10s"), (10, 30, "10-30s"), (30, 60, "30-60s"), (60, 900, "1-15min")):
        fl = [f for r in rs for f in r["fills"] if lo <= f[0] < hi and f[2] >= 5]
        row[name] = {"fills_per_game": round(len(fl) / len(rs), 2), "games_with_fill": len({id(r) for r in rs for f in r["fills"] if lo <= f[0] < hi and f[2] >= 5})}
    out[wname] = row
    print(f"{wname:24} games {len(rs):3} ({len(rs)/nd:4.1f}/day) stamp lag median {row['stamp_lag_median_s']:6.1f}s | fills/game (>=5 sh, 0.96-0.995): " +
          " ".join(f"{k} {row[k]['fills_per_game']:.2f}({row[k]['games_with_fill']})" for k in ("before_end_120s", "0-10s", "10-30s", "30-60s", "1-15min")))
(ROOT / "lab/results" / f"{time.strftime('%Y-%m-%d')}-mlb-trend.json").write_text(json.dumps(out, indent=1))
