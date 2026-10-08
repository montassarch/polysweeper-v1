"""Feeds end race (read-only, no orders): who says "match over" first: 365Scores, LiveScore or Polymarket?
And do they agree on the final score, and what is left to buy at that moment?

Covers every live Polymarket sports match except esports (esports: lab/cs2_end_race.py): football, basketball,
hockey, tennis, baseball, American football, cricket, handball ...
  discovery (every 60 s): Gamma events?live=true (main events only, not "- Halftime" etc.), matched by team names
     + start time to 365Scores "current" games and LiveScore live lists.
  polling (every ~4 s per watched match): 365Scores per-game JSON (3 KB), LiveScore per-event scoreboard (2 KB),
     Polymarket events by id (batched). Speeds up to 6 s when many matches are watched (gentle on all three).
Per match: t_365 / t_ls / t_pm = first poll where that source says the match is over, its final score, and the
moneyline books (winner's best ask, shares at 0.96-0.995) at the first "over" moment of each source.
Output: lab/data/raw/feeds_end_race/<utc date>.jsonl (local), lab/results/feeds-end-race-summary.json
(pushed every 3 h, only that file). Stable by design: every network call has a timeout and is wrapped; a crash
in one loop is logged and the loop goes on; memory is bounded (saved matches are dropped).
  py lab/feeds_end_race.py [hours=168]
"""
import json, re, subprocess, sys, time, traceback, urllib.request
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "lab"))
from polysweeper.collector import get_json, GAMMA, parse_ts, CLOB, UA  # noqa: E402
from source_coverage import same_team  # noqa: E402
from polysweeper.scorecheck import tennis_score  # noqa: E402

OUT = ROOT / "lab/data/raw/feeds_end_race"
OUT.mkdir(parents=True, exist_ok=True)
SUMMARY = ROOT / "lab/results/feeds-end-race-summary.json"
BROWSER = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/128.0 Safari/537.36"}
S365 = "https://webws.365scores.com/web"
LS = "https://prod-public-api.livescore.com/v1/api/app"
S365_SPORTS = (1, 2, 3, 4, 5, 6, 7, 8, 9)
LS_SPORTS = ("soccer", "basketball", "hockey", "tennis", "cricket")
LS_OVER = {"FT", "AET", "AP", "Ended", "Fin", "Abd", "Canc.", "Aband.", "Ret."}   # "Int." = interrupted, not over
BAND = (0.96, 0.995)
watch = {}          # pm event id -> record
done_ids = set()
stats = {"started": datetime.now(timezone.utc).isoformat(timespec="seconds"), "discovered": 0,
         "no_source": 0, "errors": 0, "no_source_examples": []}


def fetch(url, headers=None, timeout=12):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers or BROWSER), timeout=timeout) as r:
            return json.load(r)
    except Exception:  # noqa: BLE001
        stats["errors"] += 1
        return None


def books(tokens):
    try:
        req = urllib.request.Request(f"{CLOB}/books", data=json.dumps([{"token_id": t} for t in tokens]).encode(),
                                     headers={**UA, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return {b["asset_id"]: b for b in json.load(r)}
    except Exception:  # noqa: BLE001
        return {}


def snap(rec):
    bk = books([t for t, _ in rec["tokens"]])
    out = []
    for t, label in rec["tokens"]:
        asks = [(float(a["price"]), float(a["size"])) for a in bk.get(t, {}).get("asks", [])]
        out.append({"label": label, "best_ask": min((p for p, _ in asks), default=None),
                    "band_shares": round(sum(s for p, s in asks if BAND[0] <= p <= BAND[1]), 1)})
    return {"t": round(time.time(), 2), "books": out}


# ---------------- discovery ----------------
def pm_live():
    evs, off = [], 0
    while off < 1000:
        page = get_json(f"{GAMMA}/events?active=true&closed=false&live=true&limit=200&offset={off}") or []
        evs += page
        if len(page) < 200:
            break
        off += 200
    rows = []
    for e in evs:
        mls = [m for m in e.get("markets", []) if m.get("sportsMarketType") == "moneyline"]
        if not mls or "|" in str(e.get("score") or "") or e.get("ended"):
            continue            # esports (map scores) handled elsewhere; finished already
        if re.search(r" - (Halftime|Second|Exact|First|More|Player|Total|Spread|Both)", e["title"]):
            continue
        teams = None
        if len(mls) == 1:
            o = json.loads(mls[0].get("outcomes") or "[]")
            if len(o) == 2:
                teams = o
            toks = [(t, lab) for t, lab in zip(json.loads(mls[0].get("clobTokenIds") or "[]"), o)]
        else:   # 3-way football: one Yes/No market per outcome
            toks = [(json.loads(m.get("clobTokenIds") or "[]")[0], m.get("groupItemTitle") or m.get("question"))
                    for m in mls if m.get("clobTokenIds")]
        if not teams:
            t = re.sub(r"^[^:]*:\s*", "", e["title"])
            parts = re.split(r"\s+vs\.?\s+|\s+@\s+", re.sub(r"\s*\(.*?\)", "", t))
            teams = parts if len(parts) == 2 else None
        if teams:
            rows.append({"event": e["id"], "title": e["title"], "series": e.get("seriesSlug"),
                         "start": parse_ts(e.get("startTime")), "teams": teams, "tokens": toks})
    return rows


def src_lists():
    g365 = []
    for sp in S365_SPORTS:
        d = fetch(f"{S365}/games/current/?appTypeId=5&langId=1&timezoneName=UTC&userCountryId=1&sports={sp}") or {}
        for x in d.get("games", []):
            g365.append((parse_ts(x.get("startTime")), x["homeCompetitor"]["name"], x["awayCompetitor"]["name"],
                         x["id"], sp))
    gls = []
    for sp in LS_SPORTS:
        d = fetch(f"{LS}/live/{sp}/0?MD=1") or {}
        for st in d.get("Stages", []):
            for e in st.get("Events", []):
                try:
                    t = datetime.strptime(str(e.get("Esd")), "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).timestamp()
                    gls.append((t, e["T1"][0]["Nm"], e["T2"][0]["Nm"], e["Eid"], sp))
                except Exception:  # noqa: BLE001
                    pass
    return g365, gls


def find(rec, games):
    for g in games:
        if g[0] and rec["start"] and abs(g[0] - rec["start"]) > 3 * 3600:
            continue
        if same_team(rec["teams"][0], g[1]) and same_team(rec["teams"][1], g[2]):
            return g, False
        if same_team(rec["teams"][0], g[2]) and same_team(rec["teams"][1], g[1]):
            return g, True      # source home = PM side 1
    return None, None


def discover():
    pm = [r for r in pm_live() if r["event"] not in watch and r["event"] not in done_ids]
    if not pm:
        return
    g365, gls = src_lists()
    for r in pm:
        a, flip_a = find(r, g365)
        b, flip_b = find(r, gls)
        if not a and not b:
            stats["no_source"] += 1
            if len(stats["no_source_examples"]) < 40:
                stats["no_source_examples"].append(r["title"])
            done_ids.add(r["event"])
            continue
        r.update(id365=a[3] if a else None, flip365=flip_a, ls=(b[4], b[3]) if b else None, flipls=flip_b,
                 t_365=None, t_ls=None, t_pm=None, seen=time.time())
        watch[r["event"]] = r
        stats["discovered"] += 1
        print(time.strftime("%H:%M:%S"), "watch", r["title"][:70], "365" if a else "-", "LS" if b else "-", flush=True)


# ---------------- polling ----------------
def poll_365(r):
    d = fetch(f"{S365}/game/?appTypeId=5&langId=1&timezoneName=UTC&userCountryId=1&gameId={r['id365']}") or {}
    g = d.get("game") or {}
    if g.get("statusGroup") == 4 and r["t_365"] is None:
        h, a = g.get("homeCompetitor", {}).get("score"), g.get("awayCompetitor", {}).get("score")
        sc = (a, h) if r["flip365"] else (h, a)
        r.update(t_365=round(time.time(), 2), s365_status=g.get("statusText"), s365_score=sc, at_365=snap(r))
        print(time.strftime("%H:%M:%S"), "365 over", r["title"][:60], g.get("statusText"), sc, flush=True)


def poll_ls(r):
    sp, eid = r["ls"]
    d = fetch(f"{LS}/scoreboard/{sp}/{eid}?locale=en") or {}
    eps = str(d.get("Eps") or "")
    if eps in LS_OVER and r["t_ls"] is None:
        h, a = d.get("Tr1"), d.get("Tr2")
        sc = (a, h) if r["flipls"] else (h, a)
        r.update(t_ls=round(time.time(), 2), ls_status=eps, ls_score=sc, at_ls=snap(r))
        print(time.strftime("%H:%M:%S"), "LS over", r["title"][:60], eps, sc, flush=True)


def poll_pm(ids):
    evs = get_json(f"{GAMMA}/events?" + "&".join(f"id={i}" for i in ids)) or []
    for e in evs:
        r = watch.get(str(e["id"])) or watch.get(e["id"])
        if r and e.get("ended") is True and r["t_pm"] is None:
            r.update(t_pm=round(time.time(), 2), pm_score=e.get("score"), pm_finished=e.get("finishedTimestamp"),
                     at_pm=snap(r))
            print(time.strftime("%H:%M:%S"), "PM ended", r["title"][:60], e.get("score"), flush=True)


def nums(s):
    try:
        return [float(x) for x in s] if isinstance(s, (list, tuple)) else None
    except (TypeError, ValueError):
        return None


def finish(r):
    """Save a match when every matched source has said 'over', or 45 min after the first one did."""
    want = [r["t_pm"]] + ([r["t_365"]] if r["id365"] else []) + ([r["t_ls"]] if r["ls"] else [])
    firsts = [t for t in want if t]
    old = time.time() - r["seen"] > 6 * 3600
    if not firsts and not old:
        return False
    if firsts and not (all(want) or time.time() - min(firsts) > 2700 or old):
        return False
    tp = r["t_pm"]
    r["lead_365_s"] = round(tp - r["t_365"], 1) if tp and r["t_365"] else None
    r["lead_ls_s"] = round(tp - r["t_ls"], 1) if tp and r["t_ls"] else None
    pm = re.findall(r"\d+", str(r.get("pm_score") or ""))[:2]
    pmn = [float(x) for x in pm] if len(pm) == 2 and "," not in str(r.get("pm_score")) else None
    if "," in str(r.get("pm_score")) or re.match(r"^\d+-\d+(\(\d+-\d+\))?$", str(r.get("pm_score"))) and r.get("series") in ("atp", "wta", "itf", "atp-doubles", "wta-doubles"):
        ts = tennis_score(str(r.get("pm_score")))      # tennis: compare sets won
        pmn = [float(ts[0]), float(ts[1])] if ts else None
    for k in ("365", "ls"):
        sc = nums(r.get(f"s365_score" if k == "365" else "ls_score"))
        r[f"agree_{k}"] = (sc == pmn) if sc and pmn else None
    r.pop("tokens", None)
    with open(OUT / f"{datetime.now(timezone.utc):%Y-%m-%d}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(r) + "\n")
    print(time.strftime("%H:%M:%S"), "saved", r["title"][:60], "365 lead", r["lead_365_s"], "LS lead",
          r["lead_ls_s"], flush=True)
    return True


def summary():
    rows = []
    for f in sorted(OUT.glob("*.jsonl")):
        rows += [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]

    def stat(key, agree):
        v = sorted(r[key] for r in rows if r.get(key) is not None)
        return {"n": len(v), "source_first": sum(1 for x in v if x > 0), "median_lead_s": v[len(v) // 2] if v else None,
                "p10_lead_s": v[len(v) // 10] if v else None, "p90_lead_s": v[len(v) * 9 // 10] if v else None,
                "score_agree": sum(1 for r in rows if r.get(agree) is True),
                "score_disagree": [r["title"] for r in rows if r.get(agree) is False][:20]}
    by = {}
    for r in rows:
        s = by.setdefault(r.get("series") or "?", {"n": 0, "lead_365": [], "lead_ls": []})
        s["n"] += 1
        for k in ("365", "ls"):
            if r.get(f"lead_{k}_s") is not None:
                s[f"lead_{k}"].append(r[f"lead_{k}_s"])
    for s in by.values():
        for k in ("lead_365", "lead_ls"):
            v = sorted(s[k])
            s[k] = {"n": len(v), "median": v[len(v) // 2] if v else None}
    return {"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "matches_saved": len(rows),
            "s365": stat("lead_365_s", "agree_365"), "livescore": stat("lead_ls_s", "agree_ls"),
            "pm_never_ended": sum(1 for r in rows if not r.get("t_pm")), "by_series": by, **stats,
            "watching_now": len(watch)}


def publish(push):
    SUMMARY.write_text(json.dumps(summary(), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    if not push:
        return
    rel, git = "lab/results/feeds-end-race-summary.json", ["git", "-C", str(ROOT)]
    try:
        subprocess.run(git + ["add", rel], check=True, capture_output=True)
        if subprocess.run(git + ["diff", "--cached", "--quiet", "--", rel]).returncode == 0:
            return
        subprocess.run(git + ["commit", "-q", "-m", "Lab: feeds end-race summary (laptop)", "--", rel],
                       check=True, capture_output=True)
        for _ in range(3):
            subprocess.run(git + ["pull", "-q", "--rebase", "--autostash"], capture_output=True)
            if subprocess.run(git + ["push", "-q"], capture_output=True).returncode == 0:
                print("summary pushed", flush=True)
                return
            time.sleep(10)
    except Exception as exc:  # noqa: BLE001
        print("publish error", exc, flush=True)


def main(hours=168.0):
    stop, last_disc, last_sum, last_push = time.time() + hours * 3600, 0, 0, time.time()
    while time.time() < stop:
        loop = time.time()
        try:
            if loop - last_disc > 60:
                discover()
                last_disc = time.time()
            ids = list(watch)
            for i in range(0, len(ids), 40):
                poll_pm(ids[i:i + 40])
            for i in ids:
                r = watch[i]
                if r["id365"] and r["t_365"] is None:
                    poll_365(r)
                if r["ls"] and r["t_ls"] is None:
                    poll_ls(r)
                if finish(r):
                    done_ids.add(i)
                    del watch[i]
            if loop - last_sum > 600:
                push = time.time() - last_push > 3 * 3600
                publish(push)
                last_sum = time.time()
                last_push = time.time() if push else last_push
        except Exception:  # noqa: BLE001
            print("loop error", traceback.format_exc()[-600:], flush=True)
            time.sleep(10)
        # gentle pacing: 4 s, up to 6 s when many matches are watched
        time.sleep(max(0.5, (4 if len(watch) < 25 else 6) - (time.time() - loop)))
    publish(True)


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 168.0)
