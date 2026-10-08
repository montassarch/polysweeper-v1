"""Score-source coverage (read-only): for every Polymarket sports match starting in the next ~2 days, which free
score source also lists it (same two teams, start within 3 h)?

Polymarket side: active leagues from lab/results/source-atlas-leagues.json (run source_atlas.py first).
Sources tried (all free, no key):
  espn      site.api.espn.com scoreboards, every league ESPN has (soccer 219, basketball, hockey, baseball, ...)
  s365      365Scores (Israel) all games per day, 9 sports
  livescore LiveScore (UK) all games per day: soccer, basketball, hockey, tennis, cricket
  bo3       bo3.gg (CS2, Dota 2, LoL, Valorant ...) upcoming/current
  lolesp    LoL Esports official schedule
Output: lab/results/source-coverage.json (per league: matches, % found per source) + unmatched examples.
  py lab/source_coverage.py [hours_ahead=48]
"""
import json, re, sys, time, unicodedata, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
from polysweeper.collector import get_json, GAMMA, parse_ts  # noqa: E402

RES = ROOT / "lab/results"
BROWSER = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/128.0 Safari/537.36"}
PLAIN = {"User-Agent": "polysweeper-research/0.1"}   # ESPN returns 403 to a bare browser UA from Python
STOP = {"fc", "cf", "sc", "ac", "afc", "club", "de", "the", "cd", "ca", "fk", "sk", "if", "bk", "ud", "sd", "rc",
        "us", "as", "ss", "esports", "esport", "gaming", "team", "basketball", "hockey", "baseball", "football",
        "women", "w", "1", "2", "ii", "u21", "u23", "u19", "u20", "calcio", "spor", "kulubu", "sv", "vfb", "vfl",
        "tsg", "1.", "fsv", "real", "atletico", "deportivo", "club", "cs", "ks", "nk", "hnk", "gnk", "fcsb", "jk"}


def fetch(url, headers=None, timeout=20):
    try:
        req = urllib.request.Request(url, headers=headers or BROWSER)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except Exception:  # noqa: BLE001
        return None


def toks(name):
    n = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    return [w for w in re.split(r"[^a-z0-9]+", n) if w and w not in STOP]


def same_team(a, b):
    ta, tb = toks(a), toks(b)
    if not ta or not tb:
        return False
    ja, jb = "".join(ta), "".join(tb)
    if ja == jb or (min(len(ja), len(jb)) >= 4 and (ja in jb or jb in ja)):
        return True
    return any(len(w) >= 4 and w in tb for w in ta)


def pm_events(hours):
    lg = json.loads((RES / "source-atlas-leagues.json").read_text(encoding="utf-8"))
    now = time.time()
    out = []

    def one(l):
        rows, off = [], 0
        for sid in str(l.get("series") or "").split(","):
            off = 0
            while sid.strip() and off < 1000:
                page = get_json(f"{GAMMA}/events?series_id={sid.strip()}&active=true&closed=false&limit=100&offset={off}") or []
                for e in page:
                    st = parse_ts(e.get("startTime"))
                    if not st or not (now - 6 * 3600 <= st <= now + hours * 3600):
                        continue
                    teams = None
                    ml = next((m for m in e.get("markets", []) if m.get("sportsMarketType") == "moneyline"), None)
                    if ml:
                        o = json.loads(ml.get("outcomes") or "[]")
                        if len(o) == 2 and "Draw" not in o:
                            teams = o
                    if not teams:
                        t = re.sub(r"^[^:]*:\s*", "", e["title"])
                        t = re.sub(r"\s*\(.*?\)|\s+-\s+.*$", "", t)
                        parts = re.split(r"\s+vs\.?\s+|\s+v\s+|\s+@\s+", t)
                        teams = parts if len(parts) == 2 else None
                    if teams:
                        rows.append({"league": l["sport"], "title": e["title"], "start": st, "teams": teams})
                if len(page) < 100:
                    break
                off += 100
        return rows

    with ThreadPoolExecutor(8) as ex:
        for rows in ex.map(one, [l for l in lg if l["next_7d"]]):
            out += rows
    return out


# ---------- sources: each returns list of (start_ts, teamA, teamB) ----------
def espn_games(days):
    sports = ["soccer", "basketball", "hockey", "baseball", "football", "rugby", "rugby-league", "volleyball",
              "lacrosse", "australian-football", "mma", "tennis", "cricket", "golf", "racing"]
    slugs = []
    for s in sports:
        d = fetch(f"https://sports.core.api.espn.com/v2/sports/{s}/leagues?limit=1000", PLAIN) or {}
        for it in d.get("items", []):
            m = re.search(r"/leagues/([^?/]+)", it.get("$ref", ""))
            if m:
                slugs.append((s, m.group(1)))
    rng = f"{days[0]:%Y%m%d}-{days[-1]:%Y%m%d}"

    def one(sl):
        d = fetch(f"https://site.api.espn.com/apis/site/v2/sports/{sl[0]}/{sl[1]}/scoreboard?dates={rng}&limit=500", PLAIN) or {}
        g = []
        for ev in d.get("events", []):
            for c in ev.get("competitions", []):
                cs = c.get("competitors", [])
                if len(cs) == 2:
                    nm = [(x.get("team") or x.get("athlete") or {}).get("displayName", "") for x in cs]
                    g.append((parse_ts(c.get("date") or ev.get("date")), nm[0], nm[1], f"espn:{sl[1]}"))
            for grp in ev.get("groupings", []):          # tennis
                for c in grp.get("competitions", []):
                    cs = c.get("competitors", [])
                    if len(cs) == 2:
                        nm = [(x.get("athlete") or {}).get("displayName", "") for x in cs]
                        g.append((parse_ts(c.get("date")), nm[0], nm[1], f"espn:{sl[1]}"))
        return g

    with ThreadPoolExecutor(12) as ex:
        res = [x for r in ex.map(one, slugs) for x in r]
    print("espn leagues", len(slugs), "games", len(res), flush=True)
    return res


def s365_games(days):
    res = []
    for d in days:
        for sp in (1, 2, 3, 4, 5, 6, 7, 8, 9):
            g = fetch(f"https://webws.365scores.com/web/games/allscores/?appTypeId=5&langId=1&timezoneName=UTC"
                      f"&userCountryId=1&sports={sp}&startDate={d:%d/%m/%Y}&endDate={d:%d/%m/%Y}&showOdds=false") or {}
            for x in g.get("games", []):
                res.append((parse_ts(x.get("startTime")), x["homeCompetitor"]["name"], x["awayCompetitor"]["name"],
                            f"s365:{x.get('competitionDisplayName')}"))
    print("365scores games", len(res), flush=True)
    return res


def livescore_games(days):
    res = []
    for d in days:
        for sp in ("soccer", "basketball", "hockey", "tennis", "cricket"):
            g = fetch(f"https://prod-public-api.livescore.com/v1/api/app/date/{sp}/{d:%Y%m%d}/0?MD=1") or {}
            for st in g.get("Stages", []):
                for e in st.get("Events", []):
                    try:
                        t = datetime.strptime(str(e.get("Esd")), "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).timestamp()
                        res.append((t, e["T1"][0]["Nm"], e["T2"][0]["Nm"], f"livescore:{st.get('Snm')}"))
                    except Exception:  # noqa: BLE001
                        pass
    print("livescore games", len(res), flush=True)
    return res


def bo3_games(days):
    res = []
    for status in ("current", "upcoming", "finished"):
        for off in range(0, 400, 50):
            d = fetch(f"https://api.bo3.gg/api/v1/matches?filter[matches.status][in]={status}&sort="
                      f"{'-end_date' if status == 'finished' else 'start_date'}&page[limit]=50&page[offset]={off}") or {}
            rows = d.get("results", [])
            for m in rows:
                s = re.sub(r"-\d{2}-\d{2}-\d{4}$", "", m.get("slug", ""))
                if "-vs-" in s:
                    a, b = s.split("-vs-", 1)
                    res.append((parse_ts(m.get("start_date")), a.replace("-", " "), b.replace("-", " "),
                                f"bo3:d{m.get('discipline_id')}"))
            if len(rows) < 50:
                break
    print("bo3 games", len(res), flush=True)
    return res


def lolesp_games(days):
    d = fetch("https://esports-api.lolesports.com/persisted/gw/getSchedule?hl=en-US",
              {**BROWSER, "x-api-key": "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"}) or {}
    res = []
    for e in (d.get("data", {}).get("schedule", {}).get("events", [])):
        t = (e.get("match") or {}).get("teams", [])
        if len(t) == 2:
            res.append((parse_ts(e.get("startTime")), t[0]["name"], t[1]["name"], f"lolesp:{e.get('league', {}).get('name')}"))
    print("lolesports games", len(res), flush=True)
    return res


def main(hours=48):
    pm = pm_events(hours)
    print("polymarket matches", len(pm), flush=True)
    today = datetime.now(timezone.utc).date()
    days = [today + timedelta(days=i) for i in range(-1, int(hours // 24) + 1)]
    srcs = {"espn": espn_games(days), "s365": s365_games(days), "livescore": livescore_games(days),
            "bo3": bo3_games(days), "lolesp": lolesp_games(days)}
    idx = {k: [g for g in v if g[0]] for k, v in srcs.items()}
    per = {}
    for e in pm:
        row = per.setdefault(e["league"], {"matches": 0, **{k: 0 for k in srcs}, "any": 0, "where": {}, "missed": []})
        row["matches"] += 1
        hit_any = False
        for k, games in idx.items():
            g = next((g for g in games if abs(g[0] - e["start"]) <= 3 * 3600 and (
                (same_team(e["teams"][0], g[1]) and same_team(e["teams"][1], g[2])) or
                (same_team(e["teams"][0], g[2]) and same_team(e["teams"][1], g[1])))), None)
            if g:
                row[k] += 1
                hit_any = True
                row["where"].setdefault(k, g[3])
        row["any"] += hit_any
        if not hit_any and len(row["missed"]) < 3:
            row["missed"].append(e["title"])
    out = sorted(({"league": k, **v} for k, v in per.items()), key=lambda r: -r["matches"])
    tot = {k: sum(r[k] for r in out) for k in ["matches", *srcs, "any"]}
    (RES / "source-coverage.json").write_text(json.dumps({"generated": datetime.now(timezone.utc).isoformat(
        timespec="seconds"), "hours_ahead": hours, "total": tot, "leagues": out}, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print("total", tot)


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 48)
