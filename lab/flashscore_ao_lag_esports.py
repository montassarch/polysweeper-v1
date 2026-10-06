"""Flashscore finish stamp (AO) vs our shadow clock for esports (CS2, LoL, Dota 2): same idea as flashscore_ao_lag.py (tennis)."""
import collections, datetime, glob, json, re, statistics, sys, unicodedata
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lab"))
from flashscore_fetch import parse  # noqa: E402

LEAGUE = {"cs2": "COUNTER", "lol": "LEAGUE OF LEGENDS", "dota2": "DOTA"}


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(team|esports|gaming|gg|club|esport)\b", " ", s)
    return re.sub(r"[^a-z0-9]", "", s)


def same(a, b):
    a, b = norm(a), norm(b)
    return bool(a) and bool(b) and (a == b or (len(min(a, b, key=len)) >= 4 and (a in b or b in a)))


fs = {}
for p in sorted(glob.glob(str(ROOT / "lab/data/raw/flashscore/sport36_off*.txt"))):
    for m in parse(Path(p).read_text(encoding="utf8")):
        if m.get("AB") == "3" and m.get("AO", "").isdigit():
            fs[m["AA"]] = m
fs = list(fs.values())
rows, miss = [], collections.Counter()
for line in (ROOT / "code/data/shadow/events.jsonl").read_text(encoding="utf8").splitlines():
    try:
        d = json.loads(line)
    except ValueError:
        continue
    if d.get("type") != "end_window" or d.get("league") not in LEAGUE or "stopped" in (d.get("closed_because") or ""):
        continue
    outs = d.get("outcomes") or []
    if len(outs) != 2:
        continue
    c = [m for m in fs if LEAGUE[d["league"]] in m["_league"].upper() and abs(int(m["AO"]) - d["t0"]) < 3 * 3600 and
         ((same(outs[0], m["AE"]) and same(outs[1], m["AF"])) or (same(outs[0], m["AF"]) and same(outs[1], m["AE"])))]
    if len(c) != 1:
        miss[d["league"]] += 1
        continue
    m = c[0]
    ao, t0 = int(m["AO"]), d["t0"]
    rows.append({"league": d["league"], "title": d["title"][:60], "trigger": d["first_trigger"], "fs_ao_vs_t0": round(ao - t0, 1),
                 "band_gone_vs_t0": d.get("live_v1_until_s"), "bid99_vs_t0": d.get("live_bid099_at_s"),
                 "fs_ao_vs_band_gone": None if d.get("live_v1_until_s") is None else round(ao - t0 - d["live_v1_until_s"], 1),
                 "score_at_start": d.get("score_at_start")})
print("flashscore finished esports matches:", len(fs), " end windows matched:", len(rows), " unmatched:", dict(miss), " by league:", dict(collections.Counter(r["league"] for r in rows)))
for k in ("fs_ao_vs_t0", "band_gone_vs_t0", "bid99_vs_t0", "fs_ao_vs_band_gone"):
    v = sorted(r[k] for r in rows if r[k] is not None)
    if v:
        print(f"{k:20} n={len(v):3} median {statistics.median(v):8.1f} p10 {v[len(v)//10]:8.1f} p90 {v[9*len(v)//10]:8.1f} min {v[0]} max {v[-1]}")
for r in sorted(rows, key=lambda r: r["fs_ao_vs_t0"])[:25]:
    print(r["league"], r["fs_ao_vs_t0"], r["band_gone_vs_t0"], r["fs_ao_vs_band_gone"], r["title"])
out = ROOT / "lab/results" / f"{datetime.date.today()}-flashscore-ao-lag-esports.json"
out.write_text(json.dumps(rows, indent=1), encoding="utf8")
