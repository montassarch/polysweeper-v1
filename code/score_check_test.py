"""Validate check 2 on finished Polymarket matches: does the score ever disagree with the real result?"""
import json, sys, collections
from polysweeper.collector import leagues, get_json, GAMMA
from polysweeper.scorecheck import winner_outcome, score_winner, title_teams

ESPORTS = ["cs2", "lol", "dota2", "val", "codmw", "r6siege", "ow", "mlbb", "hok", "sc2", "pubg", "lol-wild-rift"]
TENNIS = ["atp", "wta", "itf"]
MAX = int(sys.argv[1]) if len(sys.argv) > 1 else 1500

L = leagues()
out = {}
for sport, keys in (("esports", ESPORTS), ("tennis", TENNIS)):
    for lg in keys:
        if lg not in L: continue
        c = collections.Counter(); bad = []
        offset = 0
        while offset < MAX:
            evs = get_json(f"{GAMMA}/events?series_id={L[lg]['series']}&closed=true&limit=100&offset={offset}&order=endDate&ascending=false") or []
            for e in evs:
                for m in e.get("markets", []):
                    if m.get("sportsMarketType") != "moneyline": continue
                    try:
                        outs = json.loads(m["outcomes"]); px = [float(x) for x in json.loads(m["outcomePrices"])]
                    except (KeyError, ValueError):
                        continue
                    if sorted(px) != [0.0, 1.0]:
                        c["not 1/0 (void or 50/50)"] += 1; continue
                    real = px.index(1.0)
                    c["resolved"] += 1
                    teams = title_teams(e.get("title", ""))
                    if teams and [t.lower() for t in teams] != [o.lower() for o in outs]:
                        c["title order differs from outcome order"] += 1
                    sw = winner_outcome(e, outs, sport)
                    if sw is None:
                        c["score gives no verdict"] += 1
                    elif sw == real:
                        c["AGREE"] += 1
                    else:
                        c["DISAGREE"] += 1
                        bad.append({"title": e["title"], "score": e.get("score"), "period": e.get("period"), "outcomes": outs, "prices": px})
            if len(evs) < 100: break
            offset += 100
        out[lg] = {"counts": dict(c), "disagree": bad[:20]}
        print(lg, dict(c), flush=True)
        for b in bad[:5]: print("   DISAGREE:", b)
json.dump(out, open("data/score_check.json", "w"), indent=1)
