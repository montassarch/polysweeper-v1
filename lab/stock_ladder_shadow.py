"""Pretend-trading recorder for the far-strike rule on Polymarket stock/ETF ladders
(idea card 1 of R-2026-10-08; proposed scoreboard row 9). READ-ONLY: no orders, no keys, no wallet.

Rule (pretend): buy 5 shares of the side that the stock price already makes certain, on a far strike of a ladder
(daily "close above", weekly "finish week above", weekly closing brackets, weekly "hit" touch ladders), when
  - the strike is at least Z_MIN "normal moves" away: |ln(spot/strike)| / (sigma_1min * sqrt(trading minutes left)),
    sigma_1min = max(last 60 minutes, last ~5 sessions) of 1-minute log-return std (Yahoo bars; Pyth is the settlement source),
  - and at least DIST_MIN percent away in plain price terms,
  - and the book shows >= 5 shares of that side at a price of 0.98 - 0.995 (average price of the 5 shares).
To be fair to slow code, a pretend fill only counts if the same ask is STILL there at the next snapshot
(>= PERSIST_S seconds later); the fill price is the worse of the two looks. Candidates that vanish are counted too
(that is the competition measurement). Each token is filled at most once per day.
Settlement: when Gamma says the market is closed with a clear 1/0 result the fill becomes a win or a loss.

  python3 lab/stock_ladder_shadow.py                  # run all day (leave it open; sleeps outside market hours)
  python3 lab/stock_ladder_shadow.py --cycles 3 --interval 15 --anyhours   # quick test, also outside market hours
Outputs: lab/data/raw/stock-shadow/<date>.jsonl (raw, git-ignored) and lab/results/stock-ladder-shadow-summary.json
(small; commit it). Standard library only. Set POLYSWEEPER_NO_ALERTS=1 not needed (no alerts here).
"""
import argparse, collections, datetime, json, math, sys, time, urllib.error, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "lab"))
from polysweeper.collector import get_json, post_json, GAMMA, CLOB  # noqa: E402
import stock_ladder_pull as P  # noqa: E402
import stock_ladder_tape as T  # noqa: E402
import stock_ladder_yahoo as Yh  # noqa: E402

RAW = ROOT / "lab/data/raw/stock-shadow"
SUMMARY = ROOT / "lab/results/stock-ladder-shadow-summary.json"
RAW.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept": "application/json,text/plain,*/*"}
FAMILIES = {"dailyclose_above", "weekly_above", "weekly_bracket", "weekly_hit", "monthly_above", "monthly_hit"}   # open events only (touched hit strikes close within minutes)
HOLIDAYS = {"2026-11-26", "2026-12-25", "2027-01-01", "2027-01-18", "2027-02-15"}   # NYSE closed days after today
SHARES = 5
BAND_LO, BAND_HI = 0.98, 0.995
STALE_OK = False          # testing only: accept bars older than 6 minutes (outside market hours)


# ---------- time helpers (US Eastern, no tz database needed) ----------
def us_dst(d):
    """True if US daylight saving time is in force on date d (second Sunday of March .. first Sunday of November)"""
    def nth_sunday(y, m, n):
        first = datetime.date(y, m, 1)
        return first + datetime.timedelta(days=(6 - first.weekday()) % 7 + 7 * (n - 1))
    return nth_sunday(d.year, 3, 2) <= d < nth_sunday(d.year, 11, 1)


def session_utc(d):
    """(open_ts, close_ts) in unix seconds for trading date d (regular hours 9:30-16:00 ET; no early-close table)"""
    off = 4 if us_dst(d) else 5
    base = datetime.datetime(d.year, d.month, d.day, tzinfo=datetime.timezone.utc).timestamp()
    return base + (9.5 + off) * 3600, base + (16 + off) * 3600


def is_trading_day(d):
    return d.weekday() < 5 and d.strftime("%Y-%m-%d") not in HOLIDAYS


def trading_minutes_left(now, end_day):
    """trading minutes from now until the close of end_day (390 per full day)"""
    d = datetime.datetime.fromtimestamp(now, datetime.timezone.utc).date()
    end = datetime.datetime.strptime(end_day, "%Y-%m-%d").date()
    total = 0.0
    while d <= end:
        if is_trading_day(d):
            o, c = session_utc(d)
            total += max(0.0, c - max(now, o)) / 60.0
        d += datetime.timedelta(days=1)
    return total


def sessions_ahead(now, end_day):
    """number of session OPENS still to come before the close of end_day (= overnight gaps still to be crossed)"""
    d = datetime.datetime.fromtimestamp(now, datetime.timezone.utc).date()
    end = datetime.datetime.strptime(end_day, "%Y-%m-%d").date()
    n = 0
    while d <= end:
        if is_trading_day(d) and session_utc(d)[0] > now:
            n += 1
        d += datetime.timedelta(days=1)
    return n


# ---------- data ----------
def yahoo_bars(sym, rng="5d"):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1m&range={rng}&includePrePost=false"
    delay = 2.0
    for _ in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                d = json.load(r)
            res = d["chart"]["result"][0]
            q = res["indicators"]["quote"][0]
            ts = res.get("timestamp") or []
            return T.Bars({"t": ts, "o": q["open"], "h": q["high"], "l": q["low"], "c": q["close"],
                           "v": [v or 0 for v in q["volume"]]}, sym) if ts else None
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503):
                time.sleep(delay); delay *= 2; continue
            return None
        except Exception:
            time.sleep(delay); delay *= 2
    return None


def load_universe(now):
    d0 = datetime.datetime.fromtimestamp(now, datetime.timezone.utc).strftime("%Y-%m-%d")
    d1 = (datetime.datetime.fromtimestamp(now, datetime.timezone.utc) + datetime.timedelta(days=8)).strftime("%Y-%m-%d")
    evs = [P.slim_event(e) for e in P.list_events(d0, d1, closed="false")]
    out = []
    for e in evs:
        if e["family"] not in FAMILIES:
            continue
        e["end_day"] = T.session_date(e["endDate"])
        e["wstart"] = T.window_start_day(e["family"], e["end_day"])
        out.append(e)
    return out


def live_class(bars, fam, st, now, end_day, wstart, created):
    """-> (implied_idx, z, zt, dist_pct, spot, mleft) using only completed 1-minute bars; None if unknown.
    z = intraday-only normal moves; zt = same but adding one overnight gap per session open still ahead"""
    i = bars.idx_before(now)
    if i < 60:
        return None
    if now - bars.T[i] > 300 + 60 and not STALE_OK:   # stale data (more than ~5 minutes old) -> do not trade
        return None
    sig = bars.sigma(i)
    if not sig:
        return None
    mleft = max(1.0, trading_minutes_left(now, end_day))
    scale = sig * math.sqrt(mleft)
    nights = sessions_ahead(now, end_day)
    gs = T.gap_sigma(bars.sym, datetime.datetime.fromtimestamp(now, datetime.timezone.utc).strftime("%Y-%m-%d")) if nights else 0.0
    scale_t = math.sqrt(scale * scale + nights * gs * gs)      # intraday moves + one overnight gap per session open ahead
    spot = bars.C[i]
    kind = st[0]
    if kind == "above":
        d = math.log(spot / st[1])
        return (0 if d > 0 else 1), abs(d) / scale, abs(d) / scale_t, abs(d) * 100, spot, mleft
    if kind == "bracket":
        lo, hi = st[1], st[2]
        inside = lo <= spot < hi
        d = min(abs(math.log(spot / e)) for e in (lo, hi) if math.isfinite(e))
        return (0 if inside else 1), d / scale, d / scale_t, d * 100, spot, mleft
    if kind in ("up", "down"):
        i0 = T.window_start_idx(bars, wstart, T.created_ts(created or ""))
        if i0 is None or i0 > i:
            i0 = i
        mx, mn = bars.runext(i0)
        k = i - i0
        K = st[1]
        if kind == "up":
            touched = mx[k] >= K; d = math.log(K / spot)
        else:
            touched = mn[k] <= K; d = math.log(spot / K)
        if touched:
            return None                       # already touched: the market resolves YES within minutes; not our rule
        return 1, d / scale, d / scale_t, d * 100, spot, mleft
    return None


def vwap_for(asks, shares):
    """average price of buying `shares` from the ask list (sorted ascending), or None if the book is too thin"""
    need, cost = shares, 0.0
    for p, s in asks:
        take = min(need, s)
        cost += take * p; need -= take
        if need <= 1e-9:
            return cost / shares
    return None


def fetch_books(tokens):
    books = {}
    for k in range(0, len(tokens), 100):
        r = post_json(f"{CLOB}/books", [{"token_id": t} for t in tokens[k:k + 100]])
        for b in (r or []):
            books[b["asset_id"]] = b
    return books


def asks_of(b):
    return sorted((float(a["price"]), float(a["size"])) for a in (b or {}).get("asks", []))


# ---------- settlement ----------
def settle(fills):
    changed = 0
    for f in fills:
        if f.get("result") in ("win", "loss"):
            continue
        m = get_json(f"{GAMMA}/markets?condition_ids={f['cid']}&closed=true&limit=1")   # closed=true is needed for settled markets
        if not m:
            continue
        m = m[0]
        try:
            pr = [float(x) for x in json.loads(m.get("outcomePrices") or "[]")]
        except Exception:
            continue
        if m.get("closed") and len(pr) == 2 and sorted(pr) == [0.0, 1.0]:
            won = pr[f["oi"]] == 1.0
            f["result"] = "win" if won else "loss"
            f["settled_at"] = int(time.time())
            changed += 1
        elif m.get("closed") and len(pr) == 2:
            f["result"] = "void"
            changed += 1
    return changed


def fee(p, sh, rate=0.04):
    return sh * rate * p * (1 - p)


def write_summary(state, started):
    fills = state["fills"]
    done = [f for f in fills if f.get("result") in ("win", "loss")]
    wins = [f for f in done if f["result"] == "win"]
    losses = [f for f in done if f["result"] == "loss"]
    pnl = sum(((1 - f["price"]) * SHARES - fee(f["price"], SHARES)) for f in wins) - sum(f["price"] * SHARES + fee(f["price"], SHARES) for f in losses)
    tiers = {"zt>=4": lambda f: True, "zt>=6 and dist>=2%": lambda f: f["z"] >= 6 and f["dist"] >= 2,
             "zt>=8 and dist>=3%": lambda f: f["z"] >= 8 and f["dist"] >= 3}
    tier_tab = {}
    for name, fn in tiers.items():
        s = [f for f in fills if fn(f)]
        d = [f for f in s if f.get("result") in ("win", "loss")]
        tier_tab[name] = dict(fills=len(s), settled=len(d), losses=sum(1 for f in d if f["result"] == "loss"))
    cands = state["cand_count"]
    out = dict(updated=datetime.datetime.utcnow().isoformat() + "Z", started=started, cycles=state["cycles"],
               candidates_seen=cands, candidates_vanished=state["vanished"],
               persisted_share=round(len(fills) / max(1, len(fills) + state["vanished"]), 3),
               pretend_fills=len(fills), settled=len(done), wins=len(wins), losses=len(losses),
               pending=len(fills) - len(done), pnl_usd_5sh=round(pnl, 3), tiers=tier_tab,
               by_family=dict(collections.Counter(f["fam"] for f in fills)),
               by_day=dict(sorted(collections.Counter(f["day"] for f in fills).items())),
               supply_by_hour_utc={h: {k: round(v / max(1, c["n"]), 2) for k, v in c.items() if k != "n"} for h, c in sorted(state["supply"].items())},
               vanish_life_s_median=(sorted(state["life"])[len(state["life"]) // 2] if state["life"] else None),
               last_fills=[{k: f[k] for k in ("day", "t", "tk", "fam", "g", "side", "price", "z", "dist", "mleft", "result") if k in f} for f in fills[-15:]],
               losses_detail=[{k: f[k] for k in ("day", "tk", "fam", "g", "side", "price", "z", "dist", "mleft", "spot") if k in f} for f in losses])
    SUMMARY.write_text(json.dumps(out, indent=1))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=float, default=20.0)
    ap.add_argument("--cycles", type=int, default=0, help="stop after N cycles (0 = run until killed)")
    ap.add_argument("--anyhours", action="store_true", help="also run outside market hours (testing)")
    ap.add_argument("--zmin", type=float, default=4.0, help="log fills from this zt (summary shows the zt>=6 tiers separately)")
    ap.add_argument("--persist", type=float, default=15.0, help="seconds an ask must survive to count as a fill")
    a = ap.parse_args()
    global STALE_OK
    STALE_OK = a.anyhours
    started = datetime.datetime.utcnow().isoformat() + "Z"
    state = {"fills": [], "cycles": 0, "cand_count": 0, "vanished": 0, "life": [], "supply": collections.defaultdict(lambda: collections.Counter())}
    if SUMMARY.exists():
        try:
            old = json.loads(SUMMARY.read_text())
            fp = RAW / "fills.json"
            if fp.exists():
                state["fills"] = json.loads(fp.read_text())
                state["cand_count"] = old.get("candidates_seen", 0); state["vanished"] = old.get("candidates_vanished", 0)
        except Exception:
            pass
    universe, uni_ts = [], 0.0
    bars, bars_ts = {}, {}
    cand = {}                      # token -> dict(first_ts, first_vwap)
    filled_today = set((f["day"], f["tok"]) for f in state["fills"])
    last_settle = 0.0
    n = 0
    while True:
        now = time.time()
        today = datetime.datetime.fromtimestamp(now, datetime.timezone.utc).date()
        o, c = session_utc(today)
        in_hours = is_trading_day(today) and (o - 600) <= now <= (c + 2100)
        if not in_hours and not a.anyhours:
            if now - last_settle > 600 and state["fills"]:
                if settle(state["fills"]):
                    (RAW / "fills.json").write_text(json.dumps(state["fills"]))
                write_summary(state, started); last_settle = now
            time.sleep(60)
            continue
        try:
            if now - uni_ts > 1800 or not universe:
                universe, uni_ts = load_universe(now), now
            tickers = sorted({e["ticker"] for e in universe})
            for tk in tickers:                    # daily bars (overnight-gap volatility), refreshed about once a day
                fd = RAW.parent / "stockladder" / "yahoo_daily" / f"{tk}.json"
                if not fd.exists() or now - fd.stat().st_mtime > 20 * 3600:
                    if Yh.pull_daily(tk, "1y"):
                        T._DAILY.pop(tk, None)
                    time.sleep(0.4)
            for tk in tickers:
                if now - bars_ts.get(tk, 0) > 55:
                    b = yahoo_bars(tk)
                    if b is not None:
                        bars[tk], bars_ts[tk] = b, now
                    time.sleep(0.3)
            # 1. classify every market (cheap, no network): right-side token + z
            pend = []
            for e in universe:
                b = bars.get(e["ticker"])
                if b is None:
                    continue
                for m in e["markets"]:
                    st = T.parse_strike(e["family"], m["g"])
                    if st is None or len(m["tokens"]) != 2:
                        continue
                    r = live_class(b, e["family"], st, now, e["end_day"], e["wstart"], m.get("created"))
                    if r is None:
                        continue
                    impl, z0, z, dist, spot, mleft = r      # z = total-horizon normal moves (with overnight gaps)
                    if z >= a.zmin - 1:                  # poll a bit below the logging threshold
                        pend.append((e, m, impl, z, dist, spot, mleft, z0))
            books = fetch_books([p[1]["tokens"][p[2]] for p in pend])
            # 2. supply snapshot + candidate logic
            hour = datetime.datetime.fromtimestamp(now, datetime.timezone.utc).strftime("%H")
            sup = state["supply"][hour]
            sup["n"] += 1
            seen_now = set()
            for e, m, impl, z, dist, spot, mleft, z0 in pend:
                tok = m["tokens"][impl]
                asks = asks_of(books.get(tok))
                if z >= 6 and dist >= 2:
                    sup["tokens_z6"] += 1
                    if not asks: sup["no_ask"] += 1
                    elif asks[0][0] < BAND_LO: sup["below_band"] += 1
                    elif asks[0][0] <= BAND_HI: sup["in_band"] += 1
                    elif asks[0][0] < 0.999: sup["0.996-0.998"] += 1
                    else: sup["0.999+"] += 1
                if z < a.zmin:
                    continue
                v = vwap_for(asks, SHARES)
                day = today.strftime("%Y-%m-%d")
                if v is None or not (BAND_LO <= v <= BAND_HI) or (day, tok) in filled_today:
                    continue
                seen_now.add(tok)
                if tok not in cand:
                    cand[tok] = {"first": now, "vwap": v}
                    state["cand_count"] += 1
                elif now - cand[tok]["first"] >= a.persist:
                    px = max(v, cand[tok]["vwap"])
                    f = dict(day=day, t=int(now), tok=tok, cid=m["cid"], oi=impl, tk=e["ticker"], fam=e["family"], g=m["g"],
                             side=["Yes", "No"][impl] if e["family"] != "updown" else ["Up", "Down"][impl], price=round(px, 4),
                             z=round(z, 2), z_intraday=round(z0, 2), dist=round(dist, 2), mleft=round(mleft), spot=round(spot, 4), life=round(now - cand[tok]["first"]))
                    state["fills"].append(f)
                    filled_today.add((day, tok))
                    cand.pop(tok, None)
                    with open(RAW / f"{day}.jsonl", "a") as fh:
                        fh.write(json.dumps({"ev": "fill", **f}) + "\n")
            for tok in list(cand):
                if tok not in seen_now:
                    state["vanished"] += 1
                    state["life"].append(round(now - cand[tok]["first"]))
                    cand.pop(tok)
            n += 1
            state["cycles"] += 1
            if n % 6 == 0 or a.cycles:
                (RAW / "fills.json").write_text(json.dumps(state["fills"]))
                write_summary(state, started)
            if now - last_settle > 600 and now > c:
                if settle(state["fills"]):
                    (RAW / "fills.json").write_text(json.dumps(state["fills"]))
                last_settle = now
            print(time.strftime("%H:%M:%S", time.gmtime(now)), "markets right-side zt>=%g:" % (a.zmin - 1), len(pend),
                  "candidates", len(cand), "fills", len(state["fills"]), "vanished", state["vanished"], flush=True)
        except Exception as ex:                    # never die on a bad cycle
            print("cycle error:", repr(ex)[:200], flush=True)
        if a.cycles and n >= a.cycles:
            break
        time.sleep(max(1.0, a.interval - (time.time() - now)))
    if state["fills"]:
        settle(state["fills"])
        (RAW / "fills.json").write_text(json.dumps(state["fills"]))
    out = write_summary(state, started)
    print(json.dumps({k: out[k] for k in ("cycles", "candidates_seen", "candidates_vanished", "pretend_fills", "wins", "losses", "pending")}))


if __name__ == "__main__":
    main()
