"""Tennis "match is over" bid test, LIVE (read-only, no orders, no keys).  Spin-off of the row-4 decided-state study (R-2026-10-09).

Question: when 365Scores / LiveScore say a tennis match is over (a median ~160 s before Polymarket's own flag), what does the winner's
order book look like, and would a 5-share resting buy placed `delay` seconds later have been filled by the retail sellers who are still
unloading, before Polymarket's finished stamp?  The queue is read from the REAL book at the "over" moment; the fill is replayed against
the public trades printed afterwards.

  python3 lab/tennis_end_bids.py record [hours=6]    wraps lab/feeds_end_race.py (same discovery/polling), tennis only, and saves the
                                                    full top-10 bids AND asks of both tokens at the first "over" moment of each source
  python3 lab/tennis_end_bids.py analyze             joins the saved matches with Gamma's result and the public tape ->
                                                    lab/results/2026-10-09-tennis-end-bids.json (+ prints a table)
Raw: lab/data/raw/tennis_end_bids/<utc date>.jsonl (git-ignored).  Standard library only.  Set POLYSWEEPER_NO_ALERTS=1 (nothing here alerts).

Fill model for a bid at price B placed at join = first "over" + delay:
  - queue ahead = shares bid at exactly B in the snapshot (0 if B is above the best bid or between levels);
  - bids ABOVE B do not matter: a taker print at or below B only happens after they are gone;
  - filled once public taker SELL prints with price <= B (and >= 0.95) on the winner's token, between join and the finished stamp, add up to queue + 5 shares.
Not modelled: cancels ahead of us (cautious: ignored), new bidders arriving above us, our own latency beyond `delay`.
"""
import collections, json, re, sys, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "lab"))
OUT = ROOT / "lab/data/raw/tennis_end_bids"
OUT.mkdir(parents=True, exist_ok=True)
DATA = "https://data-api.polymarket.com"


def record(hours):
    import feeds_end_race as F
    F.OUT = OUT
    F.SUMMARY = OUT / "feeds-summary.json"             # never touch the laptop's committed summary
    F.publish = lambda push: F.SUMMARY.write_text(json.dumps(F.summary(), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    orig = F.pm_live

    def pm_live_tennis():
        return [r for r in orig() if (r.get("series") or "").lower() in ("atp", "wta")]
    F.pm_live = pm_live_tennis

    def snap(rec):
        bk = F.books([t for t, _ in rec["tokens"]])
        out = []
        for i, (t, label) in enumerate(rec["tokens"]):
            b = bk.get(t, {})
            bids = sorted(((float(x["price"]), float(x["size"])) for x in b.get("bids", [])), reverse=True)[:10]
            asks = sorted((float(x["price"]), float(x["size"])) for x in b.get("asks", []))[:10]
            out.append({"idx": i, "label": label, "bids": bids, "asks": asks, "best_ask": asks[0][0] if asks else None})
        return {"t": round(time.time(), 2), "books": out}
    F.snap = snap
    F.main(hours)


# ---------------------------------------------------------------- analysis
def tape(cid, lo, hi):
    from polysweeper.collector import get_json
    rows, off = [], 0
    while off <= 5000:
        page = get_json(f"{DATA}/trades?market={cid}&limit=500&offset={off}")
        if not isinstance(page, list) or not page:
            break
        rows += page
        if min(t["timestamp"] for t in page) < lo or len(page) < 500:
            break
        off += 500
    return [t for t in rows if lo <= t["timestamp"] <= hi]


def analyze():
    from polysweeper.collector import get_json, GAMMA, parse_ts
    recs = []
    for f in sorted(OUT.glob("*.jsonl")):
        recs += [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]
    rows = []
    for r in recs:
        src = [(r.get("t_365"), r.get("at_365"), r.get("agree_365")), (r.get("t_ls"), r.get("at_ls"), r.get("agree_ls"))]
        src = [x for x in src if x[0] and x[1] and x[2] is not False]
        if not src:
            continue
        t_src, snapb, _ = min(src, key=lambda x: x[0])
        e = get_json(f"{GAMMA}/events/{r['event']}")
        if not isinstance(e, dict):
            continue
        ms = [m for m in e.get("markets", []) if m.get("sportsMarketType") == "moneyline"]
        if len(ms) != 1 or not e.get("finishedTimestamp"):
            continue
        m = ms[0]
        try:
            px = [float(x) for x in json.loads(m["outcomePrices"])]
        except Exception:
            continue
        if sorted(px) != [0.0, 1.0]:
            continue                                   # not settled yet (or void): analyse later
        fin = parse_ts(e["finishedTimestamp"])
        w = px.index(1.0)
        book = next((b for b in snapb["books"] if b["idx"] == w), None)
        if book is None:
            continue
        tr = sorted(tape(m["conditionId"], t_src - 5, fin + 5), key=lambda t: t["timestamp"])
        prints = [(t["timestamp"], float(t["price"]), float(t["size"])) for t in tr if t["side"] == "SELL" and t["outcomeIndex"] == w]
        bids = book["bids"]
        row = {"event": r["event"], "title": r.get("title"), "lead_s": round(fin - t_src, 1), "snap_age_s": round(t_src - snapb["t"], 1),
               "best_bid": bids[0][0] if bids else None, "best_bid_size": bids[0][1] if bids else None,
               "bid_depth_ge_0.99": round(sum(s for p, s in bids if p >= 0.99), 1), "bid_depth_ge_0.995": round(sum(s for p, s in bids if p >= 0.995), 1),
               "best_ask": book["best_ask"], "cells": {}}
        for d in (0, 15, 30, 60):
            tj = t_src + d
            for B in (0.99, 0.995, 0.998):
                q = sum(s for p, s in bids if abs(p - B) < 1e-9)
                need, got, filled, wait = q + 5.0, 0.0, 0, None
                for ts, p, s in prints:
                    if ts >= tj and 0.95 <= p <= B + 1e-9 and ts < fin:
                        got += s
                        if got >= need:
                            filled, wait = 1, ts - tj
                            break
                row["cells"][f"d{d}_B{B}"] = {"filled": filled, "wait_s": wait, "queue": q, "window_s": round(fin - tj, 1)}
        rows.append(row)
    summ = {"matches": len(rows), "cells": {}}
    for key in (f"d{d}_B{B}" for d in (0, 15, 30, 60) for B in (0.99, 0.995, 0.998)):
        use = [x for x in rows if x["cells"][key]["window_s"] > 0]
        f = sum(x["cells"][key]["filled"] for x in use)
        summ["cells"][key] = {"matches_with_window": len(use), "filled": f, "share": round(f / len(use), 3) if use else None,
                              "median_queue": sorted(x["cells"][key]["queue"] for x in use)[len(use) // 2] if use else None}
    leads = sorted(x["lead_s"] for x in rows)
    summ["lead_s"] = {"n": len(leads), "median": leads[len(leads) // 2] if leads else None, "p10": leads[len(leads) // 10] if leads else None,
                      "p90": leads[9 * len(leads) // 10] if leads else None}
    summ["best_bid_at_over"] = dict(collections.Counter(("none" if x["best_bid"] is None else ">=0.999" if x["best_bid"] >= 0.999 else "0.99-0.998" if x["best_bid"] >= 0.99 else "<0.99") for x in rows))
    summ["rows"] = rows
    (ROOT / "lab/results/2026-10-09-tennis-end-bids.json").write_text(json.dumps(summ, indent=1))
    print("matches analysed:", len(rows), "lead", summ["lead_s"], "best bid at the first 'over':", summ["best_bid_at_over"])
    for k, v in summ["cells"].items():
        print(f"  {k:14s} filled {v['filled']:3d} of {v['matches_with_window']:3d} = {v['share']}  median queue at B {v['median_queue']}")


if __name__ == "__main__":
    if sys.argv[1] == "record":
        record(float(sys.argv[2]) if len(sys.argv) > 2 else 6.0)
    else:
        analyze()
