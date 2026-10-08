"""Backup study (market making), part 2: adverse selection. What happens to a maker after a fill?

Read-only, public data only. For a sample of markets per type:
- every recent taker trade (Data API /trades, takerOnly=true): the maker is on the other side;
- the 1-minute mid series (CLOB /prices-history, fidelity=1);
- maker result per share, in cents, after 1, 10 and 60 minutes (vs the later mid), and for settled markets at the
  final result (0 or 1). Positive = the maker made money, negative = the maker was picked off.
- price jumps: how many 1-minute mid moves of 2c, 5c, 10c+ per market-day (a resting quote that close gets run over).

Usage: py -3 lab/mm_markout.py      -> lab/results/2026-10-08-mm-markout.json
"""
import json, os, random, sys, time, urllib.request, collections, statistics, datetime, bisect

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, "data", "raw", "mm")
UA = {"User-Agent": "polysweeper-research/0.1 (read-only data collection)"}
NOW = time.time()
H = (60, 600, 3600)


def get(url, tries=4):
    err = None
    for i in range(tries):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60))
        except Exception as e:  # noqa
            err = e
            if "400" in str(e) or "422" in str(e):
                break
            time.sleep(1.5 * (i + 1))
    print("FAILED", url[:110], err, file=sys.stderr)
    return None


def trades(cid, since, pages=25):
    """Data API v2, taker rows only (one row per fill), newest first, cursor paging."""
    out, cur = [], None
    for k in range(pages):
        u = f"https://data-api.polymarket.com/v2/trades?condition={cid}&limit=1000&taker_only=true"
        if cur:
            u += "&cursor=" + cur
        d = get(u)
        if not d or not d.get("data"):
            break
        for x in d["data"]:
            out.append({"timestamp": x["timestamp"], "price": x["price"], "size": x["size"], "side": x["side"],
                        "outcomeIndex": x.get("outcome_index", 0)})
        cur = (d.get("pagination") or {}).get("next_cursor")
        if not cur or out[-1]["timestamp"] < since:
            break
        time.sleep(0.1)
    return [x for x in out if x["timestamp"] >= since]


def mids(tok, t0, t1):
    pts = []
    t = t0
    while t < t1:
        e = min(t + 86400, t1)
        d = get(f"https://clob.polymarket.com/prices-history?market={tok}&startTs={int(t)}&endTs={int(e)}&fidelity=1")
        if d:
            pts += [(p["t"], p["p"]) for p in d.get("history", [])]
        t = e
        time.sleep(0.1)
    pts = sorted(set(pts))
    return pts


def analyse(m, kind):
    """kind = live (last 48 h) or closed (whole tape up to 4,000 trades, result known)."""
    if kind == "live":
        since = NOW - 48 * 3600
    else:
        since = NOW - 14 * 86400  # markets that ended 1-7 days ago: their last 1-2 weeks
    tr = trades(m["cid"], since)
    if len(tr) < 20:
        return None
    t0 = min(x["timestamp"] for x in tr) - 120
    t1 = max(x["timestamp"] for x in tr) + 3700
    t1 = min(t1, NOW)
    ser = mids(m["tok"], t0, t1)
    if len(ser) < 30:
        return None
    ts = [a for a, _ in ser]
    ps = [b for _, b in ser]

    def mid_at(t, after):
        if after:
            i = bisect.bisect_left(ts, t)
            return ps[i] if i < len(ps) else None
        i = bisect.bisect_right(ts, t) - 1
        return ps[i] if i >= 0 else None

    rows = []
    game = None
    if m.get("game"):
        try:
            game = datetime.datetime.fromisoformat(m["game"].replace("Z", "+00:00")).timestamp()
        except Exception:
            game = None
    for x in tr:
        p = float(x["price"])
        sz = float(x["size"])
        s = 1 if x["side"] == "BUY" else -1
        if int(x.get("outcomeIndex", 0)) == 1:  # NO token -> YES terms
            p = 1 - p
            s = -s
        t = x["timestamp"]
        mb = mid_at(t - 1, False)
        r = {"t": t, "p": p, "s": s, "sz": sz, "half": (s * (p - mb)) if mb is not None else None}
        for h in H:
            mh = mid_at(t + h, True) if t + h <= ts[-1] else None
            r[h] = s * (p - mh) if mh is not None else None
        if kind == "closed" and m.get("outcome") is not None:
            r["res"] = s * (p - m["outcome"])
        r["phase"] = ("pre" if (game and t < game) else "live") if game else "na"
        if game and t < game:
            mg = mid_at(game - 1, False)  # last mid before the start (resting orders are cleared at the start)
            r["start"] = s * (p - mg) if mg is not None else None
        rows.append(r)
    # jumps per market-day on the 1-minute series (only while trading happened); sports: pre-game only
    pts = list(zip(ts, ps))
    if game:
        pts = [(a, b) for a, b in pts if a < game]
    if len(pts) < 10:
        pts = list(zip(ts, ps))
    span_days = max((pts[-1][0] - pts[0][0]) / 86400, 1 / 24)
    jumps = collections.Counter()
    for (_, a), (_, b) in zip(pts, pts[1:]):
        d = abs(b - a)
        for c in (0.02, 0.05, 0.10):
            if d >= c - 1e-9:
                jumps[c] += 1
    return rows, {f"jumps_{int(c * 100)}c_per_day": round(jumps[c] / span_days, 2) for c in (0.02, 0.05, 0.10)}


def summarize(allrows):
    out = {}
    w = sum(r["sz"] for r in allrows)
    if not w:
        return out
    for k in ("half",) + H + ("start", "res"):
        vals = [(r[k], r["sz"]) for r in allrows if r.get(k) is not None]
        if not vals:
            continue
        ww = sum(s for _, s in vals)
        out[f"maker_c_{k}"] = round(100 * sum(v * s for v, s in vals) / ww, 3)
        if k in (3600, "start", "res"):
            out[f"share_loss_2c_{k}"] = round(sum(s for v, s in vals if v <= -0.02) / ww, 3)
            out[f"share_loss_5c_{k}"] = round(sum(s for v, s in vals if v <= -0.05) / ww, 3)
            out[f"share_loss_10c_{k}"] = round(sum(s for v, s in vals if v <= -0.10) / ww, 3)
    out["trades"] = len(allrows)
    out["shares"] = round(w)
    return out


def main():
    sys.path.insert(0, ROOT)
    from mm_scan import mtype
    ev = json.load(open(os.path.join(RAW, "gamma-open-markets.json"), encoding="utf-8"))
    rw = {r["condition_id"]: r for r in json.load(open(os.path.join(RAW, "rewards-current.json"), encoding="utf-8"))}
    by = collections.defaultdict(list)
    for m in ev:
        r = rw.get(m["cid"])
        m["rate"] = (r.get("total_daily_rate") or 0) if r else 0
        if m["rate"] <= 0 or m["vol24"] < 1000:
            continue
        by[mtype(m)].append(m)
    random.seed(21)
    live = []
    for t, ms in by.items():
        live += [(t, m) for m in random.sample(ms, min(14, len(ms)))]
    # closed markets that ended 1-7 days ago (result known)
    closed = []
    end_min = datetime.datetime.fromtimestamp(NOW - 7 * 86400, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    end_max = datetime.datetime.fromtimestamp(NOW - 3600 * 6, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cm = []
    for off in range(0, 1500, 100):
        d = get(f"https://gamma-api.polymarket.com/markets?closed=true&end_date_min={end_min}&end_date_max={end_max}"
                f"&order=volumeNum&ascending=false&limit=100&offset={off}&include_tag=true")
        if not d:
            break
        cm += d
        if len(d) < 100:
            break
        time.sleep(0.15)
    cby = collections.defaultdict(list)
    for x in cm:
        try:
            toks = json.loads(x.get("clobTokenIds") or "[]")
            op = [float(v) for v in json.loads(x.get("outcomePrices") or "[]")]
        except Exception:
            continue
        if len(toks) != 2 or len(op) != 2 or float(x.get("volumeNum") or 0) < 2000:
            continue
        if op[0] not in (0.0, 1.0) and op[0] != 0.5:
            continue
        mm = {"cid": x["conditionId"], "q": (x.get("question") or "")[:100], "tok": toks[0], "outcome": op[0],
              "tags": [t.get("slug") for t in (x.get("tags") or [])], "fee": x.get("feeSchedule"),
              "clear": x.get("clearBookOnStart"), "game": x.get("gameStartTime"), "end": x.get("endDate"),
              "smt": x.get("sportsMarketType"), "vol24": 0, "ev": "", "negRisk": x.get("negRisk")}
        mt = mtype(mm)
        # closed markets: 'game within 3 days' test does not apply, use clearBookOnStart
        cby[mt].append(mm)
    for t, ms in cby.items():
        closed += [(t, m) for m in random.sample(ms, min(12, len(ms)))]
    print("live sample", len(live), "closed sample", len(closed), collections.Counter(t for t, _ in closed))
    res = {"live": collections.defaultdict(list), "closed": collections.defaultdict(list)}
    jumps = {"live": collections.defaultdict(list), "closed": collections.defaultdict(list)}
    examples = []
    for kind, lst in (("live", live), ("closed", closed)):
        for t, m in lst:
            a = analyse(m, kind)
            if not a:
                continue
            rows, j = a
            res[kind][t] += rows
            jumps[kind][t].append(j)
            s = summarize(rows)
            examples.append({"kind": kind, "type": t, "q": m["q"][:70], **{k: s.get(k) for k in ("trades", "maker_c_half", "maker_c_3600", "maker_c_res")}, **j})
            print(kind, t, m["q"][:50], s.get("trades"), s.get("maker_c_half"), s.get("maker_c_3600"), s.get("maker_c_res"), j)
    out = {"made": datetime.datetime.now(datetime.timezone.utc).isoformat(), "by_type": {}}
    for kind in ("live", "closed"):
        for t, rows in res[kind].items():
            s = summarize(rows)
            js = jumps[kind][t]
            for k in ("jumps_2c_per_day", "jumps_5c_per_day", "jumps_10c_per_day"):
                s[k + "_median"] = statistics.median([j[k] for j in js])
            s["markets"] = len(js)
            if t.startswith("sports_game") and kind == "closed":
                for ph in ("pre", "live"):
                    sub = [r for r in rows if r["phase"] == ph]
                    if sub:
                        s["phase_" + ph] = summarize(sub)
            out["by_type"][f"{kind}:{t}"] = s
    out["markets"] = examples
    json.dump(out, open(os.path.join(ROOT, "results", "2026-10-08-mm-markout.json"), "w"), indent=1)
    print(json.dumps(out["by_type"], indent=1))


if __name__ == "__main__":
    main()
