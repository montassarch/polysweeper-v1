"""Second cut of the stock-ladder tape (see stock_ladder_tape.py): supply, timing, wallets, tail risk, resolution delay.

  python3 lab/stock_ladder_supply.py      -> lab/results/2026-10-08-stock-ladder-supply.json
Questions: (1) at which prices do far-strike right-side buys happen (0.98-0.995 vs 0.999); (2) how many per day, which
sizes, what profit after the taker fee; (3) when in the last 90 minutes; (4) which wallets; (5) how often does a stock
really move 4/5/6 "normal moves" in the last 15/30/60/90 minutes (empirical tail, 20 tickers x 22 sessions);
(6) how long after the close do the markets settle (capital lock).
"""
import collections, datetime, json, math, statistics, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stock_ladder_tape as T  # noqa: E402

ROOT = T.ROOT
OUT = ROOT / "lab/results/2026-10-08-stock-ladder-supply.json"
FEE_RATE = 0.04


def fee(p, sh):
    return sh * FEE_RATE * p * (1 - p)


def pband(p):
    if p < 0.95: return "<0.95"
    if p < 0.98: return "0.95-0.98"
    if p < 0.99: return "0.98-0.99"
    if p < 0.995: return "0.99-0.995"
    if p < 0.999: return "0.995-0.998"
    return "0.999+"


def excursion_tail(Y):
    """for each ticker-session and start time t (every 5 min in the last 90): ratio of the largest later move to
    sigma*sqrt(minutes left); counts how often it exceeds k"""
    res = {m: collections.Counter() for m in (15, 30, 60, 90)}
    tot = {m: 0 for m in (15, 30, 60, 90)}
    mx = {m: (0, None) for m in (15, 30, 60, 90)}
    fin = {m: collections.Counter() for m in (15, 30, 60, 90)}
    for tk, bars in Y.items():
        for day, (a, b) in bars.days.items():
            if b - a < 380:
                continue
            last = b - 1
            for m in (15, 30, 60, 90):
                i = last - m
                sig = bars.sigma(i)
                if not sig:
                    continue
                s0 = bars.C[i]
                seg = bars.C[i + 1:last + 1]
                hi = max(max(bars.H[i + 1:last + 1]), s0); lo = min(min(bars.L[i + 1:last + 1]), s0)
                scale = sig * math.sqrt(m)
                r_ext = max(math.log(hi / s0), math.log(s0 / lo)) / scale     # largest excursion, either direction
                r_fin = abs(math.log(bars.C[last] / s0)) / scale               # final displacement
                tot[m] += 1
                for k in (2, 3, 4, 5, 6, 8):
                    if r_ext >= k: res[m][k] += 1
                    if r_fin >= k: fin[m][k] += 1
                if r_ext > mx[m][0]:
                    mx[m] = (round(r_ext, 2), f"{tk} {day} (move {100*max(math.log(hi/s0), math.log(s0/lo)):.2f}%, sigma-scale {100*scale:.3f}%)")
    return {m: dict(sessions=tot[m], reach_k={k: res[m][k] for k in (2, 3, 4, 5, 6, 8)},
                    finish_beyond_k={k: fin[m][k] for k in (2, 3, 4, 5, 6, 8)}, max_ratio=mx[m]) for m in res}


def main():
    rows, valid, mis = T.main()
    Y = {f.stem: T.Bars(json.loads(f.read_text()), f.stem) for f in (T.RAW / "yahoo").glob("*.json")}
    evs = json.loads((T.RAW / "events.json").read_text())
    out = {"generated": datetime.datetime.utcnow().isoformat() + "Z"}
    # 1. price bands of right-side far-strike buys in the last 90 min of the final day
    for zt in (4, 6):
        sel = [r for r in rows if r["right"] and r["z"] >= zt and 0 <= r["min_to_end"] <= 90]
        tab = collections.OrderedDict()
        for b in ("<0.95", "0.95-0.98", "0.98-0.99", "0.99-0.995", "0.995-0.998", "0.999+"):
            s = [r for r in sel if pband(r["p"]) == b]
            tab[b] = dict(n=len(s), n5=sum(1 for r in s if r["sz"] >= 5), shares=round(sum(r["sz"] for r in s)),
                          markets=len({(r["slug"], r["g"]) for r in s}), losers=sum(1 for r in s if not r["won"]))
        out[f"last90_right_z>={zt}_by_price"] = tab
    # 2. per day, cheap band, z>=6 (and z>=4), size >= 5, last 90 min
    def per_day(zt, lo=0.98, hi=0.995):
        sel = [r for r in rows if r["right"] and r["z"] >= zt and 0 <= r["min_to_end"] <= 90 and lo <= r["p"] <= hi and r["sz"] >= 5]
        by = collections.defaultdict(list)
        for r in sel:
            by[r["end"]].append(r)
        days = sorted(by)
        cnt = [len({(x["slug"], x["g"]) for x in by[d]}) for d in days]
        gross = sum((1 - r["p"]) * 5 for r in sel)
        fees = sum(fee(r["p"], 5) for r in sel)
        return dict(trades=len(sel), days_with_fill=len(days), markets_per_day_avg=round(statistics.mean(cnt), 1) if cnt else 0,
                    markets_per_day_median=statistics.median(cnt) if cnt else 0, min=min(cnt) if cnt else 0, max=max(cnt) if cnt else 0,
                    profit_5sh_gross_total=round(gross, 2), fees_5sh_total=round(fees, 3),
                    avg_profit_per_5sh_after_fee=round((gross - fees) / len(sel), 4) if sel else None,
                    all_sessions=len(next(iter(Y.values())).days))
    out["per_day_band_0.98-0.995_z>=6"] = per_day(6)
    out["per_day_band_0.98-0.995_z>=4"] = per_day(4)
    out["per_day_band_0.985-0.995_z>=6"] = per_day(6, 0.985, 0.995)
    # per family, z>=6, cheap band, size>=5
    fam = {}
    for f in sorted({r["fam"] for r in rows}):
        sel = [r for r in rows if r["fam"] == f and r["right"] and r["z"] >= 6 and 0 <= r["min_to_end"] <= 90 and 0.98 <= r["p"] <= 0.995 and r["sz"] >= 5]
        fam[f] = dict(trades=len(sel), markets=len({(r["slug"], r["g"]) for r in sel}), losers=sum(1 for r in sel if not r["won"]),
                      shares_med=statistics.median([r["sz"] for r in sel]) if sel else None)
    out["by_family_z>=6_0.98-0.995_5sh+"] = fam
    # 3. timing (minutes before the close) of cheap-band right-side z>=6 buys
    sel = [r for r in rows if r["right"] and r["z"] >= 6 and 0 <= r["min_to_end"] <= 90 and 0.98 <= r["p"] <= 0.995]
    hist = collections.Counter()
    for r in sel:
        m = r["min_to_end"]
        hist["0-5" if m < 5 else "5-15" if m < 15 else "15-30" if m < 30 else "30-60" if m < 60 else "60-90"] += 1
    out["timing_minutes_before_close_z>=6_cheap"] = dict(hist)
    # 4. wallets
    wc = collections.Counter(r["w"] for r in sel)
    out["wallets_z>=6_cheap_last90"] = dict(distinct=len(wc), top5_share=[(w[:10], n) for w, n in wc.most_common(5)], trades=len(sel))
    # wallets in the 0.999 band (sweepers)
    s999 = [r for r in rows if r["right"] and r["z"] >= 6 and 0 <= r["min_to_end"] <= 90 and r["p"] >= 0.999]
    w9 = collections.Counter(r["w"] for r in s999)
    out["wallets_z>=6_0.999_last90"] = dict(distinct=len(w9), trades=len(s999), top5=[(w[:10], n) for w, n in w9.most_common(5)])
    # 5. empirical tail
    out["tail_excursion"] = excursion_tail(Y)
    # 6. settlement delay after the close, by family (minutes), for markets whose closedTime exists
    delay = collections.defaultdict(list)
    for ev in evs:
        end_day = T.session_date(ev["endDate"])
        tend = datetime.datetime.strptime(end_day, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc).timestamp() + 20 * 3600
        for m in ev["markets"]:
            ct = T.created_ts(m.get("closedTime") or "")
            fi = T.final_idx(m["final"])
            if ct is None or fi is None:
                continue
            # NO-type (still open at the end): resolved after the close
            if ct >= tend - 60:
                delay[ev["family"]].append((ct - tend) / 60.0)
    dd = {}
    for f, v in delay.items():
        v.sort()
        q = lambda p: round(v[int(p * (len(v) - 1))], 1)
        dd[f] = dict(n=len(v), p10=q(.1), median=q(.5), p90=q(.9), p99=q(.99), max=round(v[-1], 1))
    out["settle_delay_min_after_close"] = dd
    OUT.write_text(json.dumps(out, indent=1))
    print("wrote", OUT)
    return out


if __name__ == "__main__":
    main()
