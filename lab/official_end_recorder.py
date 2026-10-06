"""Measure, live, what is left to buy when WE first see the official MLB / NHL final (read-only, no orders).

For every MLB game today/tomorrow (and every NHL game, via the official NHL API; NHL record has no play end time, only t_seen): poll the official MLB Stats API (small schedule call, ~1 s in the 8th inning or later) and note the wall-clock
moment our poll first shows 'Final' (t_seen). Meanwhile Polymarket's market websocket (code/polysweeper/livefeed.py) records the top of every
main-event book and the big trades. About 150 s after t_seen we save, per game: t_seen, the official last-play end time (so our observation latency),
Polymarket's own `finishedTimestamp`, and for each main market the winner's best ask / shares in 0.96-0.995 from t_seen-60 s to t_seen+150 s plus trades.
Result: lab/data/raw/official_end/<utc date>.jsonl  ->  answers 'is anything left at 0.96-0.995 when we see the final, and for how long?'
  python3 lab/official_end_recorder.py [hours=6]       (Run during MLB playoff games; stop with Ctrl-C. Measuring only.)
"""
import json, os, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
from polysweeper.collector import get_json, GAMMA, parse_ts  # noqa: E402
from polysweeper.livefeed import LiveFeed  # noqa: E402

MLB = "https://statsapi.mlb.com/api"
OUT = ROOT / "lab/data/raw/official_end"
OUT.mkdir(parents=True, exist_ok=True)
feed = LiveFeed()
feed.start()
games = {}            # gamePk -> dict(slug, tokens, state, t_seen, saved)


def today_games():
    now = datetime.now(timezone.utc)
    found = []
    for d in {(now - timedelta(hours=8)).strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d"), (now + timedelta(hours=8)).strftime("%Y-%m-%d")}:
        s = get_json(f"{MLB}/v1/schedule?sportId=1&date={d}&hydrate=team,linescore") or {"dates": []}
        for x in s["dates"]:
            for g in x["games"]:
                found.append(g)
    return found


def register(g):
    pk = g["gamePk"]
    if pk in games or g.get("doubleHeader") in ("Y", "S"):      # doubleheaders: two games share one slug pattern, skip them
        return
    ab, hb = g["teams"]["away"]["team"].get("abbreviation", "").lower(), g["teams"]["home"]["team"].get("abbreviation", "").lower()
    slug = f"mlb-{ab}-{hb}-{g.get('officialDate')}"
    ev = get_json(f"{GAMMA}/events?slug={slug}")
    toks = {}
    if ev:
        for m in ev[0]["markets"]:
            try:
                ids = json.loads(m["clobTokenIds"])
            except (KeyError, TypeError, ValueError):
                continue
            for i, t in enumerate(ids):
                toks[str(t)] = {"cid": m["conditionId"], "type": m.get("sportsMarketType"), "q": m.get("question"), "idx": i}
    games[pk] = {"slug": slug, "tokens": toks, "t_seen": None, "saved": False, "state": None, "ev": ev[0]["id"] if ev else None}
    print(time.strftime("%H:%M:%S"), "registered", slug, "tokens", len(toks), flush=True)


NHL = "https://api-web.nhle.com/v1"


def nhl_today():
    now = datetime.now(timezone.utc)
    out = []
    for d in {(now - timedelta(hours=10)).strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d"), (now + timedelta(hours=10)).strftime("%Y-%m-%d")}:
        s = get_json(f"{NHL}/schedule/{d}") or {}
        for day in s.get("gameWeek", []):
            for g in day.get("games", []):
                out.append(g)
    return {g["id"]: g for g in out}.values()


def register_nhl(g):
    pk = "nhl%s" % g["id"]
    if pk in games:
        return
    st = datetime.fromisoformat(g["startTimeUTC"].replace("Z", "+00:00")).timestamp()
    names = [[g[k].get("commonName", {}).get("default", "").lower(), g[k].get("placeName", {}).get("default", "").lower()] for k in ("awayTeam", "homeTeam")]
    ev = None
    page = get_json(f"{GAMMA}/events?series_id=10346&closed=false&limit=100&order=startDate&ascending=true") or []
    for e in page:
        t = (e.get("title") or "").lower()
        es = parse_ts(e["startTime"]) if e.get("startTime") else 0
        if all(any(n and n in t for n in pair) for pair in names) and abs(es - st) < 4 * 3600:
            ev = e
            break
    toks = {}
    if ev:
        for m in ev["markets"]:
            try:
                ids = json.loads(m["clobTokenIds"])
            except (KeyError, TypeError, ValueError):
                continue
            for i, t in enumerate(ids):
                toks[str(t)] = {"cid": m["conditionId"], "type": m.get("sportsMarketType"), "q": m.get("question"), "idx": i}
    games[pk] = {"slug": ev["slug"] if ev else "nhl-unmatched-%s" % g["id"], "tokens": toks, "t_seen": None, "saved": False, "state": None, "ev": ev["id"] if ev else None, "kind": "nhl", "nhl_id": g["id"]}
    print(time.strftime("%H:%M:%S"), "registered NHL", games[pk]["slug"], "tokens", len(toks), flush=True)


def save(pk):
    g = games[pk]
    if g.get("kind") == "nhl":
        end = None
    else:
        f = get_json(f"{MLB}/v1.1/game/{pk}/feed/live?fields=liveData,plays,allPlays,about,endTime,gameData,status,detailedState") or {}
        ends = [p["about"]["endTime"] for p in f.get("liveData", {}).get("plays", {}).get("allPlays", []) if p["about"].get("endTime")]
        end = max(datetime.fromisoformat(x.replace("Z", "+00:00")).timestamp() for x in ends) if ends else None
    ev = get_json(f"{GAMMA}/events?slug={g['slug']}") or [{}]
    fin = ev[0].get("finishedTimestamp")
    ev = ev if ev[0] else [{}]
    final = {}
    for m in ev[0].get("markets", []):
        try:
            final[m["conditionId"]] = [float(x) for x in json.loads(m["outcomePrices"])]
        except (KeyError, TypeError, ValueError):
            pass
    t0 = g["t_seen"]
    markets = []
    for tok, meta in g["tokens"].items():
        px = final.get(meta["cid"])
        winner = bool(px) and px[meta["idx"]] == 1.0
        hist = feed.history(tok, t0 - 60, t0 + 150)
        trades = feed.trades(tok, t0 - 60, t0 + 150)
        if not (hist or trades):
            continue
        markets.append({"type": meta["type"], "q": (meta["q"] or "")[:60], "idx": meta["idx"], "winner": winner,
                        "book": [[round(r[0] - t0, 2), r[1], r[2], r[3], r[4]] for r in hist],   # (s vs t_seen, best ask, best bid, shares 0.96-0.995, shares 0.995-0.999)
                        "trades": [[round(r[0] - t0, 2), r[1], r[2], r[3]] for r in trades]})
    rec = {"slug": g["slug"], "pk": str(pk), "kind": g.get("kind", "mlb"), "t_seen": t0, "official_end": end, "our_latency_s": None if end is None else round(t0 - end, 1),
           "polymarket_finished": parse_ts(fin) if fin else None, "markets": markets, "feed": feed.status()}
    with open(OUT / (time.strftime("%Y-%m-%d", time.gmtime()) + ".jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
    g["saved"] = True
    print(time.strftime("%H:%M:%S"), "saved", g["slug"], "latency", rec["our_latency_s"], "markets with data", len(markets), flush=True)


stop = time.time() + float(sys.argv[1] if len(sys.argv) > 1 else 6) * 3600
last_list = 0
while time.time() < stop:
    now = time.time()
    if now - last_list > 120:
        for g in today_games():
            if g["status"]["abstractGameState"] in ("Live", "Preview"):
                register(g)
        for g in nhl_today():
            if g.get("gameState") in ("FUT", "PRE", "LIVE", "CRIT"):
                register_nhl(g)
        feed.set_tokens([t for g in games.values() for t in g["tokens"]])
        last_list, live_pks = now, None
    for pk, g in list(games.items()):
        if g["saved"]:
            continue
        if g["t_seen"] is not None:
            if now - g["t_seen"] >= 150:
                save(pk)
            continue
        if g.get("kind") == "nhl":
            l = get_json(f"{NHL}/gamecenter/{g['nhl_id']}/landing") or {}
            gs = l.get("gameState")
            per = (l.get("periodDescriptor") or {}).get("number", 0)
            g["state"] = ("Live" if gs in ("LIVE", "CRIT") else gs, 9 if per >= 3 else 0)       # 'inning' slot: 9 = third period or later (poll fast)
            st = "Final" if gs in ("FINAL", "OFF") else "Live"
        else:
            s = get_json(f"{MLB}/v1/schedule?gamePk={pk}&hydrate=linescore") or {"dates": []}
            got = [x for d in s["dates"] for x in d["games"]]
            if not got:
                continue
            st = got[0]["status"]["abstractGameState"]
            ls = got[0].get("linescore", {})
            inning = ls.get("currentInning", 0)
            g["state"] = (st, inning)
        if st == "Final":
            g["t_seen"] = time.time()
            print(time.strftime("%H:%M:%S"), "FINAL seen", g["slug"], flush=True)
    live8 = any(g["state"] and g["state"][0] == "Live" and g["state"][1] >= 8 and not g["t_seen"] for g in games.values())
    time.sleep(1.0 if live8 else 15.0)
