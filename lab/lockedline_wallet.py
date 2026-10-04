"""Lab idea #17 (locked lines): which of wallet 0x4dDC...'s 0.95+ buys are on side markets
(totals Over/Under, spreads, NRFI, BTTS) and did they win? Uses lab/data/raw/4ddc_trades.json
(Data API trades) + Gamma markets for results. Output: lab/data/raw/2026-10-04-lockedline-wallet.json"""
import json, sys, re, collections, time
sys.path.insert(0, '/home/user/polysweeper-v1/code')
from polysweeper.collector import get_json, GAMMA
R = '/home/user/polysweeper-v1/lab/'
tr = [t for t in json.load(open(R + 'data/raw/4ddc_trades.json')) if t['side'] == 'BUY' and t['price'] >= 0.95]
cids = sorted({t['conditionId'] for t in tr})
info = {}
for i in range(0, len(cids), 20):
    q = '&'.join('condition_ids=' + c for c in cids[i:i + 20])
    for m in get_json(f'{GAMMA}/markets?{q}&limit=50&closed=true') or []:
        info[m['conditionId']] = m
    for m in get_json(f'{GAMMA}/markets?{q}&limit=50') or []:
        info.setdefault(m['conditionId'], m)
    time.sleep(0.1)
def typ(s):
    m = re.match(r'^[a-z0-9]+-[a-z0-9]+-[a-z0-9]+-\d{4}-\d{2}-\d{2}(?:-(.*))?$', s)
    t = (m.group(1) if m else '?') or 'moneyline'
    return re.sub(r'\d+pt\d+', 'X', t)
out = collections.defaultdict(lambda: [0, 0, 0, 0.0])  # buys, wins, losses, pnl
rows = []
for t in tr:
    m = info.get(t['conditionId'])
    res = None
    if m and m.get('outcomePrices'):
        op = json.loads(m['outcomePrices']); oc = json.loads(m['outcomes'])
        if m.get('closed') and max(map(float, op)) > 0.99:
            res = float(op[oc.index(t['outcome'])]) if t['outcome'] in oc else None
    k = (t['slug'].split('-')[0], typ(t['slug']), t['outcome'] if t['outcome'] in ('Over', 'Under', 'Yes', 'No') else 'team')
    o = out[k]; o[0] += 1
    if res is not None:
        if res > 0.5: o[1] += 1
        else: o[2] += 1
        o[3] += t['size'] * (res - t['price'])
    rows.append(dict(slug=t['slug'], outcome=t['outcome'], price=t['price'], size=t['size'], ts=t['timestamp'], res=res,
                     cid=t['conditionId'], q=(m or {}).get('question')))
json.dump(rows, open(R + 'data/raw/2026-10-04-lockedline-wallet.json', 'w'))
for k, v in sorted(out.items(), key=lambda x: -x[1][0])[:30]:
    print(k, v[0], 'W', v[1], 'L', v[2], 'pnl', round(v[3], 1))
