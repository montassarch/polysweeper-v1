"""Live cross-check (run after flashscore_live_probe.py and sports_ws_record.py ran together):
for tennis / esports matches that finished while both were recording: Flashscore's own change stamp (DD) and our first sight of 'finished',
versus Polymarket's Sports WebSocket 'ended' (its finishedTimestamp and the time we received the message). Negative = Flashscore earlier."""
import collections, datetime, glob, json, statistics, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lab"))
from flashscore_ao_lag import norm  # noqa: E402


def same_player(poly_name, fs_name):
    """loose: any surname token (len>2) of the Flashscore name (singles 'Surname I.' or doubles 'A A./B B.') appears in the Polymarket name."""
    p = set(norm(poly_name))
    toks = [w for part in fs_name.split("/") for w in norm(part) if len(w) > 2]
    return bool(toks) and any(w in p for w in toks)



fs, ws = [], {}
for f in glob.glob(str(ROOT / "lab/data/raw/flashscore_live/*.jsonl")):
    for l in open(f, encoding="utf8"):
        try:
            r = json.loads(l)
        except ValueError:
            continue
        if r.get("DA") == "3" and r.get("DD"):
            fs.append(r)
for f in glob.glob(str(ROOT / "lab/data/raw/sports_ws/*.jsonl")):
    for l in open(f, encoding="utf8"):
        try:
            r = json.loads(l)
        except ValueError:
            continue
        m = r.get("m")
        if isinstance(m, dict) and m.get("ended") and m.get("finishedTimestamp"):
            key = (m.get("leagueAbbreviation"), m.get("homeTeam"), m.get("awayTeam"))
            if key not in ws:
                ws[key] = (r["t"], datetime.datetime.fromisoformat(m["finishedTimestamp"][:26].replace("Z", "") + "+00:00").timestamp(), m)
rows = []
for r in fs:
    name = (r["name"] or "").split("|")[0]
    if " vs " not in name:
        continue
    a, b = [x.strip() for x in name.split(" vs ")]
    for (lg, h, aw), (trecv, fin, m) in ws.items():
        if h and aw and ((same_player(h, a) and same_player(aw, b)) or (same_player(h, b) and same_player(aw, a))):
            rows.append({"match": f"{h} v {aw}", "league": lg, "fs_DD_vs_ws_finished": int(r["DD"]) - fin, "fs_first_seen_vs_ws_received": r["t"] - trecv})
print("matches seen by both:", len(rows))
for x in rows:
    print(x)
v = [x["fs_DD_vs_ws_finished"] for x in rows]
if v:
    print("Flashscore change stamp minus Polymarket WS finishedTimestamp (s): median", statistics.median(v), "min", min(v), "max", max(v))
