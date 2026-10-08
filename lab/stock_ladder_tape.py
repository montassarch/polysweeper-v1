"""Tape test for the "last-hour dead-strike sweep" on Polymarket stock/ETF ladders (idea card 1, R-2026-10-08).

For every public BUY trade on a stock/ETF ladder market (closed events, Sep 8 - Oct 7 2026) it asks, using ONLY
information known at the trade time (Yahoo 1-minute bars as a stand-in for Pyth, the settlement source):
  - which side the stock price implies (e.g. spot far below the strike => NO),
  - how many "normal moves" (z) the strike is away: |ln(spot/strike)| / (sigma_1min * sqrt(trading minutes left)),
    sigma_1min = max(last 60 minutes, last ~5 sessions) of the 1-minute log-return standard deviation,
  - whether the side that was bought is the implied side ("right side") or not ("trap"),
and then looks at how the market really settled. A "loser" is a right-side buy whose token paid 0.
Also checks Yahoo against the real settlements (close-above, bracket, touch, up/down markets) to see how far
Yahoo and Pyth can disagree.

  python3 lab/stock_ladder_pull.py 2026-09-08 2026-10-09     # tape (raw, git-ignored)
  python3 lab/stock_ladder_yahoo.py                          # Yahoo 1-minute bars
  python3 lab/stock_ladder_tape.py                           # writes lab/results/2026-10-08-stock-ladder-tape.json

Read-only. Nothing here places orders.
"""
import bisect, collections, datetime, itertools, json, math, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "lab/data/raw/stockladder"
OUT = ROOT / "lab/results/2026-10-08-stock-ladder-tape.json"
CLOSE_H = 20  # 16:00 ET = 20:00 UTC while US daylight time lasts (until 1 Nov 2026)


def utc(ts):
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).replace(tzinfo=None)


class Bars:
    """1-minute regular-session bars of one ticker, with prefix sums for rolling volatility."""

    def __init__(self, d, sym=None):
        self.sym = sym
        self.T, self.O, self.H, self.L, self.C = [], [], [], [], []
        self.official = {}
        rows = [r for r in zip(d["t"], d["o"], d["h"], d["l"], d["c"], d["v"]) if r[4] is not None]
        last_of_day = {}
        for k, r in enumerate(rows):
            last_of_day[utc(r[0]).strftime("%Y-%m-%d")] = k
        for k, (t, o, h, l, c, v) in enumerate(rows):
            day = utc(t).strftime("%Y-%m-%d")
            # Yahoo adds a synthetic last bar (volume 0, open=high=low=close) at the closing time = official close
            if k == last_of_day[day] and not v and o == h == l == c and t % 60 == 0 and len(rows) > 1 and k > 0 and t - rows[k - 1][0] <= 120 and (t % 3600 == 0):
                self.official[day] = c
                continue
            self.T.append(t); self.O.append(o); self.H.append(h); self.L.append(l); self.C.append(c)
        self.n = len(self.T)
        self.days = collections.OrderedDict()
        for i, t in enumerate(self.T):
            day = utc(t).strftime("%Y-%m-%d")
            a = self.days.setdefault(day, [i, i + 1])
            a[1] = i + 1
        r1, r2, w = [0.0], [0.0], [0]
        s1 = s2 = 0.0; cnt = 0
        for i in range(self.n):
            ok = i > 0 and self.T[i] - self.T[i - 1] <= 300 and self.T[i] // 86400 == self.T[i - 1] // 86400
            if ok:
                r = math.log(self.C[i] / self.C[i - 1])
                s1 += r; s2 += r * r; cnt += 1
            r1.append(s1); r2.append(s2); w.append(cnt)
        self.S1, self.S2, self.W = r1, r2, w
        self._ext = {}

    def idx_before(self, ts):
        """index of the last COMPLETED bar at time ts (bar start <= ts-60)"""
        return bisect.bisect_right(self.T, ts - 60) - 1

    def sigma(self, i):
        def win(k):
            a = max(0, i - k + 1)
            n = self.W[i + 1] - self.W[a + 1] if a + 1 <= i + 1 else 0
            if n < 15:
                return None
            return math.sqrt((self.S2[i + 1] - self.S2[a + 1]) / n)
        s60, s5d = win(60), win(1950)
        cands = [x for x in (s60, s5d) if x]
        return max(cands) if cands else None

    def runext(self, i0):
        """running max of High and min of Low from bar i0 on (cached)"""
        if i0 not in self._ext:
            self._ext[i0] = (list(itertools.accumulate(self.H[i0:], max)), list(itertools.accumulate(self.L[i0:], min)))
        return self._ext[i0]

    def day_range(self, day):
        return self.days.get(day)

    def prev_day_close(self, day):
        keys = list(self.days)
        if day not in self.days:
            return None
        k = keys.index(day)
        if k == 0:
            return None
        i1 = self.days[keys[k - 1]][1] - 1
        return self.C[i1]


_DAILY = {}


def gap_sigma(tk, day):
    """RMS of overnight log gaps (open vs previous close) over the 60 sessions before `day` (Yahoo daily bars)"""
    if tk not in _DAILY:
        f = RAW / "yahoo_daily" / f"{tk}.json"
        if f.exists():
            d = json.loads(f.read_text())
            days = [utc(t).strftime("%Y-%m-%d") for t in d["t"]]
            gaps = [math.log(d["o"][i] / d["c"][i - 1]) for i in range(1, len(days))]
            _DAILY[tk] = (days[1:], gaps)
        else:
            _DAILY[tk] = ([], [])
    days, gaps = _DAILY[tk]
    k = bisect.bisect_left(days, day)
    g = gaps[max(0, k - 60):k]
    if len(g) < 10:
        return 0.004          # fallback 0.4% when too little history
    return math.sqrt(sum(x * x for x in g) / len(g))


def num(s):
    return float(s.replace(",", ""))


def parse_strike(fam, g):
    """-> ('above', K) | ('bracket', lo, hi) | ('up', K) | ('down', K) | ('updown',)"""
    if fam in ("dailyclose_above", "weekly_above", "monthly_above"):
        m = re.search(r"\$([\d,\.]+)", g or "")
        return ("above", num(m.group(1))) if m else None
    if fam == "weekly_bracket":
        g = g or ""
        m = re.match(r"^<\$([\d,\.]+)$", g)
        if m: return ("bracket", -math.inf, num(m.group(1)))
        m = re.match(r"^>\$([\d,\.]+)$", g)
        if m: return ("bracket", num(m.group(1)), math.inf)
        m = re.match(r"^\$([\d,\.]+)-\$([\d,\.]+)$", g)
        if m: return ("bracket", num(m.group(1)), num(m.group(2)))
        return None
    if fam in ("weekly_hit", "monthly_hit"):
        m = re.match(r"^([↑↓])\s*\$([\d,\.]+)", g or "")
        if m: return ("up" if m.group(1) == "↑" else "down", num(m.group(2)))
        return None
    if fam == "updown":
        return ("updown",)
    return None


def final_idx(final):
    try:
        f = [float(x) for x in final]
    except Exception:
        return None
    if len(f) == 2 and sorted(f) == [0.0, 1.0]:
        return f.index(1.0)
    return None


def session_date(end_iso):
    d = datetime.datetime.strptime(end_iso[:19], "%Y-%m-%dT%H:%M:%S") - datetime.timedelta(hours=5)
    return d.strftime("%Y-%m-%d")


def window_start_day(fam, end_day):
    d = datetime.datetime.strptime(end_day, "%Y-%m-%d")
    if fam == "weekly_hit":
        return (d - datetime.timedelta(days=4)).strftime("%Y-%m-%d")
    if fam == "monthly_hit":
        return d.strftime("%Y-%m-01")
    return end_day


def created_ts(s):
    try:
        s = s.replace("Z", "").split(".")[0].replace(" ", "T")
        return datetime.datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=datetime.timezone.utc).timestamp()
    except Exception:
        return None


def window_start_idx(bars, wstart_day, created):
    """first bar of the touch window: week/month start, but not before the market existed"""
    i0 = next((a for day, (a, b) in bars.days.items() if day >= wstart_day), None)
    if i0 is None:
        return None
    if created:
        j = bisect.bisect_left(bars.T, created)   # first bar starting at/after creation
        i0 = max(i0, j)
    return i0


def classify(bars, fam, st, ts, end_day, wstart_day, created=None, why=None):
    """-> dict(implied_idx, z, mleft, spot, dist_pct, post) or None. Uses only data up to ts."""
    tend = datetime.datetime.strptime(end_day, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc).timestamp() + CLOSE_H * 3600
    rng_end = bars.day_range(end_day)
    if rng_end is None:
        if why is not None: why["no_end_day_bars"] += 1
        return None
    idx_end = rng_end[1] - 1
    post = ts >= tend
    i = bars.idx_before(min(ts, tend))
    if i < 0:
        if why is not None: why["before_data"] += 1
        return None
    if post:
        i = idx_end
        mleft = 1
    else:
        mleft = max(idx_end - i, 0) + 1
    sig = bars.sigma(i)
    if not sig:
        if why is not None: why["no_sigma"] += 1
        return None
    spot = bars.C[i]
    scale = sig * math.sqrt(mleft)
    # total horizon volatility: intraday 1-minute moves plus one overnight gap for every session open still to come
    nights = sum(1 for dk, (a0, b0) in bars.days.items() if dk <= end_day and bars.T[a0] > ts)
    gs = gap_sigma(bars.sym, end_day) if nights else 0.0
    scale_total = math.sqrt(scale * scale + nights * gs * gs)
    kind = st[0]
    if kind == "above":
        K = st[1]
        d = math.log(spot / K)
        return dict(implied=0 if d > 0 else 1, z=abs(d) / scale, zt=abs(d) / scale_total, mleft=mleft, spot=spot, dist=abs(d) * 100, post=post, nights=nights)
    if kind == "updown":
        K = bars.prev_day_close(end_day)
        if K is None:
            return None
        d = math.log(spot / K)
        return dict(implied=0 if d > 0 else 1, z=abs(d) / scale, zt=abs(d) / scale_total, mleft=mleft, spot=spot, dist=abs(d) * 100, post=post, nights=nights)
    if kind == "bracket":
        lo, hi = st[1], st[2]
        inside = lo <= spot < hi
        edges = [e for e in (lo, hi) if math.isfinite(e)]
        d = min(abs(math.log(spot / e)) for e in edges)
        return dict(implied=0 if inside else 1, z=d / scale, zt=d / scale_total, mleft=mleft, spot=spot, dist=d * 100, post=post, nights=nights)
    if kind in ("up", "down"):
        K = st[1]
        i0 = window_start_idx(bars, wstart_day, created)
        if i0 is None or i < i0:
            if why is not None: why["hit_before_window"] += 1
            return None
        mx, mn = bars.runext(i0)
        k = i - i0
        if kind == "up":
            touched = mx[k] >= K
            d = math.log(K / spot)
        else:
            touched = mn[k] <= K
            d = math.log(spot / K)
        if touched:
            return dict(implied=0, z=abs(d) / scale, zt=abs(d) / scale_total, mleft=mleft, spot=spot, dist=abs(d) * 100, post=post, touched=True, nights=nights)
        return dict(implied=1, z=d / scale, zt=d / scale_total, mleft=mleft, spot=spot, dist=d * 100, post=post, nights=nights)
    return None


ZB = [(0, 1, "z<1"), (1, 2, "1-2"), (2, 3, "2-3"), (3, 4, "3-4"), (4, 6, "4-6"), (6, 10, "6-10"), (10, 1e9, "10+")]


def zbucket(z):
    for a, b, name in ZB:
        if a <= z < b:
            return name
    return "10+"


def main():
    evs = json.loads((RAW / "events.json").read_text())
    Y = {f.stem: Bars(json.loads(f.read_text()), f.stem) for f in (RAW / "yahoo").glob("*.json")}
    rows = []          # every classified BUY trade
    skipped = collections.Counter()
    valid = collections.defaultdict(lambda: collections.Counter())   # Yahoo vs settlement checks
    valid_mis = []
    for ev in evs:
        bars = Y.get(ev["ticker"])
        fam = ev["family"]
        if bars is None:
            skipped["no_yahoo"] += 1
            continue
        end_day = session_date(ev["endDate"])
        wstart = window_start_day(fam, end_day)
        rng = bars.day_range(end_day)
        if rng is None:
            skipped["no_bars_for_day"] += 1
            continue
        mk = {m["cid"]: m for m in ev["markets"]}
        # ---- Yahoo vs settlement
        i_last = rng[1] - 1
        c_last = bars.C[i_last]
        for m in ev["markets"]:
            st = parse_strike(fam, m["g"])
            fi = final_idx(m["final"])
            if st is None or fi is None:
                continue
            pred = None; dist = None
            if st[0] == "above":
                pred = 0 if c_last > st[1] else 1; dist = abs(math.log(c_last / st[1])) * 100
            elif st[0] == "bracket":
                lo, hi = st[1], st[2]
                pred = 0 if lo <= c_last < hi else 1
                dist = min(abs(math.log(c_last / e)) for e in (lo, hi) if math.isfinite(e)) * 100
            elif st[0] == "updown":
                pc = bars.prev_day_close(end_day)
                if pc is None: continue
                pred = 0 if c_last > pc else 1; dist = abs(math.log(c_last / pc)) * 100
            elif st[0] in ("up", "down") and fam == "weekly_hit":
                i0 = window_start_idx(bars, wstart, created_ts(m.get("created") or ""))
                if i0 is None or i0 > i_last: continue
                if st[0] == "up":
                    ex = max(bars.H[i0:i_last + 1]); touched = ex >= st[1]; dist = abs(math.log(ex / st[1])) * 100
                else:
                    ex = min(bars.L[i0:i_last + 1]); touched = ex <= st[1]; dist = abs(math.log(ex / st[1])) * 100
                pred = 0 if touched else 1
            if pred is None:
                continue
            ok = pred == fi
            b = "<0.05%" if dist < 0.05 else "0.05-0.2%" if dist < 0.2 else "0.2-0.5%" if dist < 0.5 else "0.5-1%" if dist < 1 else "1%+"
            valid[fam][(b, ok)] += 1
            if not ok:
                valid_mis.append(dict(slug=ev["slug"], g=m["g"], fam=fam, dist_pct=round(dist, 3), pred=pred, actual=fi,
                                      yahoo_close=c_last, official=bars.official.get(end_day)))
        # ---- trades
        try:
            trades = json.loads((RAW / "trades" / f"{ev['id']}.json").read_text())
        except Exception:
            skipped["no_trades_file"] += 1
            continue
        tend = datetime.datetime.strptime(end_day, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc).timestamp() + CLOSE_H * 3600
        for t in trades:
            if t["side"] != "BUY":
                continue
            m = mk.get(t["cid"])
            if m is None:
                skipped["trade_unknown_market"] += 1
                continue
            st = parse_strike(fam, m["g"])
            fi = final_idx(m["final"])
            if st is None or fi is None:
                skipped["no_strike_or_final"] += 1
                continue
            c = classify(bars, fam, st, t["ts"], end_day, wstart, created_ts(m.get("created") or ""), skipped)
            if c is None:
                skipped["no_class"] += 1
                continue
            oi = t["oi"]
            rows.append(dict(fam=fam, tk=ev["ticker"], slug=ev["slug"], g=m["g"], end=end_day, ts=t["ts"], p=t["price"],
                             sz=t["size"], w=t["w"], oi=oi, right=(oi == c["implied"]), won=(oi == fi),
                             z=c["z"], zt=c.get("zt", c["z"]), nights=c.get("nights", 0), mleft=c["mleft"], dist=c["dist"], post=c["post"],
                             min_to_end=(tend - t["ts"]) / 60.0, touched=c.get("touched", False)))
    print("classified BUY trades", len(rows), "skipped", dict(skipped))
    return rows, valid, valid_mis


def stats(sel):
    n = len(sel)
    loss = [r for r in sel if not r["won"]]
    return dict(n=n, markets=len({(r["slug"], r["g"]) for r in sel}), shares=round(sum(r["sz"] for r in sel), 1),
                n5=sum(1 for r in sel if r["sz"] >= 5), losers=len(loss),
                avg_p=round(sum(r["p"] for r in sel) / n, 4) if n else None)


def wilson_upper(k, n, z=1.96):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    a = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return round((c + a) / d, 4)


if __name__ == "__main__":
    rows, valid, valid_mis = main()
    res = {"generated": datetime.datetime.utcnow().isoformat() + "Z", "n_rows": len(rows)}
    # validation
    res["yahoo_vs_settlement"] = {fam: {f"{b}|{'ok' if ok else 'MISMATCH'}": n for (b, ok), n in sorted(c.items())} for fam, c in valid.items()}
    res["mismatches"] = valid_mis[:60]
    band = lambda r: 0.98 <= r["p"] <= 0.995
    last90 = lambda r: 0 <= r["min_to_end"] <= 90
    out = {}
    for label, sel in [
        ("last90_final_day", [r for r in rows if band(r) and last90(r)]),
        ("all_times", [r for r in rows if band(r) and not r["post"]]),
        ("post_close_to_resolution", [r for r in rows if band(r) and r["post"] and r["min_to_end"] > -60]),
    ]:
        tab = {}
        for fam in sorted({r["fam"] for r in sel}) + ["ALL"]:
            s2 = [r for r in sel if fam == "ALL" or r["fam"] == fam]
            right = [r for r in s2 if r["right"]]
            wrong = [r for r in s2 if not r["right"]]
            ent = {"right": stats(right), "wrong_side": stats(wrong)}
            ent["right_by_z"] = {name: stats([r for r in right if zbucket(r["z"]) == name]) for _, _, name in ZB}
            for zt in (2, 3, 4, 6):
                s3 = [r for r in right if r["z"] >= zt]
                ent[f"right_z>={zt}"] = dict(stats(s3), upper95_loss_rate=wilson_upper(len(s3) and sum(1 for r in s3 if not r['won']), len(s3)))
            tab[fam] = ent
        out[label] = tab
    res["tape"] = out
    # losers detail (right side, any z) in the cheap band, last 90 min and all times
    res["right_side_losers"] = [dict(slug=r["slug"], g=r["g"], tk=r["tk"], p=r["p"], sz=r["sz"], z=round(r["z"], 2), dist_pct=round(r["dist"], 3),
                                     min_to_end=round(r["min_to_end"], 1), end=r["end"], w=r["w"][:10], oi=r["oi"])
                                for r in rows if band(r) and not r["post"] and r["right"] and not r["won"]][:80]
    OUT.write_text(json.dumps(res, indent=1))
    print("wrote", OUT)
