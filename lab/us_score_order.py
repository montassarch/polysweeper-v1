"""Does Polymarket's US-sports score (a-b) list teams in TITLE order? Check on settled games."""
import json, sys, collections
sys.path.insert(0, "../code")
from polysweeper.collector import GAMMA, get_json, leagues
from polysweeper.scorecheck import title_teams
L = leagues(); res = collections.Counter(); bad = []
for lg in ("mlb", "nfl", "cfb", "nhl"):
    sid = L[lg]["series"]
    for off in range(0, 400, 100):
        evs = get_json(f"{GAMMA}/events?series_id={sid}&closed=true&limit=100&offset={off}&order=endDate&ascending=false") or []
        for e in evs:
            sc, teams = e.get("score"), title_teams(e.get("title", ""))
            if not sc or not teams or "-" not in sc: continue
            try: a, b = [int(x) for x in sc.split("|")[-1].strip().split("-")[:2]]
            except ValueError: res[(lg, "unparsed")] += 1; continue
            m = next((m for m in e.get("markets", []) if m.get("sportsMarketType") == "moneyline"), None)
            if not m or a == b: res[(lg, "tie/nomkt")] += 1; continue
            outs, px = json.loads(m["outcomes"]), json.loads(m.get("outcomePrices") or "[]")
            if not px or max(map(float, px)) < 0.99: res[(lg, "unresolved/void")] += 1; continue
            won = outs[[float(p) for p in px].index(max(map(float, px)))].strip().lower()
            lead = teams[0 if a > b else 1].strip().lower()
            ok = won == lead
            res[(lg, "match" if ok else "MISMATCH")] += 1
            if not ok and len(bad) < 8: bad.append((lg, e.get("title"), sc, won))
for k in sorted(res): print(k, res[k])
for b in bad: print("BAD", b)
