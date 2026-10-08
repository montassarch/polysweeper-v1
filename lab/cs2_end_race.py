"""CS2 end race (read-only, no orders): who says "match over" first, bo3.gg or Polymarket, and do they agree?

Same idea as tennis_end_race.py, with bo3.gg (free CS2 site, JSON API, no key) as the outside source.
Every ~5 s: bo3.gg live + recently finished CS2 matches, and Polymarket's state for every live Polymarket CS2
match that bo3.gg also has (matched on both team names in bo3.gg's match slug). Per match:
  t_bo3   first poll where bo3.gg shows status 'finished', and its winner (+ bo3.gg's own end_date)
  t_pm    first poll where Polymarket shows ended=true, and the winner from its score
and at both moments the moneyline books (POST /books): winner's best ask and shares on sale at 0.96-0.995.
agree = bo3.gg winner == Polymarket score winner (a second source must never disagree).
Result: lab/data/raw/cs2_end_race/<utc date>.jsonl (one line per match) + lab/results/cs2-end-race-summary.json.
  py lab/cs2_end_race.py [hours=24]      (stop with Ctrl-C; measuring only)
"""
import json, re, sys, time
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "lab"))
from polysweeper.collector import get_json, GAMMA, parse_ts  # noqa: E402
from polysweeper.scorecheck import winner_outcome  # noqa: E402
from tennis_end_race import snap  # noqa: E402  (books at 0.96-0.995, same as tennis)
import urllib.request  # noqa: E402

BO3 = "https://api.bo3.gg/api/v1/matches?filter[matches.discipline_id][eq]=1&filter[matches.status][in]={}&page[limit]=50{}"
BROWSER = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36"}
SERIES = 10310   # Polymarket CS2
OUT = ROOT / "lab/data/raw/cs2_end_race"
OUT.mkdir(parents=True, exist_ok=True)
SUMMARY = ROOT / "lab/results/cs2-end-race-summary.json"
matches = {}     # pm event id -> record
stats = {"pm_live_seen": 0, "unmatched": []}


def norm(name):
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")


def bo3_get(status, extra=""):
    try:
        req = urllib.request.Request(BO3.format(status, extra), headers=BROWSER)
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.load(r).get("results", [])
    except Exception as exc:  # noqa: BLE001
        print("bo3 error", exc, flush=True)
        return []


def bo3_all():
    """Current + 50 most recently finished bo3.gg CS2 matches, by id."""
    rows = bo3_get("current") + bo3_get("finished", "&sort=-end_date")
    return {m["id"]: m for m in rows}


def slug_side(slug, outcomes):
    """bo3.gg slug 'team-a-vs-team-b-08-10-2026' -> (outcome index of team1, of team2) or None."""
    s = re.sub(r"-\d{2}-\d{2}-\d{4}$", "", slug or "")
    if "-vs-" not in s:
        return None
    t1, t2 = (core(x) for x in s.split("-vs-", 1))
    o = [core(norm(x)) for x in outcomes]
    if same(o[0], t1) and same(o[1], t2):
        return (0, 1)
    if same(o[1], t1) and same(o[0], t2):
        return (1, 0)
    return None


def core(n):
    """'infurity-gaming' -> 'infurity'; drops filler words that one site has and the other doesn't."""
    words = [w for w in n.strip("-").split("-") if w and w not in {"team", "gaming", "esports", "esport", "club", "gg"}]
    return "-".join(words)


def same(a, b):
    return bool(a and b) and (a == b or (min(len(a), len(b)) >= 4 and (a in b or b in a)))


def discover(bo3):
    seen = {m["pm"]["event"] for m in matches.values()}
    evs, off = [], 0   # page through: the first pages are old unresolved events (Mar-Apr), not today's
    while off < 2000:
        page = get_json(f"{GAMMA}/events?series_id={SERIES}&active=true&closed=false&limit=100&offset={off}") or []
        evs += page
        if len(page) < 100:
            break
        off += 100
    for e in evs:
        if e["id"] in seen or e.get("ended") or not e.get("live"):
            continue
        ml = next((m for m in e.get("markets", []) if m.get("sportsMarketType") == "moneyline"), None)
        if not ml:
            continue
        outs, toks = json.loads(ml["outcomes"]), json.loads(ml["clobTokenIds"])
        hit = next(((b, sides) for b in bo3.values() if b["status"] == "current"
                    for sides in [slug_side(b["slug"], outs)] if sides), None)
        if not hit:
            if e["title"] not in stats["unmatched"]:
                stats["unmatched"].append(e["title"])
                print(time.strftime("%H:%M:%S"), "no bo3.gg match for", e["title"], flush=True)
            continue
        b, sides = hit
        matches[e["id"]] = {"event": e["id"], "title": e["title"], "bo3_id": b["id"], "bo3_slug": b["slug"],
                            "bo3_team_idx": {str(b["team1_id"]): sides[0], str(b["team2_id"]): sides[1]},
                            "outcomes": outs, "tokens": toks, "t_bo3": None, "t_pm": None, "saved": False,
                            "pm": {"event": e["id"]}}
        print(time.strftime("%H:%M:%S"), "watching", e["title"], flush=True)


def summarize():
    rows = []
    for f in sorted(OUT.glob("*.jsonl")):
        rows += [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]
    both = [r for r in rows if r.get("bo3_lead_s") is not None]
    leads = sorted(r["bo3_lead_s"] for r in both)
    SUMMARY.write_text(json.dumps({
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "matches_saved": len(rows), "both_finished": len(both),
        "agree": sum(1 for r in both if r.get("agree") is True),
        "disagree": [r["title"] for r in both if r.get("agree") is False],
        "bo3_first": sum(1 for x in leads if x > 0),
        "median_bo3_lead_s": leads[len(leads) // 2] if leads else None,
        "band_shares_at_bo3_winner": [r["at_bo3_winner_band"] for r in both],
        "unmatched_pm_titles": stats["unmatched"][-30:],
    }, indent=1), encoding="utf-8")


def winner_band(s):
    return next((b["band_shares"] for b in s["books"] if b["winner"]), None) if s else None


def main(hours=24.0):
    stop, last_disc, last_sum = time.time() + hours * 3600, 0, 0
    while time.time() < stop:
        bo3 = bo3_all()
        if time.time() - last_disc > 60:
            discover(bo3)
            last_disc = time.time()
        open_ids = [i for i, m in matches.items() if not m["saved"]]
        pm = {e["id"]: e for e in (get_json(f"{GAMMA}/events?" + "&".join(f"id={i}" for i in open_ids)) or [])} if open_ids else {}
        for i in open_ids:
            m = matches[i]
            b = bo3.get(m["bo3_id"])
            if b and b["status"] == "finished" and m["t_bo3"] is None:
                side = m["bo3_team_idx"].get(str(b.get("winner_team_id")))
                m.update(t_bo3=round(time.time(), 2), bo3_side=side, bo3_end=b.get("end_date"),
                         bo3_score=f'{b.get("team1_score")}-{b.get("team2_score")}', at_bo3=snap(m, side))
                print(time.strftime("%H:%M:%S"), "bo3 final", m["title"], m["bo3_score"], flush=True)
            e = pm.get(i)
            if e and e.get("ended") is True and m["t_pm"] is None:
                side = winner_outcome(e, m["outcomes"], "esports")
                m.update(t_pm=round(time.time(), 2), pm_score=e.get("score"), pm_side=side,
                         pm_finished=e.get("finishedTimestamp"), at_pm=snap(m, side))
                print(time.strftime("%H:%M:%S"), "PM ended", m["title"], e.get("score"), flush=True)
            first = min(x for x in (m["t_bo3"], m["t_pm"], time.time()) if x)
            if (m["t_bo3"] and m["t_pm"]) or (first < time.time() - 1800 and (m["t_bo3"] or m["t_pm"])):
                m["saved"] = True
                m["agree"] = (m.get("bo3_side") == m.get("pm_side")) if m["t_bo3"] and m["t_pm"] else None
                m["bo3_lead_s"] = round(m["t_pm"] - m["t_bo3"], 1) if m["t_bo3"] and m["t_pm"] else None
                end_ts = parse_ts(m.get("bo3_end"))
                m["bo3_end_lag_s"] = round(m["t_bo3"] - end_ts, 1) if end_ts and m["t_bo3"] else None
                m["at_bo3_winner_band"] = winner_band(m.get("at_bo3"))
                with open(OUT / f"{datetime.now(timezone.utc):%Y-%m-%d}.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps(m) + "\n")
                print(time.strftime("%H:%M:%S"), "saved", m["title"], "bo3.gg ahead by", m["bo3_lead_s"], "s",
                      "agree", m["agree"], flush=True)
                summarize()
        if time.time() - last_sum > 600:
            summarize()
            last_sum = time.time()
        time.sleep(5)
    summarize()


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 24.0)
