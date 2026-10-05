"""Download CS2 round-by-round map histories from bo3.gg's free public JSON API (read-only).
Saves compact rows to lab/data/raw/cs2_rounds/games_<page>.json : id, match_id, number, map,
winner, loser, rounds = list of round-winner names (in order). Also match info pages (bo_type, tier).
Usage: python3 comeback_cs2_fetch.py <max_game_pages> <max_match_pages>"""
import json, os, sys, time, urllib.request
UA = {'User-Agent': 'polysweeper-research/0.1 (read-only)'}
RAW = '/home/user/polysweeper-v1/lab/data/raw/cs2_rounds/'
os.makedirs(RAW, exist_ok=True)


def get(u, tries=3):
    for i in range(tries):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=90))
        except Exception as e:
            err = e; time.sleep(3 * (i + 1))
    print('fail', u, err, flush=True)
    return None


GP, MP = int(sys.argv[1]), int(sys.argv[2])
for p in range(GP):
    f = RAW + f'games_{p:04d}.json'
    if os.path.exists(f): continue
    d = get(f'https://api.bo3.gg/api/v1/games?with=game_rounds&page[limit]=100&page[offset]={p*100}'
            '&sort=-begin_at&filter[games.game_version][eq]=2&filter[games.status][eq]=finished')
    if not d: continue
    rows = []
    for g in d['results']:
        rr = sorted(g.get('game_rounds') or [], key=lambda r: r['round_number'])
        rows.append(dict(id=g['id'], match_id=g['match_id'], number=g['number'], map=g['map_name'],
                         begin=g['begin_at'], winner=g['winner_clan_name'], loser=g['loser_clan_name'],
                         ws=g['winner_clan_score'], ls=g['loser_clan_score'],
                         rounds=[r['winner_clan_name'] for r in rr]))
    json.dump(rows, open(f, 'w'))
    if p % 20 == 0: print('games page', p, flush=True)
    time.sleep(0.4)
for p in range(MP):
    f = RAW + f'matches_{p:04d}.json'
    if os.path.exists(f): continue
    d = get(f'https://api.bo3.gg/api/v1/matches?page[limit]=100&page[offset]={p*100}&sort=-start_date'
            '&filter[matches.status][eq]=finished&filter[matches.discipline_id][eq]=1')
    if not d: continue
    rows = [dict(id=m['id'], slug=m['slug'], bo=m['bo_type'], tier=m['tier'], t1=m['team1_id'], t2=m['team2_id'],
                 s1=m['team1_score'], s2=m['team2_score'], win=m['winner_team_id'], start=m['start_date'],
                 gv=m.get('game_version')) for m in d['results']]
    json.dump(rows, open(f, 'w'))
    if p % 20 == 0: print('match page', p, flush=True)
    time.sleep(0.4)
print('done')
