"""Pull Polymarket stock/ETF ladder events (closed ones) and their full public tape, for the last-hour
dead-strike sweep study (idea card 1 of R-2026-10-08).

  python3 lab/stock_ladder_pull.py 2026-09-08 2026-10-08      # end-date window [from, to)

Writes (raw, git-ignored): lab/data/raw/stockladder/events.json  (one row per event, with its markets)
                           lab/data/raw/stockladder/trades/<eventId>.json  (compact trades of the event)
Families (by slug): dailyclose_above, weekly_above, weekly_bracket, weekly_hit, monthly_above, monthly_hit, updown.
Read-only public endpoints (Gamma events, Data API trades). Polite: 0.2 s pause per call (collector.get_json).
"""
import json, re, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
from polysweeper.collector import get_json  # noqa: E402

GAMMA = "https://gamma-api.polymarket.com"
DATA = "https://data-api.polymarket.com"
OUT = ROOT / "lab/data/raw/stockladder"
(OUT / "trades").mkdir(parents=True, exist_ok=True)


def family(slug):
    if "opens-up-or-down" in slug:
        return "opens"
    if "-up-or-down-on-" in slug:
        return "updown"
    if re.search(r"-closes?-above-on-", slug):
        return "dailyclose_above"
    if slug.startswith("will-") and "-hit-week-of-" in slug:
        return "weekly_hit"
    if re.search(r"-above-on-", slug):
        return "weekly_above"
    if re.search(r"-week-[a-z]+-\d", slug):
        return "weekly_bracket"
    if "-above-in-" in slug:
        return "monthly_above"
    if "hit-in-" in slug:
        return "monthly_hit"
    return "other"


def ticker(slug):
    s = slug
    if s.startswith("what-price-will-"):
        return s[len("what-price-will-"):].split("-")[0].upper()
    if s.startswith("will-"):
        s = s[5:]
    return s.split("-")[0].upper()


def list_events(d0, d1, closed="true"):
    evs, off = [], 0
    while True:
        url = (f"{GAMMA}/events?tag_slug=stocks&closed={closed}&end_date_min={d0}T00:00:00Z"
               f"&end_date_max={d1}T00:00:00Z&limit=100&offset={off}&order=endDate&ascending=false")
        page = get_json(url) or []
        evs += page
        if len(page) < 100:
            break
        off += 100
    return evs


def slim_event(e):
    ms = []
    for m in e.get("markets", []):
        try:
            toks = json.loads(m.get("clobTokenIds") or "[]")
            outs = json.loads(m.get("outcomes") or "[]")
            prices = json.loads(m.get("outcomePrices") or "[]")
        except Exception:
            continue
        ms.append({"cid": m.get("conditionId"), "q": m.get("question"), "g": m.get("groupItemTitle"),
                   "tokens": toks, "outcomes": outs, "final": prices, "closedTime": m.get("closedTime"),
                   "uma": m.get("umaResolutionStatus"), "endDate": m.get("endDate"),
                   "bid": m.get("bestBid"), "ask": m.get("bestAsk"), "vol": m.get("volume"),
                   "created": m.get("createdAt") or m.get("startDate")})
    return {"id": e["id"], "slug": e["slug"], "title": e.get("title"), "family": family(e["slug"]),
            "ticker": ticker(e["slug"]), "endDate": e.get("endDate"), "closedTime": e.get("closedTime"),
            "startDate": e.get("startDate"), "negRisk": e.get("negRisk"), "markets": ms}


def pull_trades(ev, cap=15000):
    f = OUT / "trades" / f"{ev['id']}.json"
    if f.exists():
        return ev["id"], -1
    rows, off = [], 0
    while off <= cap:
        page = get_json(f"{DATA}/trades?eventId={ev['id']}&limit=500&offset={off}")
        if not isinstance(page, list) or not page:
            break
        rows += page
        if len(page) < 500:
            break
        off += 500
    keep = [{"cid": t.get("conditionId"), "side": t.get("side"), "price": t.get("price"), "size": t.get("size"),
             "ts": t.get("timestamp"), "w": t.get("proxyWallet"), "oi": t.get("outcomeIndex"),
             "o": t.get("outcome"), "tx": t.get("transactionHash")} for t in rows]
    f.write_text(json.dumps(keep))
    return ev["id"], len(keep)


if __name__ == "__main__":
    d0, d1 = sys.argv[1], sys.argv[2]
    raw = list_events(d0, d1)
    evs = [slim_event(e) for e in raw]
    keep_fam = {"dailyclose_above", "weekly_above", "weekly_bracket", "weekly_hit", "monthly_above", "monthly_hit", "updown"}
    evs = [e for e in evs if e["family"] in keep_fam]
    (OUT / "events.json").write_text(json.dumps(evs))
    print("events", len(evs))
    n = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        for eid, k in pool.map(pull_trades, evs):
            n += 1
            if n % 50 == 0:
                print("pulled", n, "of", len(evs), flush=True)
    print("done")
