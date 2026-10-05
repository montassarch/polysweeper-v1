"""Dota 2 series comebacks (map level) from OpenDota's free proMatches list (series_id, series_type, winner).
States: Bo3 leader 1-0, Bo5 leader 2-0 / 2-1. Output: lab/results/2026-10-05-comeback-dota.json"""
import json, os, time, urllib.request, collections
UA = {'User-Agent': 'polysweeper-research/0.1 (read-only)'}
RAW = '/home/user/polysweeper-v1/lab/data/raw/dota_promatches.json'
rows = json.load(open(RAW)) if os.path.exists(RAW) else []
if not rows:
    lt = None
    for i in range(300):
        u = 'https://api.opendota.com/api/proMatches' + (f'?less_than_match_id={lt}' if lt else '')
        try:
            d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60))
        except Exception as e:
            print('err', i, e, flush=True); time.sleep(20); continue
        if not d: break
        rows += d
        lt = min(r['match_id'] for r in d)
        if i % 50 == 0: print(i, len(rows), flush=True)
        time.sleep(1.2)
    json.dump(rows, open(RAW, 'w'))
S = collections.defaultdict(list)
for r in rows:
    if r.get('series_id') and r.get('series_type') in (1, 2) and r.get('radiant_team_id') and r.get('dire_team_id'):
        S[(r['series_id'], r['series_type'])].append(r)
C = collections.defaultdict(lambda: [0, 0])
for (sid, st), gs in S.items():
    gs.sort(key=lambda r: r['start_time'])
    need = 2 if st == 1 else 3
    win = [r['radiant_team_id'] if r['radiant_win'] else r['dire_team_id'] for r in gs]
    w = collections.Counter(win)
    if max(w.values()) != need or len(w) > 2 or len(gs) > 2 * need - 1: continue
    champ = w.most_common(1)[0][0]
    tier = 'premium/pro' if (gs[0].get('league_name') or '') else '?'
    sc = collections.Counter()
    for t in win[:-1]:
        sc[t] += 1
        lead = max(sc, key=lambda x: sc[x]); lw = sc[lead]; tw = sum(sc.values()) - lw
        if lw == tw: continue
        k = f'Bo{2*need-1} {lw}-{tw}'
        C[k][0] += 1; C[k][1] += (lead != champ)
res = {k: {'n': v[0], 'lost': v[1], 'rate': round(v[1] / v[0], 4)} for k, v in sorted(C.items())}
json.dump({'series': len(S), 'states': res}, open('/home/user/polysweeper-v1/lab/results/2026-10-05-comeback-dota.json', 'w'), indent=0)
for k, v in res.items(): print(k, v)
