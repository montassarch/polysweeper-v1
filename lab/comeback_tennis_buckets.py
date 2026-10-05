"""Tennis Markov model for the tester's buckets (lab/results/2026-10-05-state-supply.json).
Equal-strength players; p = serve-point win rate. Output lab/results/2026-10-05-comeback-tennis-buckets.json"""
import json
from comeback_tennis_model import make
P = {'ATP main tour p=0.64': (0.64, 0.64), 'ATP Challenger p=0.62': (0.62, 0.62),
     'WTA p=0.56': (0.56, 0.56), 'WTA/ITF p=0.54': (0.54, 0.54),
     'ATP, leader stronger 0.66 v 0.62': (0.66, 0.62), 'WTA, leader stronger 0.58 v 0.54': (0.58, 0.54)}
ST = []
for sets, lab in (((1, 0), '1 set up, set 2'), ((1, 1), 'deciding set')):
    for g in ((3, 0), (4, 0), (4, 1), (5, 0), (5, 1), (5, 2)):
        for srv in (True, False):
            ST.append((f'{lab} {g[0]}-{g[1]}, {"leader" if srv else "trailer"} to serve', sets[0], sets[1], g[0], g[1], srv))
out = {}
for name, (pa, pb) in P.items():
    f = make(pa, pb, 3)
    out[name] = {s[0]: round(1 - f(*s[1:]), 5) for s in ST}
json.dump(out, open('/home/user/polysweeper-v1/lab/results/2026-10-05-comeback-tennis-buckets.json', 'w'), indent=1)
keys = [s[0] for s in ST]
print('state'.ljust(42) + ''.join(n.split(' p=')[0][:12].rjust(13) for n in P))
for k in keys:
    print(k.ljust(42) + ''.join(f'{"1/%d" % round(1/out[n][k]):>13}' for n in P))
