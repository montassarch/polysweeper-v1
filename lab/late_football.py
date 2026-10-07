"""Scoreboard row 8: football, team leading by 2+ goals at minute 88+ (owner idea 2026-10-07).

Part A (safety, ESPN only, many seasons): how often does a team leading at minute T fail to win in
regular time? By lead size (1, 2, 3+) and T (80, 85, 88). Cup ties that went to extra time are skipped
(Polymarket settles on 90 minutes; ESPN's final would include extra time).
Part B (fills, recent Polymarket matches): for matches where a team led by 2+ (and by 1, for comparison)
at minute 88, what traded on that team's "Will X win?" YES token from minute 88 to 2 min after full time:
shares at 0.95-0.99, 0.99-0.995 and above 0.995. Any trade = an order a buyer could have filled at that
price (a taker or a resting bid).

Read-only, standard library. Raw downloads cached in lab/data/raw/football/ (git-ignored).
Usage: python lab/late_football.py [partA_seasons_start=2024-08-01] [partB_days=45]
"""
import json, re, sys, time, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "code"))
from polysweeper.results_espn import same_club  # noqa: E402

UA = {"User-Agent": "polysweeper-research/0.1 (read-only data collection)"}
CACHE = ROOT / "data" / "raw" / "football"
CACHE.mkdir(parents=True, exist_ok=True)
OUT = ROOT / "results" / "late-football.json"
# ESPN code -> Polymarket series id (Polymarket's leagues, from collector.leagues())
LEAGUES = {"eng.1": 10188, "esp.1": 10193, "ger.1": 10194, "ita.1": 10203, "fra.1": 10195,
           "uefa.champions": 10204, "uefa.europa": 10209, "por.1": 10330, "ned.1": 10286}
# extra leagues for the safety count only (no Polymarket match-up needed)
SAFETY_ONLY = ["eng.2", "esp.2", "ger.2", "ita.2", "fra.2", "usa.1", "bra.1", "arg.1", "mex.1", "tur.1", "bel.1", "sco.1"]


def get(url, cache_name=None, tries=4):
    if cache_name:
        p = CACHE / cache_name
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                data = json.load(r)
            if cache_name:
                (CACHE / cache_name).write_text(json.dumps(data), encoding="utf-8")
            time.sleep(0.15)
            return data
        except Exception as e:  # noqa: BLE001
            if "400" in str(e) or "404" in str(e):
                return None
            time.sleep(2 ** i)
    return None


def minute(display):
    """"88'" -> (88, 0); "90'+3'" -> (90, 3)."""
    m = re.findall(r"\d+", display or "")
    return (int(m[0]), int(m[1]) if len(m) > 1 else 0) if m else None


def goals_of(comp):
    """List of (minute tuple, team index 0/1) checked against the final score; None if it doesn't add up."""
    teams = comp["competitors"]
    ids = [t["id"] for t in teams]
    final = [int(t.get("score") or 0) for t in teams]
    gl = []
    for d in comp.get("details", []):
        if not d.get("scoringPlay"):
            continue
        mt = minute(d.get("clock", {}).get("displayValue"))
        tid = (d.get("team") or {}).get("id")
        if mt is None or tid not in ids:
            return None
        gl.append((mt, ids.index(tid)))
    cnt = [sum(1 for _, k in gl if k == i) for i in (0, 1)]
    return gl if cnt == final else None


def score_at(gl, T):
    s = [0, 0]
    for (base, extra), k in gl:
        if base < T:
            s[k] += 1
    return s


def daterange(a, b):
    d = a
    while d <= b:
        yield d
        d += timedelta(days=1)


def scoreboard(code, day):
    ymd = day.strftime("%Y%m%d")
    fresh = day > datetime.now(timezone.utc) - timedelta(days=2)
    return get(f"https://site.api.espn.com/apis/site/v2/sports/soccer/{code}/scoreboard?dates={ymd}",
               None if fresh else f"sb_{code}_{ymd}.json")


def part_a(start, end):
    stats = {}  # (T, lead) -> [n, won, drew, lost]
    cases = []
    seen = set()
    for code in list(LEAGUES) + SAFETY_ONLY:
        for day in daterange(start, end):
            sb = scoreboard(code, day)
            for ev in (sb or {}).get("events", []):
                st = ev["status"]["type"]
                if ev["id"] in seen or not st.get("completed") or st.get("name") not in ("STATUS_FULL_TIME", "STATUS_FINAL"):
                    continue
                seen.add(ev["id"])
                comp = ev["competitions"][0]
                gl = goals_of(comp)
                if gl is None:
                    continue
                final = score_at(gl, 999)
                for T in (80, 85, 88):
                    s = score_at(gl, T)
                    lead = abs(s[0] - s[1])
                    if lead == 0:
                        continue
                    lead_k = min(lead, 3)
                    ldr = 0 if s[0] > s[1] else 1
                    res = "won" if final[ldr] > final[1 - ldr] else "drew" if final[0] == final[1] else "lost"
                    r = stats.setdefault(f"T{T}_lead{lead_k}", {"n": 0, "won": 0, "drew": 0, "lost": 0})
                    r["n"] += 1
                    r[res] += 1
                    if res != "won" and lead >= 2:
                        cases.append({"league": code, "match": ev["name"], "date": ev["date"][:10], "T": T,
                                      "score_at_T": s, "final": final})
        print("part A", code, "matches so far", len(seen), flush=True)
    return {"matches": len(seen), "stats": stats, "lead2_failures": cases}


def poly_events(series, since):
    out, off = [], 0
    while True:
        b = get(f"https://gamma-api.polymarket.com/events?series_id={series}&closed=true&limit=50&offset={off}"
                f"&order=endDate&ascending=false")
        if not b:
            break
        out += b
        last = b[-1].get("endDate") or ""
        if len(b) < 50 or last[:10] < since.strftime("%Y-%m-%d"):
            break
        off += 50
    return out


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def key_times(code, eid):
    s = get(f"https://site.api.espn.com/apis/site/v2/sports/soccer/{code}/summary?event={eid}", f"sum_{code}_{eid}.json")
    if not s:
        return None
    ke = [k for k in s.get("keyEvents", []) if k.get("wallclock")]
    h2 = [k for k in ke if (k.get("period") or {}).get("number") == 2 and k.get("type", {}).get("type") in ("kickoff", "start-2nd-half", "halftime")]
    pts = [(k["clock"]["value"], ts(k["wallclock"])) for k in ke if (k.get("period") or {}).get("number") == 2 and k.get("clock")]
    ft = [ts(k["wallclock"]) for k in ke if k.get("type", {}).get("type") in ("end-regular-time", "full-time", "end-of-game", "end-match")]
    if not pts:
        return None
    # minute 88 = clock value 5280 s; take the closest second-half event and shift by the clock difference
    c, w = min(pts, key=lambda p: abs(p[0] - 5280))
    t88 = w + (5280 - c)
    tft = max(ft) if ft else max(w for _, w in pts)
    return t88, tft, bool(ft), bool(h2)


def trades(cond, t_from):
    out, off = [], 0
    while off <= 9500:
        b = get(f"https://data-api.polymarket.com/trades?market={cond}&limit=500&offset={off}")
        if not b:
            break
        out += b
        if len(b) < 500 or min(x["timestamp"] for x in b) < t_from:
            break
        off += 500
    return out


def part_b(days):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = []
    for code, series in LEAGUES.items():
        evs = poly_events(series, since)
        for day in daterange(since, datetime.now(timezone.utc) - timedelta(days=1)):
            for ev in (scoreboard(code, day) or {}).get("events", []):
                if not ev["status"]["type"].get("completed") or ev["status"]["type"].get("name") not in ("STATUS_FULL_TIME", "STATUS_FINAL"):
                    continue
                comp = ev["competitions"][0]
                gl = goals_of(comp)
                if gl is None:
                    continue
                s = score_at(gl, 88)
                lead = abs(s[0] - s[1])
                if lead == 0:
                    continue
                ldr = 0 if s[0] > s[1] else 1
                final = score_at(gl, 999)
                names = [t["team"]["displayName"] for t in comp["competitors"]]
                t0 = ts(ev["date"])
                pe = [e for e in evs if e.get("startTime") and abs(ts(e["startTime"]) - t0) < 3 * 3600
                      and any(m.get("sportsMarketType") == "moneyline" for m in e.get("markets", []))
                      and all(any(same_club(n, w) for w in re.split(r" vs\.? ", e.get("title", ""))) for n in names)]
                if not pe:
                    continue
                mk = [m for m in pe[0].get("markets", []) if m.get("sportsMarketType") == "moneyline"
                      and not (m.get("groupItemTitle") or "").lower().startswith("draw")
                      and same_club(names[ldr], (m.get("groupItemTitle") or ""))]
                if not mk:
                    continue
                kt = key_times(code, ev["id"])
                if not kt:
                    continue
                t88, tft, has_ft, _ = kt
                tr = trades(mk[0]["conditionId"], t88 - 60)
                win = final[ldr] > final[1 - ldr]
                band = {"0.95-0.99": 0.0, "0.99-0.995": 0.0, ">0.995": 0.0, "<0.95": 0.0}
                for x in tr:
                    if not (t88 <= x["timestamp"] <= tft + 120):
                        continue
                    # YES and NO share one book: a NO trade at q is a YES trade at 1 - q
                    p = float(x["price"]) if str(x.get("outcome")).lower() == "yes" else 1 - float(x["price"])
                    k = "<0.95" if p < 0.95 else "0.95-0.99" if p < 0.99 else "0.99-0.995" if p <= 0.995 else ">0.995"
                    band[k] += float(x["size"])
                rows.append({"league": code, "match": ev["name"], "date": ev["date"][:10], "lead_at_88": lead,
                             "leader_won": win, "window_min": round((tft + 120 - t88) / 60, 1), "ft_marked": has_ft,
                             "shares": {k: round(v) for k, v in band.items()}})
        print("part B", code, "matched", len(rows), flush=True)
    return rows


def main():
    a_start = datetime.fromisoformat(sys.argv[1] if len(sys.argv) > 1 else "2024-08-01").replace(tzinfo=timezone.utc)
    b_days = int(sys.argv[2]) if len(sys.argv) > 2 else 45
    b = part_b(b_days)
    res = {"made": datetime.now(timezone.utc).isoformat(timespec="seconds"), "part_b": b}
    OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")
    a = part_a(a_start, datetime.now(timezone.utc) - timedelta(days=1))
    res["part_a"] = a
    OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(a["stats"], indent=1))
    for lead in (1, 2):
        sel = [r for r in b if (r["lead_at_88"] >= 2) == (lead == 2)]
        tot = {k: sum(r["shares"][k] for r in sel) for k in ("<0.95", "0.95-0.99", "0.99-0.995", ">0.995")}
        print(f"part B lead {'2+' if lead == 2 else '1'}: matches {len(sel)}, leader lost/drew {sum(not r['leader_won'] for r in sel)},"
              f" matches with 5+ shares at 0.95-0.99 {sum(r['shares']['0.95-0.99'] >= 5 for r in sel)}, shares {tot}")


if __name__ == "__main__":
    main()
