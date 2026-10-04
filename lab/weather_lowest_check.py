"""Read-only: closed temperature events that resolved to the LOWEST bracket (last ~40 days). Did the lowest bracket's
price agree before resolution (no-data rule check)? Uses trades cached by weather_fetch.py, or fetches into
lab/data/raw/weather/trades_low/. Prints one line per event and a summary."""
import json, os, sys, time, datetime as dt
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from weather_cities import TZ, city_kind
from weather_fetch import g, RAW

evs = {e["id"]: e for e in json.load(open(os.path.join(RAW, "events_closed.json")))}
ids = json.load(open(os.path.join(RAW, "lowest_winner_ids.json")))
os.makedirs(os.path.join(RAW, "trades_low"), exist_ok=True)
flag = 0; rows = []
for eid in ids:
    e = evs[eid]
    f1, f2 = os.path.join(RAW, "trades", eid + ".json"), os.path.join(RAW, "trades_low", eid + ".json")
    if os.path.exists(f1):
        tr = json.load(open(f1))
    elif os.path.exists(f2):
        tr = json.load(open(f2))
    else:
        tr = g(f"https://data-api.polymarket.com/trades?eventId={eid}&limit=1000&takerOnly=true") or []
        json.dump(tr, open(f2, "w")); time.sleep(0.3)
    city, kind = city_kind(e["title"])
    tz = ZoneInfo(TZ[city])
    ms = sorted(e["markets"], key=lambda m: int(m["groupItemThreshold"]))
    cid = ms[0]["conditionId"]
    end = dt.datetime.fromisoformat(e["eventDate"]).replace(tzinfo=tz) + dt.timedelta(days=1)
    ys = [(t["timestamp"], t["price"] if t["outcome"] == "Yes" else 1 - t["price"]) for t in tr if t["conditionId"] == cid]
    before = [y for ts, y in sorted(ys) if ts < end.timestamp()]
    last6 = [y for ts, y in ys if end.timestamp() - 6 * 3600 <= ts < end.timestamp()]
    lastp = before[-1] if before else None
    mx6 = max(last6) if last6 else None
    bad = (mx6 is not None and mx6 < 0.5) or (mx6 is None and (lastp is None or lastp < 0.5))
    flag += bad
    rows.append((e["eventDate"], city, kind, ms[0]["groupItemTitle"], lastp and round(lastp, 3), mx6 and round(mx6, 3),
                 len(tr), "CHECK" if bad else "ok"))
for r in sorted(rows):
    if r[-1] == "CHECK":
        print(r)
print("lowest-bracket winners", len(rows), "flagged (lowest YES < 0.5 in last 6h of local day or no price)", flag)
