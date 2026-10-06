"""Tennis end race (read-only, no orders): who says "match over" first, ESPN or Polymarket, and what is left to buy then?

Every ~3 s: ESPN's free tennis scoreboards (ATP + WTA) and Polymarket's state (live/ended/score) for every live
Polymarket tennis match that ESPN also covers (matched on both players' last names). For each match we note:
  t_espn   first poll where ESPN shows the match final (state 'post'), and ESPN's winner
  t_pm     first poll where Polymarket shows ended=true, and its score
and at both moments we read the moneyline books (POST /books): the winner's best ask and the shares on sale at
0.96-0.995. Also: does ESPN's winner agree with Polymarket's final score? (a second source must never disagree).
Result: lab/data/raw/tennis_end_race/<utc date>.jsonl, one line per finished match.
  py lab/tennis_end_race.py [hours=12]      (stop with Ctrl-C; measuring only)
"""
import json, sys, time
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
from polysweeper.collector import get_json, GAMMA, CLOB, UA  # noqa: E402
import urllib.request  # noqa: E402

ESPN = "https://site.api.espn.com/apis/site/v2/sports/tennis/{}/scoreboard"
SERIES = {"atp": 10365, "wta": 10366}
OUT = ROOT / "lab/data/raw/tennis_end_race"
OUT.mkdir(parents=True, exist_ok=True)
BAND = (0.96, 0.995)
matches = {}   # pm event id -> record


def last(name):
    return (name or "").strip().split(" ")[-1].lower()


def books(tokens):
    try:
        req = urllib.request.Request(f"{CLOB}/books", data=json.dumps([{"token_id": t} for t in tokens]).encode(),
                                     headers={**UA, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return {b["asset_id"]: b for b in json.load(r)}
    except Exception as exc:  # noqa: BLE001
        print("books error", exc, flush=True)
        return {}


def snap(rec, side):
    """Best ask and shares in band for both moneyline sides (side = winner index if known)."""
    bk = books(rec["tokens"])
    out = []
    for i, t in enumerate(rec["tokens"]):
        asks = [(float(a["price"]), float(a["size"])) for a in bk.get(t, {}).get("asks", [])]
        best = min((p for p, _ in asks), default=None)
        band = round(sum(s for p, s in asks if BAND[0] <= p <= BAND[1]), 1)
        out.append({"idx": i, "best_ask": best, "band_shares": band, "winner": i == side})
    return {"t": round(time.time(), 2), "books": out}


def pm_winner(score, outcomes):
    """Winner index from a final tennis score like '6-3, 5-7, 6-2' (sets won by side 0 vs side 1)."""
    try:
        a = b = 0
        for s in score.split(","):
            x, y = s.strip().split("(")[0].split("-")
            a, b = a + (int(x) > int(y)), b + (int(y) > int(x))
        return 0 if a > b else 1 if b > a else None
    except Exception:  # noqa: BLE001
        return None


def discover(espn_live):
    """Register live Polymarket tennis matches whose two players are both in a live/just-final ESPN match."""
    for tour, sid in SERIES.items():
        for e in get_json(f"{GAMMA}/events?series_id={sid}&active=true&closed=false&limit=200") or []:
            if e["id"] in matches or e.get("ended") or not e.get("live"):
                continue
            ml = next((m for m in e.get("markets", []) if m.get("sportsMarketType") == "moneyline"), None)
            if not ml:
                continue
            outs, toks = json.loads(ml["outcomes"]), json.loads(ml["clobTokenIds"])
            key = frozenset(last(o) for o in outs)
            comp = espn_live.get(key)
            if comp:
                matches[e["id"]] = {"event": e["id"], "title": e["title"], "tour": tour, "espn_id": comp["id"],
                                    "outcomes": outs, "tokens": toks, "t_espn": None, "t_pm": None, "saved": False}
                print(time.strftime("%H:%M:%S"), "watching", e["title"], flush=True)


def espn_all():
    comps = {}
    for tour in SERIES:
        r = get_json(ESPN.format(tour)) or {}
        for ev in r.get("events", []):
            for g in ev.get("groupings", []):
                for c in g.get("competitions", []):
                    names = [p.get("athlete", {}).get("displayName", "") for p in c.get("competitors", [])]
                    if len(names) == 2 and all(names):
                        win = next((p.get("athlete", {}).get("displayName") for p in c["competitors"] if p.get("winner")), None)
                        comps[frozenset(last(n) for n in names)] = {"id": c["id"], "state": c["status"]["type"]["state"],
                                                                     "detail": c["status"]["type"].get("detail"), "winner": win}
    return comps


def main(hours=12.0):
    stop, last_disc = time.time() + hours * 3600, 0
    while time.time() < stop:
        espn = espn_all()
        if time.time() - last_disc > 60:
            discover({k: v for k, v in espn.items() if v["state"] == "in"})
            last_disc = time.time()
        open_ids = [i for i, m in matches.items() if not m["saved"]]
        pm = {e["id"]: e for e in (get_json(f"{GAMMA}/events?" + "&".join(f"id={i}" for i in open_ids)) or [])} if open_ids else {}
        for i in open_ids:
            m = matches[i]
            c = next((v for v in espn.values() if v["id"] == m["espn_id"]), None)
            if c and c["state"] == "post" and m["t_espn"] is None:
                side = next((k for k, o in enumerate(m["outcomes"]) if c["winner"] and last(o) == last(c["winner"])), None)
                m.update(t_espn=round(time.time(), 2), espn_winner=c["winner"], espn_detail=c["detail"], espn_side=side,
                         at_espn=snap(m, side))
                print(time.strftime("%H:%M:%S"), "ESPN final", m["title"], c["winner"], flush=True)
            e = pm.get(i)
            if e and e.get("ended") is True and m["t_pm"] is None:
                side = pm_winner(e.get("score") or "", m["outcomes"])
                m.update(t_pm=round(time.time(), 2), pm_score=e.get("score"), pm_side=side,
                         pm_finished=e.get("finishedTimestamp"), at_pm=snap(m, side))
                print(time.strftime("%H:%M:%S"), "PM ended", m["title"], e.get("score"), flush=True)
            first = min(x for x in (m["t_espn"], m["t_pm"], time.time()) if x)
            if (m["t_espn"] and m["t_pm"]) or (first < time.time() - 1800 and (m["t_espn"] or m["t_pm"])):
                m["saved"] = True
                m["agree"] = (m.get("espn_side") == m.get("pm_side")) if m["t_espn"] and m["t_pm"] else None
                m["espn_lead_s"] = round(m["t_pm"] - m["t_espn"], 1) if m["t_espn"] and m["t_pm"] else None
                with open(OUT / f"{datetime.now(timezone.utc):%Y-%m-%d}.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps(m) + "\n")
                print(time.strftime("%H:%M:%S"), "saved", m["title"], "ESPN ahead by", m["espn_lead_s"], "s", flush=True)
        time.sleep(3)


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 12.0)
