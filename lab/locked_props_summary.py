"""Summarise locked-line scans (raw files in lab/data/raw/) into lab/results/2026-10-04-locked-props-summary.json:
lock predictions vs settlement, and how many locked markets still had >=5 shares of the winner traded at
0.90-0.99 (taker buys = an ask was resting; bid fills = a resting buy order at that price got filled)
at least N seconds after the lock."""
import json
RAW = '/home/user/polysweeper-v1/lab/data/raw/'
def acc(sel, lo, a=0.9, b=0.99):
    o = dict(mk_taker=0, sh_taker=0, mk_bid=0, sh_bid=0)
    for x in sel:
        t = sum(p[3] for p in x['post'] if p[0] >= lo and p[1] == 'taker_buy_win' and a <= p[2] <= b)
        m = sum(p[3] for p in x['post'] if p[0] >= lo and p[1].startswith('maker_bid') and a <= p[2] <= b)
        o['mk_taker'] += t >= 5; o['mk_bid'] += m >= 5; o['sh_taker'] += round(t); o['sh_bid'] += round(m)
    return o
out = {}
for name, files in (('MLB 2026-09-20..10-03', ['2026-09-26-locked-props.json', '2026-10-03-locked-props.json']), ('NFL 2026-09-17..10-03', ['2026-10-04-locked-props-nfl.json'])):
    r = [x for f in files for x in json.load(open(RAW + f))]
    ok = [x for x in r if x['settled_ok'] and (x['closed'] or 1e12) > x['lock']]
    d = sorted(x['closed'] - x['lock'] for x in ok if x['closed'])
    out[name] = dict(locked_markets=len(r), settled_as_predicted=sum(x['settled_ok'] for x in r),
                     mismatches_note='all MLB mismatches = doubleheaders/slug-date errors matched to the wrong game' if len(r) != len(ok) else '',
                     median_secs_lock_to_close=round(d[len(d) // 2]) if d else None,
                     **{f'after_{lo}s_0.90-0.99': acc(ok, lo) for lo in (0, 10, 30, 60, 120, 300)},
                     **{f'after_{lo}s_0.991-0.998': acc(ok, lo, 0.9901, 0.998) for lo in (10, 120)})
json.dump(out, open('/home/user/polysweeper-v1/lab/results/2026-10-04-locked-props-summary.json', 'w'), indent=1)
print(json.dumps(out)[:1500])
