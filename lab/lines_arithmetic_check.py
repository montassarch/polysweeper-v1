"""Do full-game spreads / totals / team totals settle exactly as arithmetic on the FINAL score says? (after-the-end 'safe line' check)
Uses Polymarket's own event `score` (away-home). For MLB it is cross-checked against the MLB Stats API final runs.
Markets: totals 'A vs. B: O/U L' [Over, Under]; spreads 'Spread: T (-L)' [T, other]; team totals 'T Team Total: O/U L'; moneyline.
  python3 lab/lines_arithmetic_check.py
"""
import collections, json, re, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
from polysweeper.collector import get_json  # noqa: E402

ev = [e for e in json.loads((ROOT / "lab/data/raw/usports_events.json").read_text()) if e["slug"] == e["game"] and e.get("score")]
stats = collections.defaultdict(lambda: [0, 0]); bad = []
mlb_official = {}
for d in sorted({time.strftime("%Y-%m-%d", time.gmtime(e["start"] - 6 * 3600)) for e in ev if e["sport"] == "MLB" and e.get("start")}):
    s = get_json(f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={d}&hydrate=team,linescore") or {"dates": []}
    for x in s["dates"]:
        for g in x["games"]:
            if g["status"]["abstractGameState"] == "Final":
                a, h = g["teams"]["away"]["team"].get("abbreviation", "").lower(), g["teams"]["home"]["team"].get("abbreviation", "").lower()
                k = f"mlb-{a}-{h}-{g.get('officialDate', d)}"
                mlb_official[k] = None if k in mlb_official else (g["teams"]["away"].get("score"), g["teams"]["home"].get("score"))   # doubleheader: two games, one slug -> skip
mismatch_score = 0
for e in ev:
    try:
        a, h = [int(x) for x in e["score"].split("-")]
    except ValueError:
        continue
    if e["sport"] == "MLB" and e["slug"] in mlb_official and mlb_official[e["slug"]] is None:
        continue                                                 # doubleheader day for these two teams: not matched
    if e["sport"] == "MLB" and e["slug"] in mlb_official and mlb_official[e["slug"]] != (a, h):
        mismatch_score += 1
        if all(v is not None for v in mlb_official[e["slug"]]):
            a, h = mlb_official[e["slug"]]                      # trust the official score
    mt = re.match(r"^[a-z]+-([a-z0-9]+)-([a-z0-9]+)-\d{4}", e["slug"])
    for m in e["markets"]:
        try:
            px = [float(x) for x in json.loads(m["final"])]
        except (TypeError, ValueError):
            continue
        if sorted(px) != [0.0, 1.0]:
            continue
        won = px.index(1.0)
        q, typ = m["q"], m["type"]
        pred = None
        if typ == "totals":
            mm = re.search(r"O/U ([\d.]+)$", q)
            if mm:
                pred = 0 if a + h > float(mm.group(1)) else 1
        elif typ == "spreads":
            mm = re.match(r"^Spread: (.+) \(([-+][\d.]+)\)$", q)
            if mm and m.get("outcomes"):
                outs = json.loads(m["outcomes"]) if isinstance(m["outcomes"], str) else m["outcomes"]
                team, line = mm.group(1), float(mm.group(2))
                # which side is the away team? use outcomes order of the moneyline of the same event
                ml = [x for x in e["markets"] if x["type"] == "moneyline"]
                if ml:
                    mo = json.loads(ml[0]["outcomes"]) if isinstance(ml[0]["outcomes"], str) else ml[0]["outcomes"]
                    away_team = mo[0]
                    margin = (a - h) if team == away_team else (h - a)
                    pred = 0 if margin + line > 0 else 1
        elif typ == "team_totals":
            mm = re.match(r"^(.+) Team Total: O/U ([\d.]+)$", q)
            if mm:
                ml = [x for x in e["markets"] if x["type"] == "moneyline"]
                if ml:
                    mo = json.loads(ml[0]["outcomes"]) if isinstance(ml[0]["outcomes"], str) else ml[0]["outcomes"]
                    runs = a if mm.group(1) == mo[0] else h if mm.group(1) == mo[1] else None
                    if runs is not None:
                        pred = 0 if runs > float(mm.group(2)) else 1
        elif typ == "moneyline":
            ml_out = json.loads(m["outcomes"]) if isinstance(m["outcomes"], str) else m["outcomes"]
            if len(ml_out) == 2 and a != h:
                pred = 0 if a > h else 1
        if pred is None:
            continue
        key = (e["sport"], typ)
        stats[key][0] += 1
        if pred == won:
            stats[key][1] += 1
        elif len(bad) < 40:
            bad.append((e["slug"], q[:60], e["score"], "pred", pred, "actual", won))
print("MLB games where Polymarket's score differs from the MLB official final:", mismatch_score)
for (sp, typ), (n, ok) in sorted(stats.items()):
    print(f"  {sp:5} {typ:12} markets {n:5}  arithmetic matched settlement {ok:5}  ({ok/n:.2%})")
print("mismatches (first 25):")
for b in bad[:25]:
    print("  ", b)
(ROOT / "lab/results" / f"{time.strftime('%Y-%m-%d')}-lines-arithmetic-check.json").write_text(json.dumps({f"{k[0]}:{k[1]}": {"markets": v[0], "matched": v[1]} for k, v in stats.items()}, indent=1))
