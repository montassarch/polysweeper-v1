"""What game states does the best wallet's TAKER buying at 0.95+ happen in? MLB first (public MLB Stats API, play by play).

For each MLB taker buy of wallet 4ddc (hit an ask at >= 0.95): inning, half, outs, score at that second (from the play-by-play end times),
market type, and whether the line was already arithmetically locked (totals: runs so far vs the line).
  python3 lab/wallet_mlb_state.py
"""
import collections, json, re, statistics, sys, time
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lab")); sys.path.insert(0, str(ROOT / "code"))
from mktinfo import lookup  # noqa: E402
from polysweeper.collector import get_json  # noqa: E402

MLB = "https://statsapi.mlb.com/api/v1"
trades = [json.loads(l) for l in (ROOT / "lab/data/raw/wallets/4ddc.jsonl").read_text().splitlines() if l.strip()]
key = lambda t: (t["transactionHash"], t["asset"], t["side"], round(float(t["size"]), 4), round(float(t["price"]), 4))
takers = {key(json.loads(l)) for l in (ROOT / "lab/data/raw/wallets/4ddc_takeronly.jsonl").read_text().splitlines() if l.strip()}
buys = [t for t in trades if t["side"] == "BUY" and float(t["price"]) >= 0.95 and t["eventSlug"].startswith("mlb-")]
print("mlb buys >=0.95:", len(buys), "taker:", sum(key(t) in takers for t in buys))
info = lookup([t["conditionId"] for t in buys])
_sched = {}


def sched(date):
    if date not in _sched:
        s = get_json(f"{MLB}/schedule?sportId=1&date={date}&hydrate=team") or {"dates": []}
        _sched[date] = [(g["gamePk"], g["teams"]["away"]["team"].get("abbreviation", "").lower(), g["teams"]["home"]["team"].get("abbreviation", "").lower())
                        for d in s["dates"] for g in d["games"]]
    return _sched[date]


_feed = {}


def plays(pk):
    if pk not in _feed:
        f = get_json(f"{MLB}/../v1.1/game/{pk}/feed/live".replace("/v1/../", "/")) or {}
        out = []
        for p in (f.get("liveData", {}).get("plays", {}).get("allPlays") or []):
            et = p["about"].get("endTime")
            if not et:
                continue
            out.append((datetime.fromisoformat(et.replace("Z", "+00:00")).timestamp(), p["about"]["inning"], p["about"]["halfInning"],
                        p["count"]["outs"] if "count" in p else None, p["result"].get("awayScore"), p["result"].get("homeScore")))
        out.sort()
        _feed[pk] = out
    return _feed[pk]


rows, miss = [], 0
for t in buys:
    slug = t["eventSlug"]
    m = re.match(r"^mlb-([a-z]+)-([a-z]+)-(\d{4}-\d{2}-\d{2})", slug)
    if not m:
        miss += 1; continue
    away, home, date = m.groups()
    pk = next((pk for pk, a, h in sched(date) if a == away and h == home), None)
    if not pk:
        miss += 1; continue
    pl = plays(pk)
    ts = t["timestamp"]
    before = [p for p in pl if p[0] <= ts]
    st = before[-1] if before else None
    mi = info.get(t["conditionId"]) or {}
    final = mi.get("final")
    won = final[t["outcomeIndex"]] if final else None
    last_end = pl[-1][0] if pl else None
    rows.append({"taker": key(t) in takers, "type": mi.get("type"), "price": float(t["price"]), "size": float(t["size"]), "title": t["title"],
                 "outcome": t["outcome"], "inning": st[1] if st else 0, "half": st[2] if st else None, "outs": st[3] if st else None,
                 "away": st[4] if st else None, "home": st[5] if st else None, "after_final_out_s": (ts - last_end) if last_end else None,
                 "won": won})
print("rows", len(rows), "unmatched", miss)
tk = [r for r in rows if r["taker"]]
print("\nTAKER MLB buys:", len(tk), "lost", sum(1 for r in tk if r["won"] == 0))
print(" by market type:", collections.Counter(r["type"] for r in tk).most_common())
print(" moneyline taker buys by inning (state = last completed play):")
ml = [r for r in tk if r["type"] == "moneyline"]
for inn, n in sorted(collections.Counter((min(r["inning"], 10) if r["after_final_out_s"] is not None and r["after_final_out_s"] < 0 else 99) for r in ml).items()):
    print("   inning", inn if inn != 99 else "AFTER final out", n)
print(" moneyline taker buys: lead of the side bought (runs):")
ld = collections.Counter()
for r in ml:
    if r["away"] is None or r["after_final_out_s"] is None or r["after_final_out_s"] >= 0:
        continue
    # side bought is r['outcome'] (team name); lead sign unknown without mapping -> use absolute score diff
    ld[abs((r["away"] or 0) - (r["home"] or 0))] += 1
print("   |score diff|:", sorted(ld.items()))
print(" taker buys AFTER the final out:", sum(1 for r in tk if r["after_final_out_s"] is not None and r["after_final_out_s"] >= 0),
      " median seconds after the last play:", statistics.median([r["after_final_out_s"] for r in tk if r["after_final_out_s"] is not None and r["after_final_out_s"] >= 0] or [0]))
print(" totals taker buys: runs so far vs line (Over locked if runs > line):")
c = collections.Counter()
for r in tk:
    if r["type"] != "totals":
        continue
    mm = re.search(r"O/U ([\d.]+)", r["title"])
    if not mm or r["away"] is None:
        continue
    line, runs = float(mm.group(1)), (r["away"] or 0) + (r["home"] or 0)
    over = r["outcome"].lower().startswith("over")
    pre = r["after_final_out_s"] is not None and r["after_final_out_s"] < 0
    c[("Over" if over else "Under", "locked (runs>line)" if (over and runs > line) else "final already" if not pre else "not locked", "inning " + str(min(r["inning"], 10)))] += 1
for k, n in sorted(c.items()): print("   ", k, n)
print(" spreads taker buys by inning:", sorted(collections.Counter(min(r["inning"], 10) for r in tk if r["type"] == "spreads" and (r["after_final_out_s"] or -1) < 0).items()))
print(" other taker types by inning:", collections.Counter((r["type"], min(r["inning"], 10)) for r in tk if r["type"] not in ("moneyline", "totals", "spreads")).most_common(8))
