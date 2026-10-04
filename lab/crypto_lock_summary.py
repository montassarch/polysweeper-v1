"""Summarise lab/data/raw/2026-10-04-crypto-lock-BTC.json (from crypto_lock_study.py) into
lab/results/2026-10-04-crypto-lock-summary.json: buys of one side at 0.95+ in the last 60 s, grouped by
seconds left and by how big an against-move (OKX proxy) would still flip the 60-s TWAP result."""
import json, collections
r = json.load(open('/home/user/polysweeper-v1/lab/data/raw/2026-10-04-crypto-lock-BTC.json'))
agg = collections.defaultdict(lambda: [0, 0, 0.0, 0.0]); post = collections.defaultdict(lambda: [0, 0, 0.0])
for x in r:
    for t in x['rows']:
        if t['p'] < 0.95: continue
        pb = '0.95-0.99' if t['p'] <= 0.99 else ('0.99-0.998' if t['p'] <= 0.998 else '>0.998')
        if t['k'] <= 0:
            a = post[pb]; a[0] += 1; a[1] += not t['won']; a[2] += t['sz']; continue
        if not x['proxy_ok'] or t['req'] is None: continue
        need = -t['req'] if t['bought'] == 'Up' else t['req']   # >0: price must move AGAINST the buyer by this fraction
        rb = '>0.3%' if need > 0.003 else ('0.1-0.3%' if need > 0.001 else ('0.03-0.1%' if need > 0.0003 else '<0.03% (or behind)'))
        kb = '1-10s' if t['k'] <= 10 else ('11-30s' if t['k'] <= 30 else '31-60s')
        a = agg[f'{kb} | flip needs {rb} | {pb}']; a[0] += 1; a[1] += not t['won']; a[2] += t['sz']; a[3] += t['sz'] * ((1 if t['won'] else 0) - t['p'])
out = dict(markets=len(r), proxy_agrees=sum(x['proxy_ok'] for x in r),
           before_end={k: dict(buys=v[0], lost=v[1], shares=round(v[2]), pnl=round(v[3], 1)) for k, v in sorted(agg.items())},
           after_end={k: dict(buys=v[0], lost=v[1], shares=round(v[2])) for k, v in post.items()})
json.dump(out, open('/home/user/polysweeper-v1/lab/results/2026-10-04-crypto-lock-summary.json', 'w'), indent=1)
for k, v in out['before_end'].items(): print(k, v)
print('after end', out['after_end'])
