"""Month-end on a weekend: US stocks stop trading Friday 16:00 ET but the monthly ladders run to Sunday 23:59 ET.
Does the dead window (about 56 h for a Sunday month-end, 32 h for a Saturday one) keep cheap asks alive for hours?
Looks at the monthly Polymarket stock ladders of May 2026 (month-end Sunday 31 May; last session Fri 29 May):
BUY trades on the token that WON at 0.98-0.995, by hours after the Friday close. Read-only.
  python3 lab/stock_monthend_weekend.py 2026-05-25 2026-06-02 [last_session_close_utc e.g. 2026-05-29T20:00:00]
"""
import collections, datetime, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code")); sys.path.insert(0, str(ROOT / "lab"))
import stock_ladder_pull as P  # noqa: E402
from polysweeper.collector import get_json  # noqa: E402
d0, d1 = sys.argv[1], sys.argv[2]
close = datetime.datetime.strptime(sys.argv[3] if len(sys.argv) > 3 else "2026-05-29T20:00:00", "%Y-%m-%dT%H:%M:%S").replace(tzinfo=datetime.timezone.utc).timestamp()
evs = [P.slim_event(e) for e in P.list_events(d0, d1)]
evs = [e for e in evs if e["family"] in ("monthly_hit", "monthly_above")]
print("monthly events", len(evs), collections.Counter(e["family"] for e in evs), [e["endDate"] for e in evs[:2]])
hist = collections.Counter(); sh = collections.Counter(); allbuy = collections.Counter(); n_events = 0
for e in evs:
    fin = {}
    for m in e["markets"]:
        try: px = [float(x) for x in m["final"]]
        except Exception: continue
        if sorted(px) == [0.0, 1.0]: fin[m["cid"]] = px
    rows, off = [], 0
    while off <= 15000:
        try: pg = get_json(f"{P.DATA}/trades?eventId={e['id']}&limit=500&offset={off}")
        except Exception: break
        if not isinstance(pg, list) or not pg: break
        rows += pg
        if len(pg) < 500: break
        off += 500
    n_events += 1
    for t in rows:
        if t["side"] != "BUY" or t["timestamp"] < close: continue
        px = fin.get(t["conditionId"])
        if px is None: continue
        h = (t["timestamp"] - close) / 3600.0
        b = "0-2min" if h < 1 / 30 else "2-10min" if h < 1 / 6 else "10-60min" if h < 1 else "1-6h" if h < 6 else "6-24h" if h < 24 else "24h+"
        allbuy[b] += 1
        if px[t["outcomeIndex"]] == 1.0 and 0.98 <= t["price"] <= 0.995:
            hist[b] += 1; sh[b] += t["size"]
order = ["0-2min", "2-10min", "10-60min", "1-6h", "6-24h", "24h+"]
print("events", n_events)
print("BUY trades after the Friday close on the WINNING token at 0.98-0.995, by time after close (trades / shares):")
for b in order: print(f"  {b:9s} {hist[b]:4d} {sh[b]:8.0f}   (all BUYs in that bucket: {allbuy[b]})")
