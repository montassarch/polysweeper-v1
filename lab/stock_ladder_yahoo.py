"""Download Yahoo Finance 1-minute bars (regular session only) for the tickers of the stock ladder study.

  python3 lab/stock_ladder_yahoo.py NVDA SPY ...      (default: every ticker in events.json)
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


if __name__ == "__main__":
    syms = sys.argv[1:]
    if not syms:
        evs = json.loads((ROOT / "lab/data/raw/stockladder/events.json").read_text())
        syms = sorted({e["ticker"] for e in evs})
    for s in syms:
        n, new = pull(s)
        print(s, "bars", n, "new", new, flush=True)
