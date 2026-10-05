"""Game state -> supply map (owner focus #1, 2026-10-05).

For every row of the PC's score log (code/data/shadow/daily/*.jsonl: one row per Polymarket score
change, with best bid/ask of both sides), classify the game state, find the side that leads on the
score, and record whether the leader's best ask sat in our band (0.96-0.995), how long the state
lasted (seconds to the next score row), and whether the leader won (Gamma resolution).
Depth is not in the score log: it is taken from pretend-buy entries (trades.jsonl asks_top5) that
match the same match and score.

Run: python3 lab/state_supply.py  -> lab/results/2026-10-05-state-supply.json (+ printed tables)
"""
import collections
import glob
import json
import os
import re
import statistics
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "code"))
from polysweeper.collector import GAMMA, get_json  # noqa: E402
from polysweeper.scorecheck import series_length  # noqa: E402

SHADOW = os.path.join(ROOT, "code", "data", "shadow")
RAW = os.path.join(ROOT, "lab", "data", "raw", "state_supply_markets.json")
OUT = os.path.join(ROOT, "lab", "results", "2026-10-05-state-supply.json")
LO, HI = 0.96, 0.995
SPORT = {"atp": "tennis", "wta": "tennis", "cs2": "cs2", "val": "val", "lol": "lol", "dota2": "dota2",
         "nfl": "nfl", "nhl": "nhl", "mlb": "mlb"}
for k in ("mlbb", "hok", "r6siege", "ow"):
    SPORT[k] = "esports_other"
TB = re.compile(r"\(.*?\)")


def load_rows():
    rows = []
    for f in sorted(glob.glob(os.path.join(SHADOW, "daily", "*.jsonl"))):
        for line in open(f):
            r = json.loads(line)
            if r.get("type") == "score":
                rows.append(r)
    return rows


def resolutions(mids):
    cache = json.load(open(RAW)) if os.path.exists(RAW) else {}
    todo = [m for m in mids if m not in cache or not cache[m].get("closed")]
    for i in range(0, len(todo), 40):
        chunk = todo[i:i + 40]
        got = []
        for extra in ("&closed=true", "&closed=false"):
            got += get_json(f"{GAMMA}/markets?" + "&".join(f"id={x}" for x in chunk) + "&limit=100" + extra) or []
        for m in got:
            try:
                prices = [float(p) for p in json.loads(m.get("outcomePrices") or "[]")]
            except ValueError:
                prices = []
            cache[str(m["id"])] = {"closed": m.get("closed"), "prices": prices,
                                   "outcomes": json.loads(m.get("outcomes") or "[]"),
                                   "uma": m.get("umaResolutionStatus")}
        time.sleep(0.3)
    os.makedirs(os.path.dirname(RAW), exist_ok=True)
    json.dump(cache, open(RAW, "w"))
    return cache


def winner_idx(res):
    if not res or len(res.get("prices", [])) != 2:
        return None
    if not res.get("closed") and not (res.get("uma") == "proposed" and max(res["prices"]) >= 0.99):
        return None
    p = res["prices"]
    if p[0] > 0.9:
        return 0
    if p[1] > 0.9:
        return 1
    return "void"


# ---------- state classifiers: return (leader_idx or None, fine_label, coarse_bucket) ----------

def tennis_state(score, period):
    if not score or "|" in score:
        return None
    sets = []
    for part in score.split(","):
        m = re.fullmatch(r"(\d+)-(\d+)", TB.sub("", part).strip())
        if not m:
            return None
        sets.append((int(m.group(1)), int(m.group(2))))
    done, cur = [], None
    for i, (a, b) in enumerate(sets):
        finished = (max(a, b) >= 6 and abs(a - b) >= 2) or (a, b) in ((7, 6), (6, 7))
        if finished and not (i == len(sets) - 1 and period == f"S{len(sets)}" and False):
            done.append((a, b))
        else:
            cur = (a, b)
    if cur is None:
        cur = (0, 0)
    s = [sum(a > b for a, b in done), sum(b > a for a, b in done)]
    if s[0] != s[1]:
        L = 0 if s[0] > s[1] else 1
    elif cur[0] != cur[1]:
        L = 0 if cur[0] > cur[1] else 1
    else:
        return (None, f"sets {s[0]}-{s[1]} games {cur[0]}-{cur[1]}", "level")
    ls, os_ = s[L], s[1 - L]
    lg, og = cur[L], cur[1 - L]
    fine = f"sets {ls}-{os_}, games {lg}-{og}"
    if ls == 2 or (ls == 1 and os_ == 0 and False):
        return (L, fine, "match won on score")
    if ls == 1 and os_ == 0:
        ctx = "1 set up"
    elif ls == os_ == 1:
        ctx = "deciding set"
    else:
        ctx = "first set"
    d = lg - og
    if d >= 3 and lg >= 5:
        g = "5+ games, lead 3+ (serving/receiving for set)"
    elif d >= 2 and lg >= 5:
        g = "5+ games, lead 2"
    elif d >= 3:
        g = "lead 3+ games"
    elif d >= 1:
        g = "lead 1-2 games"
    elif d == 0:
        g = "games level"
    else:
        g = "behind in set"
    return (L, fine, f"{ctx}: {g}")


def esports_state(score, period, title, league):
    m = re.fullmatch(r"(\d+)-(\d+)\|(\d+)-(\d+)\|Bo(\d+)", score or "")
    if not m:
        return None
    r1, r2, m1, m2, bo = (int(x) for x in m.groups())
    if series_length({"title": title}, bo) is None:
        return (None, f"title/score BoN disagree ({score})", "series length unknown")
    need = bo // 2 + 1
    rounds_known = not (r1 == 0 and r2 == 0 and m.group(1) == "000")
    if m1 != m2:
        L = 0 if m1 > m2 else 1
    elif rounds_known and r1 != r2:
        L = 0 if r1 > r2 else 1
    else:
        return (None, f"maps {m1}-{m2}", f"Bo{bo} level")
    lm, om = (m1, m2)[L], (m1, m2)[1 - L]
    lr, orr = (r1, r2)[L], (r1, r2)[1 - L]
    if lm >= need:
        return (L, f"Bo{bo} maps {lm}-{om}", f"Bo{bo} series won on score")
    ctx = f"Bo{bo} {lm}-{om}" + (" (series point)" if lm == need - 1 else "")
    if not rounds_known or league not in ("cs2", "val"):
        return (L, ctx, ctx + ", rounds n/a")
    fine = f"{ctx}, rounds {lr}-{orr}"
    d = lr - orr
    if lr >= 12 and d >= 1:
        g = "map point (12+), ahead"
    elif lr >= 10 and d >= 4:
        g = "10+ rounds, lead 4+"
    elif d >= 4:
        g = "lead 4+ rounds"
    elif d >= 1:
        g = "lead 1-3 rounds"
    elif d == 0:
        g = "rounds level"
    else:
        g = "behind on map"
    return (L, fine, f"{ctx}: {g}")


def us_state(score, period, sport):
    m = re.fullmatch(r"(\d+)-(\d+)", score or "")
    if not m:
        return None
    a, b = int(m.group(1)), int(m.group(2))
    if a == b:
        return (None, f"{score} {period}", "tied")
    L = 0 if a > b else 1
    d = abs(a - b)
    if sport == "nfl":
        lead = "lead 1-8" if d <= 8 else "lead 9-16" if d <= 16 else "lead 17+"
    elif sport == "nhl":
        lead = "lead 1" if d == 1 else "lead 2" if d == 2 else "lead 3+"
    else:
        lead = "lead 1-2" if d <= 2 else "lead 3-4" if d <= 4 else "lead 5+"
    per = period or "?"
    if sport == "mlb":
        mm = re.search(r"(\d+)", per)
        inn = int(mm.group(1)) if mm else 0
        per = "inn 1-6" if inn <= 6 else "inn 7-8" if inn <= 8 else "inn 9+"
    return (L, f"{score} {period}", f"{per} {lead}")


def classify(r, title):
    sp = SPORT.get(r["league"], "other")
    if r.get("ended"):
        tag = "ENDED flag"
    else:
        tag = None
    if sp == "tennis":
        st = tennis_state(r["score"], r.get("period"))
    elif sp in ("nfl", "nhl", "mlb"):
        st = us_state(r["score"], r.get("period"), sp)
    else:
        st = esports_state(r["score"], r.get("period"), title, r["league"])
    if st is None:
        return None
    if tag and st[0] is not None:
        return (st[0], st[1], "after end (ended flag)")
    return st


def progress(r):
    """Monotonic 'how far the match is' key. The score log flickers between an old and a new score every few
    seconds (two Gamma caches); rows whose progress is below the highest seen are dropped as stale."""
    sc, per = r.get("score") or "", r.get("period") or ""
    pm = re.search(r"(\d+)", per)
    prank = (int(pm.group(1)) * 10 if pm else 0) + (5 if per.startswith(("End", "HT")) else 0)
    if per in ("FT", "VFT") or r.get("ended"):
        prank = 999
    nums = [int(x) for x in re.findall(r"\d+", TB.sub("", sc))]
    if "|" in sc:
        m = re.fullmatch(r"(\d+)-(\d+)\|(\d+)-(\d+)\|Bo\d+", sc)
        if m:
            r1, r2, m1, m2 = (int(x) for x in m.groups())
            return (m1 + m2, r1 + r2, prank)
    if "," in sc or SPORT.get(r["league"]) == "tennis":
        return (sc.count(",") + 1 if sc else 0, sum(nums), prank)
    return (sum(nums), prank, 0)


def clean_sequence(rs):
    out, best = [], None
    for r in sorted(rs, key=lambda r: r["t"]):
        p = progress(r)
        if best is not None and p < best:
            continue
        if out and p == best and (r["score"], r.get("period"), r.get("ended")) == (
                out[-1]["score"], out[-1].get("period"), out[-1].get("ended")):
            continue
        best = p
        out.append(r)
    return out


def new_stat():
    return {"matches": set(), "band_matches": set(), "band_seconds": collections.defaultdict(float),
            "leader_lost": set(), "band_lost": set(), "depth": [], "asks": [],
            "entries": 0, "entry_losses": []}


def main():
    rows = load_rows()
    meta = {}
    for r in rows:
        if r.get("title"):
            meta.setdefault(r["event_id"], {"title": r["title"], "outcomes": r.get("outcomes")})
    trades = [json.loads(l) for l in open(os.path.join(SHADOW, "trades.jsonl"))]
    entries = [e for e in trades if e.get("type") == "entry" and (e.get("rule") or "price_only") == "price_only"]
    settled = {((s.get("rule") or "price_only"), s["key"]): s for s in trades if s.get("type") == "settled"}
    mids = sorted({b[0] for r in rows for b in r["books"]} | {e["market_id"] for e in entries})
    res = resolutions(mids)
    by_ev = collections.defaultdict(list)
    for r in rows:
        by_ev[r["event_id"]].append(r)
    span_days = (max(r["t"] for r in rows) - min(r["t"] for r in rows)) / 86400
    stats = collections.defaultdict(new_stat)
    raw_n = clean_n = 0
    for eid, rs in by_ev.items():
        title = (meta.get(eid) or {}).get("title") or ""
        sp = SPORT.get(rs[0]["league"], "other")
        win = winner_idx(res.get(rs[0]["books"][0][0]))
        seq = clean_sequence(rs)
        raw_n += len(rs)
        clean_n += len(seq)
        for i, r in enumerate(seq):
            st = classify(r, title)
            if not st:
                continue
            L, fine, bucket = st
            s = stats[(sp, bucket)]
            s["matches"].add(eid)
            if L is None:
                continue
            if win in (0, 1) and win != L:
                s["leader_lost"].add(f"{title[:40]} @ {fine}")
            ask = next((b[3] for b in r["books"] if b[1] == L), None)
            if ask is not None and LO <= ask <= HI:
                s["band_matches"].add(eid)
                s["asks"].append(ask)
                if i + 1 < len(seq):
                    s["band_seconds"][eid] += seq[i + 1]["t"] - r["t"]
                if win in (0, 1) and win != L:
                    s["band_lost"].add(f"{title[:45]} @ {fine} ask {ask} {r['ts'][5:16]}")
    # pretend in-play buys (Sep 30 - now): exact in-band asks with depth, and real outcomes
    for e in entries:
        ev = e.get("event") or {}
        r = {"league": e["league"], "score": ev.get("score"), "period": ev.get("period"),
             "ended": e.get("event_ended_flag")}
        st = classify(r, e.get("question") or "")
        sp = SPORT.get(e["league"], "other")
        if not st:
            bucket, L = "no score / unparsed", None
        else:
            L, fine, bucket = st
        tok = e.get("token_idx", int(e["key"].split(":")[1]))
        if L is not None and L != tok:
            bucket = bucket + " [bought the TRAILING side]"
        s = stats[(sp, bucket)]
        s["entries"] += 1
        top5 = e.get("asks_top5") or []
        s["depth"].append({k: round(sum(q for p, q in top5 if p <= v), 1)
                           for k, v in (("le0.97", 0.97), ("le0.99", 0.99), ("le0.995", 0.995))})
        st_rec = settled.get(("price_only", e["key"])) or settled.get((e.get("rule"), e["key"]))
        if st_rec and st_rec.get("result") == "loss":
            s["entry_losses"].append(f"{e['outcome']} @ {ev.get('score')} {ev.get('period')} ask {e['best_ask']} "
                                     f"{e['ts'][5:16]}{' ENDED' if e.get('event_ended_flag') else ''}")

    def med(xs):
        return round(statistics.median(xs), 1) if xs else None
    out = {"score_log_days": round(span_days, 2), "score_rows_raw": raw_n, "score_rows_after_deflicker": clean_n,
           "matches": len(by_ev), "band": [LO, HI], "buckets": []}
    for (sp, bucket), s in sorted(stats.items()):
        secs = list(s["band_seconds"].values())
        out["buckets"].append({
            "sport": sp, "bucket": bucket, "matches": len(s["matches"]),
            "band_matches": len(s["band_matches"]),
            "band_matches_per_day": round(len(s["band_matches"]) / span_days, 1),
            "median_band_seconds_per_match": med(secs),
            "median_ask": statistics.median(s["asks"]) if s["asks"] else None,
            "leader_lost_matches": sorted(s["leader_lost"]), "band_losses": sorted(s["band_lost"]),
            "pretend_entries": s["entries"], "entry_losses": s["entry_losses"],
            "median_shares_le0.97": med([d["le0.97"] for d in s["depth"]]),
            "median_shares_le0.99": med([d["le0.99"] for d in s["depth"]]),
            "median_shares_le0.995_top5": med([d["le0.995"] for d in s["depth"]])})
    json.dump(out, open(OUT, "w"), indent=1)
    print({k: v for k, v in out.items() if k != "buckets"})
    for b in out["buckets"]:
        if not (b["band_matches"] or b["pretend_entries"] or b["leader_lost_matches"]):
            continue
        lostm = len({x.split(" @ ")[0] for x in b["leader_lost_matches"]})
        print(f"{b['sport']:8} {b['bucket'][:62]:62} m={b['matches']:3} band={b['band_matches']:3} "
              f"/d={b['band_matches_per_day']:4} sec={b['median_band_seconds_per_match']} "
              f"Llost={lostm} ent={b['pretend_entries']} sh97={b['median_shares_le0.97']} "
              f"sh99={b['median_shares_le0.99']}")
        for x in b["band_losses"]:
            print("      BANDLOSS", x)
        for x in b["entry_losses"]:
            print("      ENTRYLOSS", x)


if __name__ == "__main__":
    main()
