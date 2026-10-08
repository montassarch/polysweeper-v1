"""Download Yahoo Finance 1-minute bars (regular session only) for the tickers of the stock ladder study.

  python3 lab/stock_ladder_yahoo.py NVDA SPY ...      (default: every ticker in events.json)
  python3 lab/stock_ladder_yahoo.py daily             (daily bars, 2 years, for the overnight-gap volatility)
Writes lab/data/raw/stockladder/yahoo/<TICKER>.json = {"t": [...unix secs...], "o","h","l","c","v"} merged over
runs (Yahoo keeps only about 30 days of 1-minute data, so re-run weekly to extend the history).
Yahoo's chart endpoint answers 429 for the default Python/curl user agents; a browser user agent works.
Read-only public data. Used only as a stand-in for the settlement source (Pyth), see R-2026-10-08.
"""
import json, sys, time, urllib.request, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "lab/data/raw/stockladder/yahoo"
OUT.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept": "application/json,text/plain,*/*", "Accept-Language": "en-US,en;q=0.9"}


def fetch(sym, p1, p2, tries=5):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1m&period1={p1}&period2={p2}"
           f"&includePrePost=false&events=div%7Csplit")
    delay = 2.0
    for _ in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503):
                time.sleep(delay)
                delay *= 2
                continue
            return None
        except Exception:
            time.sleep(delay)
            delay *= 2
    return None


def pull(sym, days=30, step=6):
    f = OUT / f"{sym}.json"
    have = json.loads(f.read_text()) if f.exists() else {"t": [], "o": [], "h": [], "l": [], "c": [], "v": []}
    rows = {t: (o, h, l, c, v) for t, o, h, l, c, v in zip(have["t"], have["o"], have["h"], have["l"], have["c"], have["v"])}
    now = int(time.time())
    end = now
    start = now - days * 86400
    cur = start
    n_new = 0
    while cur < end:
        nxt = min(cur + step * 86400, end)
        d = fetch(sym, cur, nxt)
        time.sleep(0.6)
        try:
            res = d["chart"]["result"][0]
            ts = res.get("timestamp") or []
            q = res["indicators"]["quote"][0]
            for i, t in enumerate(ts):
                if q["close"][i] is None:
                    continue
                if t not in rows:
                    n_new += 1
                rows[t] = (q["open"][i], q["high"][i], q["low"][i], q["close"][i], q["volume"][i])
        except Exception:
            pass
        cur = nxt
    ts = sorted(rows)
    out = {"t": ts, "o": [rows[t][0] for t in ts], "h": [rows[t][1] for t in ts], "l": [rows[t][2] for t in ts],
           "c": [rows[t][3] for t in ts], "v": [rows[t][4] for t in ts]}
    f.write_text(json.dumps(out))
    return len(ts), n_new


def pull_daily(sym, rng="2y"):
    """daily bars (for the overnight-gap volatility) -> lab/data/raw/stockladder/yahoo_daily/<TICKER>.json"""
    out_dir = OUT.parent / "yahoo_daily"
    out_dir.mkdir(parents=True, exist_ok=True)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range={rng}&includePrePost=false"
    delay = 2.0
    for _ in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                d = json.load(r)
            res = d["chart"]["result"][0]
            q = res["indicators"]["quote"][0]
            rows = [(t, o, h, l, c) for t, o, h, l, c in zip(res["timestamp"], q["open"], q["high"], q["low"], q["close"]) if c is not None and o is not None]
            (out_dir / f"{sym}.json").write_text(json.dumps({"t": [x[0] for x in rows], "o": [x[1] for x in rows], "c": [x[4] for x in rows]}))
            return len(rows)
        except Exception:
            time.sleep(delay); delay *= 2
    return 0


if __name__ == "__main__":
    if sys.argv[1:2] == ["daily"]:
        evs0 = json.loads((ROOT / "lab/data/raw/stockladder/events.json").read_text())
        for s in sorted({e["ticker"] for e in evs0}):
            print(s, "daily bars", pull_daily(s), flush=True)
            time.sleep(0.6)
        sys.exit(0)
    syms = sys.argv[1:]
    if not syms:
        evs = json.loads((ROOT / "lab/data/raw/stockladder/events.json").read_text())
        syms = sorted({e["ticker"] for e in evs})
    for s in syms:
        n, new = pull(s)
        print(s, "bars", n, "new", new, flush=True)
