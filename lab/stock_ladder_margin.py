"""Margin test for the stock-ladder far-strike buys (idea card 1, R-2026-10-08): not only "did it lose" but "how close
did the price come to the strike afterwards".

For every right-side BUY at 0.98-0.995 (>=5 shares, before the close) the script follows the real Yahoo 1-minute
bars from the fill to the end of the window and measures
  consumed = largest adverse move toward the strike / distance to the strike at the time of the fill
(consumed = 1.0 means the price reached the strike = a loss for the buyer; 0.2 means it used up a fifth of the room).
Also: per-week counts of fills and losers, and the biggest overnight gaps in the sample.

  python3 lab/stock_ladder_margin.py   -> lab/results/2026-10-08-stock-ladder-margin.json
"""
import collections, datetime, json, math, statistics, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stock_ladder_tape as T  # noqa: E402

OUT = T.ROOT / "lab/results/2026-10-08-stock-ladder-margin.json"


def week_of(day):
    d = datetime.datetime.strptime(day, "%Y-%m-%d")
    fri = d + datetime.timedelta(days=(4 - d.weekday()) % 7)
    return fri.strftime("%Y-%m-%d")


def consumed(bars, fam, st, ts, end_day):
    """largest adverse excursion toward the strike after ts (until the end of end_day's session) / distance at ts"""
    rng = bars.day_range(end_day)
    if rng is None:
        return None
    i = bars.idx_before(ts)
    if i < 0 or i >= rng[1] - 1:
        return None
    spot = bars.C[i]
    last = rng[1] - 1
    hi = max(bars.H[i + 1:last + 1]); lo = min(bars.L[i + 1:last + 1])
    kind = st[0]
    if kind == "above":
        K = st[1]
        if spot < K:     # NO side: danger is going up
            return math.log(max(hi, spot) / spot) / math.log(K / spot), math.log(K / spot)
        return math.log(spot / min(lo, spot)) / math.log(spot / K), math.log(spot / K)
    if kind == "up":     # touch above K, still untouched
        K = st[1]
        if spot >= K: return None
        return math.log(max(hi, spot) / spot) / math.log(K / spot), math.log(K / spot)
    if kind == "down":
        K = st[1]
        if spot <= K: return None
        return math.log(spot / min(lo, spot)) / math.log(spot / K), math.log(spot / K)
    if kind == "bracket":
        a, b = st[1], st[2]
        if a <= spot < b:
            return None
        edge = a if spot < a else b
        if spot < edge:
            return math.log(max(hi, spot) / spot) / math.log(edge / spot), math.log(edge / spot)
        return math.log(spot / min(lo, spot)) / math.log(spot / edge), math.log(spot / edge)
    return None


def main():
    rows, valid, mis = T.main()
    Y = {f.stem: T.Bars(json.loads(f.read_text()), f.stem) for f in (T.RAW / "yahoo").glob("*.json")}
    evs = {e["slug"]: e for e in json.loads((T.RAW / "events.json").read_text())}
    out = {"generated": datetime.datetime.utcnow().isoformat() + "Z"}
    # --- per week table
    def sel_fn(zt, last90):
        return [r for r in rows if r["right"] and r["z"] >= zt and 0.98 <= r["p"] <= 0.995 and r["sz"] >= 5 and not r["post"]
                and (0 <= r["min_to_end"] <= 90 if last90 else True)]
    weeks = sorted({week_of(r["end"]) for r in rows})
    tab = {}
    for w in weeks:
        e = {}
        for name, zt, l90 in (("last90_z>=6", 6, True), ("last90_z>=4", 4, True), ("allday_z>=6", 6, False), ("allday_z>=4", 4, False)):
            s = [r for r in sel_fn(zt, l90) if week_of(r["end"]) == w]
            e[name] = dict(fills=len(s), markets=len({(r["slug"], r["g"]) for r in s}), losers=sum(1 for r in s if not r["won"]))
        tab[w] = e
    out["per_week"] = tab
    # --- consumed fraction
    ev_by_slug_g = {}
    for slug, ev in evs.items():
        for m in ev["markets"]:
            ev_by_slug_g.setdefault((slug, m["g"]), m)
    res = {}
    for name, zt, l90 in (("last90_z>=4", 4, True), ("last90_z>=6", 6, True), ("allday_z>=4", 4, False), ("allday_z>=6", 6, False)):
        vals = []
        worst = []
        for r in sel_fn(zt, l90):
            ev = evs[r["slug"]]
            st = T.parse_strike(ev["family"], r["g"])
            if st is None or ev["family"] == "updown":
                continue
            c = consumed(Y[r["tk"]], ev["family"], st, r["ts"], r["end"])
            if c is None:
                continue
            vals.append(c[0])
            worst.append((c[0], r["tk"], r["slug"], r["g"], r["p"], round(r["z"], 1), round(r["min_to_end"]), round(c[1] * 100, 2)))
        vals.sort()
        if not vals:
            continue
        q = lambda p: round(vals[int(p * (len(vals) - 1))], 3)
        worst.sort(reverse=True)
        res[name] = dict(n=len(vals), median=q(.5), p90=q(.9), p99=q(.99), max=round(vals[-1], 3),
                         share_over_0_5=round(sum(1 for v in vals if v > 0.5) / len(vals), 4),
                         share_over_0_3=round(sum(1 for v in vals if v > 0.3) / len(vals), 4),
                         worst5=[(round(a, 3), tk, slug[:36], g, p, z, m, dist_pct) for a, tk, slug, g, p, z, m, dist_pct in worst[:5]])
    out["consumed_fraction"] = res
    # --- overnight gaps (close to next open) in the sample, per ticker: max abs %
    gaps = {}
    for tk, b in Y.items():
        days = list(b.days)
        g = []
        for k in range(1, len(days)):
            prev_close = b.C[b.days[days[k - 1]][1] - 1]
            op = b.O[b.days[days[k]][0]]
            g.append((abs(math.log(op / prev_close)) * 100, days[k]))
        g.sort(reverse=True)
        gaps[tk] = [round(g[0][0], 2), g[0][1], round(statistics.median([x[0] for x in g]), 2)]
    out["max_overnight_gap_pct__day__median_pct"] = gaps
    OUT.write_text(json.dumps(out, indent=1))
    print("wrote", OUT)
    return out


if __name__ == "__main__":
    o = main()
    print(json.dumps(o["per_week"], indent=0))
    print(json.dumps(o["consumed_fraction"], indent=0))
    print(json.dumps(o["max_overnight_gap_pct__day__median_pct"]))
