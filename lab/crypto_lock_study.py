"""Idea #16: crypto Up/Down 5-minute markets settle on a 60-s Chainlink TWAP (end TWAP vs TWAP at start).
In the last k seconds, (60-k)/60 of the end average is already fixed. For each recent market and each public
trade in the last 60 s and after the end: how big a price move would still flip the result ("required move"),
what price the eventual winner was bought at, and did any confident buy lose. Price proxy: OKX 1-second
candles (Chainlink itself is not public here; Binance is blocked). Usage: python3 lab/crypto_lock_study.py BTC 150
Output: lab/data/raw/2026-10-04-crypto-lock.json"""
import json, sys, time, urllib.request, collections
UA = {'User-Agent': 'polysweeper-research/0.1 (read-only)'}
def get(u):
    for i in range(3):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30))
        except Exception: time.sleep(1 + i)
def okx(sym, t0, t1):
    """1-s closes for [t0, t1) as dict sec->price"""
    out = {}
    after = (t1 + 1) * 1000
    while True:
        d = get(f'https://www.okx.com/api/v5/market/history-candles?instId={sym}-USDT&bar=1s&limit=100&after={after}')
        rows = (d or {}).get('data') or []
        if not rows: break
        for r in rows: out[int(r[0]) // 1000] = float(r[4])
        after = int(rows[-1][0])
        if after // 1000 <= t0: break
        time.sleep(0.12)
    return out
def avg(px, a, b):
    v = [px[s] for s in range(a, b) if s in px]
    return sum(v) / len(v) if v else None
def trades(cid):
    rows, off = [], 0
    while off <= 3000:
        pg = get(f'https://data-api.polymarket.com/trades?market={cid}&limit=500&offset={off}')
        if not pg: break
        rows += pg
        if len(pg) < 500: break
        off += 500
    return rows
sym, N = sys.argv[1], int(sys.argv[2])
now = int(time.time()) // 300 * 300 - 600
res = []
for i in range(N):
    st = now - 300 * i; en = st + 300
    ev = get(f'https://gamma-api.polymarket.com/events?slug={sym.lower()}-updown-5m-{st}')
    if not ev: continue
    m = ev[0]['markets'][0]
    oc = json.loads(m['outcomes']); op = json.loads(m.get('outcomePrices') or '[]')
    if not op or max(map(float, op)) < 0.99: continue
    win = oc[[float(x) for x in op].index(max(map(float, op)))]
    px = okx(sym, st - 61, en + 90)
    S = avg(px, st - 60, st); E = avg(px, en - 60, en)
    if S is None or E is None: continue
    proxy = 'Up' if E >= S else 'Down'
    rows = []
    for t in trades(m['conditionId']):
        ts = t['timestamp']
        if ts < en - 60: continue
        w = t['outcome'] == win
        if t['side'] == 'BUY': side_bought, p = t['outcome'], t['price']
        else: side_bought, p = [o for o in oc if o != t['outcome']][0], 1 - t['price']   # taker SELL = maker bought other side
        k = en - ts
        if k > 0:
            A = avg(px, en - 60, ts + 1); P = px.get(ts) or px.get(ts - 1)
            if A is None or not P: continue
            F = (60 * S - (60 - k) * A) / k if k > 0 else None
            req = (F / P - 1)   # move needed in remaining k s to land exactly on the reference
            lead = 'Up' if (60 - k) * A + k * P >= 60 * S else 'Down'
        else:
            req, lead = None, proxy
        rows.append(dict(k=k, bought=side_bought, p=round(p, 4), sz=t['size'], won=side_bought == win, req=req, lead=lead, maker=t['side'] == 'SELL'))
    res.append(dict(st=st, win=win, proxy_ok=proxy == win, margin=(E / S - 1), closed=m.get('closedTime'), rows=rows))
    time.sleep(0.1)
json.dump(res, open(f'/home/user/polysweeper-v1/lab/data/raw/2026-10-04-crypto-lock-{sym}.json', 'w'))
print('markets', len(res), 'proxy agrees', sum(r['proxy_ok'] for r in res))
