"""Is the owner's PC slow to notice 365Scores' "match over"? A fast, parallel probe from the cloud (ps-researcher, 2026-10-10).

Why: the shadow rule final_bid measured 365Scores' final a median ~70 s before Polymarket's ended flag on 12 tennis matches
(plus 13 chances where the flag was already out), while the laptop feed race measured ~167 s on 187 matches. If a fast
probe sees ~165 s on the same kind of matches, the PC's polling thread is the slow part (it asks games one after another).

What it does (read-only, public endpoints, polite: list every 4 s, detail only for live games every 4 s, Gamma per match every 6 s):
  - 365Scores tennis list (games/current, sports=3): first time a game's list status is "over" (statusGroup 4, text Ended / Just Ended)
  - 365Scores per-game detail (the endpoint the PC uses): first time it says "over"
  - Polymarket Gamma event (ATP / WTA series): first time `ended` is true, and Polymarket's own `finishedTimestamp`
  - leads = Polymarket moment minus 365 moment; one JSON line per finished match -> lab/data/raw/s365_lag_probe.jsonl
Usage: python3 lab/s365_lag_probe.py [hours=2.5]  (summary every 10 minutes -> lab/results/2026-10-10-s365-lag-probe.json)
"""
import datetime, json, os, statistics, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
from polysweeper.collector import GAMMA, parse_ts  # noqa: E402
from polysweeper.finalbid import side_map, final_365  # noqa: E402

S365 = "https://webws.365scores.com/web"
UA = {"User-Agent": "polysweeper-research/0.1 (read-only data collection)"}
OUT_RAW = ROOT / "lab/data/raw/s365_lag_probe.jsonl"
OUT_SUM = ROOT / "lab/results/2026-10-10-s365-lag-probe.json"
OUT_RAW.parent.mkdir(parents=True, exist_ok=True)
SERIES = (10365, 10366)
POOL = ThreadPoolExecutor(max_workers=10)


def fetch(url, timeout=12):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
            return json.load(r)
    except Exception:
        return None


def pm_events():
    out = []
    for sid in SERIES:
        r = fetch(f"{GAMMA}/events/keyset?series_id={sid}&closed=false&limit=100&order=startDate&ascending=true")
        for e in (r or {}).get("events", []) or []:
            st = parse_ts(e["startTime"]) if e.get("startTime") else None
            if st is None or abs(st - time.time()) > 8 * 3600:
                continue
            ms = [m for m in e.get("markets", []) if m.get("sportsMarketType") == "moneyline"]
            if len(ms) != 1:
                continue
            try:
                outs = json.loads(ms[0]["outcomes"])
            except Exception:
                continue
            if len(outs) != 2:
                continue
            out.append({"id": e["id"], "title": e.get("title"), "start": st, "outs": outs, "ended": e.get("ended") is True,
                        "finished": e.get("finishedTimestamp")})
    return out


def pm_one(eid):
    r = fetch(f"{GAMMA}/events?id={eid}")
    if isinstance(r, list) and r:
        e = r[0]
        return e.get("ended") is True, e.get("finishedTimestamp")
    return None, None


def main(hours):
    t_end = time.time() + hours * 3600
    games = {}      # 365 game id -> record
    pm = {}         # pm event id -> record
    done = []
    last_disc = 0.0
    last_sum = 0.0
    last_dbg = 0.0
    live_ids = set()
    while time.time() < t_end:
        loop = time.time()
        try:
            if loop - last_disc > 120:
                for e in pm_events():
                    pm.setdefault(e["id"], dict(e, t_pm=None, t_seen=loop))
                last_disc = loop
            d = fetch(f"{S365}/games/current/?appTypeId=5&langId=1&timezoneName=UTC&userCountryId=1&sports=3")
            now = time.time()
            for g in (d or {}).get("games", []):
                gid = g["id"]
                r = games.setdefault(gid, {"id": gid, "first_status": g.get("statusGroup"), "t_list": None, "t_detail": None, "pm": None,
                                           "home": (g.get("homeCompetitor") or {}).get("name"), "away": (g.get("awayCompetitor") or {}).get("name"),
                                           "start": g.get("startTime"), "last_poll": 0.0, "live_seen": False})
                if g.get("statusGroup") == 3:
                    r["live_seen"] = True
                if r["live_seen"] and g.get("statusGroup") == 4 and r["t_list"] is None:
                    r["t_list"] = now
                    r["list_status"] = g.get("statusText")
                    r["list_score"] = ((g.get("homeCompetitor") or {}).get("score"), (g.get("awayCompetitor") or {}).get("score"))
                    r["list_windesc"] = g.get("winDescription")
            # detail polling of live games (and of games whose list says over but detail not yet)
            todo = [r for r in games.values() if r["live_seen"] and r["t_detail"] is None and now - r["last_poll"] >= 4]
            for r in todo:
                r["last_poll"] = now
            for r, dd in zip(todo, POOL.map(lambda r: fetch(f"{S365}/game/?appTypeId=5&langId=1&timezoneName=UTC&userCountryId=1&gameId={r['id']}"), todo)):
                f = final_365((dd or {}).get("game"))
                if f and r["t_detail"] is None:
                    r["t_detail"] = time.time()
                    r["detail_status"] = f[3]
            # match 365 games to Polymarket events (once)
            for r in games.values():
                if r["pm"] is None and r["live_seen"]:
                    st = parse_ts(r["start"]) if r["start"] else None
                    for e in pm.values():
                        if st and abs(e["start"] - st) < 4 * 3600 and side_map(e["outs"], r["home"], r["away"]):
                            r["pm"] = e["id"]
                            break
            # Polymarket ended flags for matched, 365-finished games
            watch = [r for r in games.values() if r["pm"] and (r["t_list"] or r["t_detail"]) and pm[r["pm"]]["t_pm"] is None]
            for r, (ended, fin) in zip(watch, POOL.map(lambda r: pm_one(r["pm"]), watch)):
                if ended:
                    pm[r["pm"]]["t_pm"] = time.time()
                    pm[r["pm"]]["finished"] = fin
            # finished records
            for r in list(games.values()):
                if r["pm"] and pm[r["pm"]]["t_pm"] and (r["t_list"] or r["t_detail"]) and not r.get("saved"):
                    e = pm[r["pm"]]
                    fin = parse_ts(e["finished"]) if e.get("finished") else None
                    t365 = min(x for x in (r["t_list"], r["t_detail"]) if x)
                    rec = {"title": e["title"], "id365": r["id"], "list_status": r.get("list_status"), "detail_status": r.get("detail_status"),
                           "t_list": r["t_list"], "t_detail": r["t_detail"], "t_pm_seen": e["t_pm"], "pm_finished_ts": fin,
                           "detail_minus_list_s": None if not (r["t_list"] and r["t_detail"]) else round(r["t_detail"] - r["t_list"], 1),
                           "lead_list_s": None if not r["t_list"] else round(e["t_pm"] - r["t_list"], 1),
                           "lead_detail_s": None if not r["t_detail"] else round(e["t_pm"] - r["t_detail"], 1),
                           "lead_vs_stamp_s": None if not fin else round(fin - t365, 1),
                           "windesc": r.get("list_windesc"), "score": r.get("list_score")}
                    r["saved"] = True
                    done.append(rec)
                    with open(OUT_RAW, "a") as fh:
                        fh.write(json.dumps(rec) + "\n")
                    print(time.strftime("%H:%M:%S"), "match", e["title"][:55], "lead(list/detail)", rec["lead_list_s"], rec["lead_detail_s"],
                          "vs stamp", rec["lead_vs_stamp_s"], flush=True)
            if now - last_dbg > 300:
                last_dbg = now
                print(time.strftime("%H:%M:%S"), "tracking", len(games), "live_seen", sum(1 for r in games.values() if r["live_seen"]),
                      "365-over seen (list/detail)", sum(1 for r in games.values() if r["t_list"]), sum(1 for r in games.values() if r["t_detail"]),
                      "matched to PM", sum(1 for r in games.values() if r["pm"]), "PM events known", len(pm), "finished", len(done), flush=True)
            if now - last_sum > 600 and done:
                last_sum = now
                write_summary(done)
        except Exception as exc:
            print("loop error", type(exc).__name__, exc, flush=True)
        time.sleep(max(0.5, 4 - (time.time() - loop)))
    write_summary(done)


def write_summary(done):
    def stat(key):
        v = sorted(x[key] for x in done if x.get(key) is not None)
        if not v:
            return None
        return {"n": len(v), "median": round(statistics.median(v), 1), "p10": round(v[int(0.1 * (len(v) - 1))], 1),
                "p25": round(v[int(0.25 * (len(v) - 1))], 1), "p75": round(v[int(0.75 * (len(v) - 1))], 1), "p90": round(v[int(0.9 * (len(v) - 1))], 1)}
    out = {"updated": datetime.datetime.utcnow().isoformat() + "Z", "matches": len(done), "lead_list_s": stat("lead_list_s"),
           "lead_detail_s": stat("lead_detail_s"), "lead_vs_stamp_s": stat("lead_vs_stamp_s"), "detail_minus_list_s": stat("detail_minus_list_s")}
    OUT_SUM.write_text(json.dumps(out, indent=1))
    print(json.dumps(out), flush=True)


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 2.5)
