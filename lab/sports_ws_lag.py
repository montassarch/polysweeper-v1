"""How early does Polymarket's Sports WebSocket report a result, compared with shadow mode?

Joins lab/data/raw/sports_ws/*.jsonl (from sports_ws_record.py) with shadow mode's end-window records
(same PC clock). Times are seconds relative to t0 = when shadow mode saw the result (negative = earlier).
  ws_final : first ws message showing the final score
  ws_ended : first ws message with ended=true or a finished status
  v1_gone  : our band (0.96-0.995) emptied     bid99 : a 0.99 bid appeared
Run: py -3 lab/sports_ws_lag.py [events.jsonl]   (default: the live PC clone's file)
Writes lab/results/<date>-sports-ws-lag.json.
"""
import collections, datetime, glob, json, os, statistics, sys, urllib.request

HERE = os.path.dirname(__file__)
EVENTS = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\LAPTOP\polysweeper-v1\code\data\shadow\events.jsonl"
DONE = {"finished", "final", "f/ot", "f/so", "ended", "complete", "completed"}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "polysweeper-lab"})
    return json.load(urllib.request.urlopen(req, timeout=20))


def load_ws():
    games, start = collections.defaultdict(list), None
    for path in sorted(glob.glob(os.path.join(HERE, "data", "raw", "sports_ws", "*.jsonl"))):
        for line in open(path, encoding="utf-8"):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            start = r["t"] if start is None else min(start, r["t"])
            m = r.get("m")
            if isinstance(m, dict) and m.get("gameId") is not None:
                games[int(m["gameId"])].append((r["t"], m))
    return games, start


def game_id(market_id, cache={}):
    if market_id not in cache:
        try:
            m = get(f"https://gamma-api.polymarket.com/markets/{market_id}")
            gid = m.get("gameId")                    # markets carry it directly; events only sometimes listed
            if gid is None and m.get("events"):
                gid = get(f"https://gamma-api.polymarket.com/events/{m['events'][0]['id']}").get("gameId")
            cache[market_id] = gid
        except Exception:
            cache[market_id] = None
    return cache[market_id]


def main():
    games, start = load_ws()
    if start is None:
        sys.exit("no sports_ws recording yet")
    rows = []
    for line in open(EVENTS, encoding="utf-8"):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("type") != "end_window" or d["t0"] < start + 60 or "stopped" in (d.get("closed_because") or ""):
            continue
        gid = game_id(d["market_id"])
        msgs = games.get(int(gid)) if gid else None
        if not msgs:                                 # tennis markets carry no gameId: match both names in the title
            title = (d.get("title") or "").lower()
            for g, ms in games.items():
                m0 = ms[-1][1]
                if (m0.get("homeTeam") and m0.get("awayTeam") and m0["homeTeam"].lower() in title
                        and m0["awayTeam"].lower() in title and abs(ms[-1][0] - d["t0"]) < 3600):
                    gid, msgs = g, ms
                    break
        row = {"league": d["league"], "title": (d.get("title") or "")[:70], "trigger": d["first_trigger"], "game_id": gid}
        if msgs:
            final = msgs[-1][1].get("score")
            ws_final = next((t for t, m in msgs if m.get("score") == final), None)
            ws_ended = next((t for t, m in msgs if m.get("ended") or str(m.get("status", "")).lower() in DONE), None)
            row.update(final_score=final,
                       ws_final=None if ws_final is None else round(ws_final - d["t0"], 1),
                       ws_ended=None if ws_ended is None else round(ws_ended - d["t0"], 1))
        for k, col in (("v1_gone", "live_v1_until_s"), ("bid99", "live_bid099_at_s")):
            row[k] = d.get(col)
        rows.append(row)

    print(f"recording since {datetime.datetime.fromtimestamp(start):%Y-%m-%d %H:%M}, end windows: {len(rows)}, "
          f"matched to the feed: {sum('ws_ended' in r for r in rows)}")
    for r in rows:
        print(f"{r['league']:7} ws_final {r.get('ws_final')!s:>7} ws_ended {r.get('ws_ended')!s:>7} "
              f"v1_gone {r['v1_gone']!s:>8} bid99 {r['bid99']!s:>8} | {r['title'][:45]}")
    summary = {}
    for k in ("ws_final", "ws_ended", "v1_gone", "bid99"):
        v = [r[k] for r in rows if r.get(k) is not None]
        if v:
            summary[k] = {"n": len(v), "median_s": statistics.median(v), "min_s": min(v), "max_s": max(v)}
            print(f"{k:9} n={len(v):3}  median {statistics.median(v):7.1f} s  range {min(v)} .. {max(v)}")
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    out = os.path.join(HERE, "results", f"{datetime.date.today()}-sports-ws-lag.json")
    json.dump({"summary": summary, "rows": rows}, open(out, "w", encoding="utf-8"), indent=1)
    print("saved", out)


if __name__ == "__main__":
    main()
