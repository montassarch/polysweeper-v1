"""Best wallet (4ddc): ESPN win probability of the side it BOUGHT at the moment of each moneyline TAKER buy >= 0.95 (NFL, CFB, NHL, NBA, WNBA).
Question: are its in-play snipes all at ~99.5%+ model certainty (a copyable threshold) or at ordinary 95-99% states?"""
import collections, json, statistics, sys, time
from datetime import datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lab")); sys.path.insert(0, str(ROOT / "code"))
from mktinfo import lookup  # noqa: E402
from polysweeper.collector import get_json  # noqa: E402

BASE = "https://site.api.espn.com/apis/site/v2/sports"
PATH = {"nfl": "football/nfl", "cfb": "football/college-football", "nhl": "hockey/nhl", "wnba": "basketball/wnba", "nba": "basketball/nba"}
cache = json.loads((ROOT / "lab/data/raw/espn_official_end_cache.json").read_text())
trades = [json.loads(l) for l in (ROOT / "lab/data/raw/wallets/4ddc.jsonl").read_text().splitlines() if l.strip()]
key = lambda t: (t["transactionHash"], t["asset"], t["side"], round(float(t["size"]), 4), round(float(t["price"]), 4))
takers = {key(json.loads(l)) for l in (ROOT / "lab/data/raw/wallets/4ddc_takeronly.jsonl").read_text().splitlines() if l.strip()}
sel = [t for t in trades if t["side"] == "BUY" and float(t["price"]) >= 0.95 and key(t) in takers and (cache.get(t["eventSlug"]) or None)]
info = lookup([t["conditionId"] for t in sel])
sel = [t for t in sel if (info.get(t["conditionId"]) or {}).get("type") == "moneyline"]
print("moneyline taker buys >= 0.95 in ESPN-matched games:", len(sel))
games = {}


def game(slug):
    if slug not in games:
        eid = cache[slug]["espn"]; sport = slug.split("-")[0]
        s = get_json(f"{BASE}/{PATH[sport]}/summary?event={eid}") or {}
        comp = (s.get("header", {}).get("competitions") or [{}])[0]
        teams = {c["homeAway"]: c["team"] for c in comp.get("competitors", [])}
        plays = s.get("plays") or []
        if not plays:
            for d in (s.get("drives", {}).get("previous") or []):
                plays += d.get("plays", [])
        wc = {p["id"]: datetime.fromisoformat(p["wallclock"].replace("Z", "+00:00")).timestamp() for p in plays if p.get("wallclock")}
        wp = []
        for w in s.get("winprobability") or []:
            if w.get("playId") in wc and w.get("homeWinPercentage") is not None:
                wp.append((wc[w["playId"]], float(w["homeWinPercentage"])))
        wp.sort()
        games[slug] = {"teams": teams, "wp": wp}
    return games[slug]


rows = []
for t in sel:
    g = game(t["eventSlug"])
    if not g["wp"]:
        continue
    out = (t.get("outcome") or "").lower()
    side = None
    for ha, tm in g["teams"].items():
        names = [tm.get("displayName", ""), tm.get("shortDisplayName", ""), tm.get("name", ""), tm.get("location", "")]
        if any(n and (n.lower() in out or out in n.lower()) for n in names):
            side = ha
    if side is None:
        continue
    before = [w for w in g["wp"] if w[0] <= t["timestamp"]]
    if not before:
        continue
    home_wp = before[-1][1]
    wp = home_wp if side == "home" else 1 - home_wp
    after_last = t["timestamp"] - g["wp"][-1][0]
    rows.append({"slug": t["eventSlug"], "wp": wp, "price": float(t["price"]), "size": float(t["size"]), "after_last_play_s": after_last, "sport": t["eventSlug"].split("-")[0]})
print("matched with ESPN win probability:", len(rows))
def pct(x, q):
    x = sorted(x); return x[min(len(x) - 1, int(q * len(x)))]
wps = [r["wp"] for r in rows]
print("ESPN win probability of the bought side at the buy second: min %.3f p10 %.3f median %.3f p90 %.3f" % (min(wps), pct(wps, .1), statistics.median(wps), pct(wps, .9)))
for lo, hi in ((0, .9), (.9, .95), (.95, .98), (.98, .99), (.99, .995), (.995, .999), (.999, 1.01)):
    x = [r for r in rows if lo <= r["wp"] < hi]
    print(f"  WP {lo:.3f}-{hi:.3f}: buys {len(x):3}  median price {statistics.median([r['price'] for r in x]) if x else '-'}")
by = collections.Counter(r["sport"] for r in rows); print("by sport:", dict(by))
lost = [t for t in sel if (info.get(t["conditionId"]) or {}).get("final") and info[t["conditionId"]]["final"][t["outcomeIndex"]] == 0.0]
print("lost moneyline taker buys:", [(t["title"][:40], t["price"]) for t in lost])
low = sorted(rows, key=lambda r: r["wp"])[:8]
print("lowest-WP buys:", [(r["slug"][-20:], round(r["wp"], 3), r["price"], round(r["after_last_play_s"])) for r in low])
