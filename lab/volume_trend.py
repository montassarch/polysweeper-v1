"""Where is Polymarket sports volume moving? Weekly count and traded volume of FINISHED events per league, last N weeks.
(ps-researcher 2026-10-10; read-only Gamma /events/keyset, public.)

  python3 lab/volume_trend.py [days=42]   -> lab/results/2026-10-10-volume-trend.json  (and a table on screen)

`volume` is the lifetime volume of the whole event (all markets of the match, incl. spreads/totals/props), in USD.
Week = ISO week of the match start (UTC). The newest week is incomplete.
"""
import collections, datetime, json, sys, time, urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
from polysweeper.collector import get_json, GAMMA, parse_ts  # noqa: E402

SERIES = {"ATP": 10365, "WTA": 10366, "CS2": 10310, "DOTA2": 10309, "LOL": 10311, "VAL": 10369,
          "EPL": 10188, "LAL": 10193, "BUN": 10194, "SEA": 10203, "FL1": 10195, "UCL": 10204, "MLS": 10189, "ELC": 10355, "BRA": 10359,
          "MLB": 3, "NFL": 12185, "CFB": 12756, "NHL": 10346, "NBA": 10345, "WNBA": 10105}
GROUP = {"ATP": "tennis", "WTA": "tennis", "CS2": "esports", "DOTA2": "esports", "LOL": "esports", "VAL": "esports",
         "EPL": "football", "LAL": "football", "BUN": "football", "SEA": "football", "FL1": "football", "UCL": "football", "MLS": "football",
         "ELC": "football", "BRA": "football", "MLB": "MLB", "NFL": "NFL", "CFB": "CFB", "NHL": "NHL", "NBA": "NBA/WNBA", "WNBA": "NBA/WNBA"}


def main(days):
    cutoff = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)).timestamp()
    rows = []
    for name, sid in SERIES.items():
        cur, n = "", 0
        while True:
            url = f"{GAMMA}/events/keyset?series_id={sid}&closed=true&limit=100&order=startDate&ascending=false"
            if cur:
                url += "&after_cursor=" + urllib.parse.quote(cur)
            resp = get_json(url)
            page = resp.get("events") if isinstance(resp, dict) else None
            if not isinstance(page, list) or not page:
                break
            stop = False
            for e in page:
                st = parse_ts(e["startTime"]) if e.get("startTime") else None
                if st is None:
                    continue
                if st < cutoff:
                    stop = True
                    continue
                try:
                    vol = float(e.get("volume") or 0)
                except (TypeError, ValueError):
                    vol = 0.0
                rows.append((name, st, vol))
                n += 1
            cur = resp.get("next_cursor") or ""
            if stop or len(page) < 100 or not cur:
                break
            time.sleep(0.2)
        print(name, n, flush=True)
    wk = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0.0]))
    for name, st, vol in rows:
        d = datetime.datetime.fromtimestamp(st, datetime.timezone.utc)
        iso = d.isocalendar()
        key = f"{iso[0]}-W{iso[1]:02d}"
        g = wk[GROUP[name]][key]
        g[0] += 1
        g[1] += vol
    weeks = sorted({k for g in wk.values() for k in g})
    out = {"weeks": weeks, "by_group": {g: {k: {"events": v[0], "volume_usd": round(v[1])} for k, v in sorted(d.items())} for g, d in wk.items()},
           "by_league_total": {n: {"events": sum(1 for r in rows if r[0] == n), "volume_usd": round(sum(r[2] for r in rows if r[0] == n))} for n in SERIES}}
    (ROOT / "lab/results/2026-10-10-volume-trend.json").write_text(json.dumps(out, indent=1))
    print("week      " + "".join(f"{g:>22}" for g in wk))
    for w in weeks:
        print(w + "  " + "".join(f"{wk[g][w][0]:>8} ev ${wk[g][w][1] / 1e6:>7.2f}M " for g in wk))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 42)
