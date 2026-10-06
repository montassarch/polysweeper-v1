"""Flashscore result timing vs Polymarket and our shadow clock, after the fact (tennis).

Idea #20, owner focus #2. Flashscore's day feed stores, per finished match, AO = the time (unix s) of the
match row's last change. For a finished match this is (at most) the moment Flashscore showed the final result.
We join those with shadow mode's tennis end windows (t0 = when our shadow mode saw the result through
Polymarket's score field; v1_gone = when our 0.96-0.995 band emptied, relative to t0) and Polymarket's own
`finishedTimestamp`. Negative = earlier than the comparison clock.

  python3 lab/flashscore_ao_lag.py            (needs lab/data/raw/flashscore/*.txt from flashscore_fetch.py)
  -> lab/results/<date>-flashscore-ao-lag.json
"""
import collections, datetime, glob, json, re, statistics, sys, unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lab"))
sys.path.insert(0, str(ROOT / "code"))
from flashscore_fetch import parse                       # noqa: E402
from polysweeper.collector import get_json, GAMMA, parse_ts  # noqa: E402

EVENTS = ROOT / "code/data/shadow/events.jsonl"


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z ]", " ", s.replace("-", " ")).split()


def same_player(poly_name, fs_name):
    """poly 'Omar Jasika' vs flashscore 'Jasika O.' (surname + initial)."""
    p, f = norm(poly_name), norm(fs_name)
    if not p or not f:
        return False
    init = f[-1] if len(f[-1]) == 1 else None
    sur = [w for w in f if len(w) > 1]
    return bool(sur) and all(w in p for w in sur) and (init is None or any(w.startswith(init) for w in p if w not in sur))


def load_fs():
    seen = {}
    for path in sorted(glob.glob(str(ROOT / "lab/data/raw/flashscore/sport2_off*.txt"))):
        for m in parse(Path(path).read_text(encoding="utf8")):
            if m.get("AB") == "3" and m.get("AO", "").isdigit():
                seen[m["AA"]] = m                      # newest file wins
    return list(seen.values())


def poly_finished(market_id, cache={}):
    if market_id not in cache:
        m = get_json(f"{GAMMA}/markets/{market_id}")
        ev = ((m or {}).get("events") or [{}])[0]
        cache[market_id] = parse_ts(ev.get("finishedTimestamp")) if ev.get("finishedTimestamp") else None
    return cache[market_id]


def med(x):
    return round(statistics.median(x), 1) if x else None


def main():
    fs = load_fs()
    print("flashscore finished matches:", len(fs))
    rows, unmatched = [], 0
    for line in EVENTS.read_text(encoding="utf8").splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("type") != "end_window" or d.get("league") not in ("atp", "wta") or "stopped" in (d.get("closed_because") or ""):
            continue
        outs = d.get("outcomes") or []
        if len(outs) != 2:
            continue
        cands = [m for m in fs if abs(int(m["AD"]) - d["t0"]) < 8 * 3600 and
                 ((same_player(outs[0], m["AE"]) and same_player(outs[1], m["AF"])) or
                  (same_player(outs[0], m["AF"]) and same_player(outs[1], m["AE"])))]
        if len(cands) != 1:
            unmatched += 1
            continue
        m = cands[0]
        t0, ao = d["t0"], int(m["AO"])
        pf = poly_finished(d["market_id"])
        rows.append({"title": d["title"][:70], "league": d["league"], "t0": round(t0), "trigger": d["first_trigger"],
                     "fs_ao_vs_t0": round(ao - t0, 1),
                     "poly_finished_vs_t0": None if pf is None else round(pf - t0, 1),
                     "fs_ao_vs_poly_finished": None if pf is None else round(ao - pf, 1),
                     "band_gone_vs_t0": d.get("live_v1_until_s"), "bid99_vs_t0": d.get("live_bid099_at_s"),
                     "fs_ao_vs_band_gone": None if d.get("live_v1_until_s") is None else round(ao - t0 - d["live_v1_until_s"], 1),
                     "fs_start_to_ao_min": round((ao - int(m["AD"])) / 60), "fs_status": m.get("AC"), "score": d.get("score_at_start")})
    print("tennis end windows matched:", len(rows), "unmatched/ambiguous:", unmatched)
    summ = {}
    for k in ("fs_ao_vs_t0", "poly_finished_vs_t0", "fs_ao_vs_poly_finished", "band_gone_vs_t0", "bid99_vs_t0", "fs_ao_vs_band_gone"):
        v = [r[k] for r in rows if r[k] is not None]
        if v:
            v.sort()
            summ[k] = {"n": len(v), "median": med(v), "p10": v[len(v) // 10], "p90": v[(9 * len(v)) // 10], "min": v[0], "max": v[-1]}
            print(f"{k:24} n={len(v):3} median {summ[k]['median']:8} p10 {summ[k]['p10']:8} p90 {summ[k]['p90']:8}  (min {v[0]}, max {v[-1]})")
    out = ROOT / "lab/results" / f"{datetime.date.today()}-flashscore-ao-lag.json"
    out.write_text(json.dumps({"summary": summ, "rows": rows}, indent=1), encoding="utf8")
    print("saved", out)


if __name__ == "__main__":
    main()
