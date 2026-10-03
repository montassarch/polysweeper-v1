"""Read-only: download closed daily-temperature events (gamma) for the last N days, then the taker trades of
each event (data-api, one call per event via eventId). Caches in lab/data/raw/weather/ (git-ignored).
Usage: python3 lab/weather_fetch.py events 40      -> events_closed.json (last 40 days of event dates)
       python3 lab/weather_fetch.py trades 2026-09-20 2026-10-02  -> trades/<eventId>.json"""
import json, os, sys, time, urllib.request, urllib.error, datetime as dt

RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "raw", "weather")
UA = {"User-Agent": "ps-lab/1.0"}


def g(u, tries=5):
    for i in range(tries):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60))
        except urllib.error.HTTPError as ex:
            if ex.code in (400, 404, 422):
                return None
            time.sleep(2 + 3 * i)
        except Exception:
            time.sleep(2 + 3 * i)
    return None


def events(days):
    os.makedirs(RAW, exist_ok=True)
    today = dt.date.today()
    out, seen = [], set()
    for k in range(days + 2):
        d = today - dt.timedelta(days=k)
        lo, hi = d.isoformat() + "T00:00:00Z", (d + dt.timedelta(days=1)).isoformat() + "T00:00:00Z"
        for off in range(0, 600, 100):
            p = g(f"https://gamma-api.polymarket.com/events?tag_slug=daily-temperature&closed=true&limit=100&offset={off}"
                  f"&end_date_min={lo}&end_date_max={hi}") or []
            for e in p:
                if e["id"] not in seen:
                    seen.add(e["id"]); out.append(e)
            time.sleep(0.2)
            if len(p) < 100:
                break
        print(d, len(out), file=sys.stderr)
    json.dump(out, open(os.path.join(RAW, "events_closed.json"), "w"))
    print("events", len(out))


def trades(d0, d1):
    evs = json.load(open(os.path.join(RAW, "events_closed.json")))
    tdir = os.path.join(RAW, "trades"); os.makedirs(tdir, exist_ok=True)
    todo = [e for e in evs if d0 <= (e.get("eventDate") or "") <= d1]
    n = 0
    for e in todo:
        f = os.path.join(tdir, e["id"] + ".json")
        if os.path.exists(f):
            continue
        allt, off = [], 0
        while True:
            p = g(f"https://data-api.polymarket.com/trades?eventId={e['id']}&limit=1000&offset={off}&takerOnly=true")
            n += 1
            if p is None:
                break
            allt += p
            if len(p) < 1000 or off >= 9000:
                break
            off += 1000; time.sleep(0.3)
        json.dump(allt, open(f, "w"))
        time.sleep(0.3)
    print("events", len(todo), "requests", n)


if __name__ == "__main__":
    if sys.argv[1] == "events":
        events(int(sys.argv[2]))
    else:
        trades(sys.argv[2], sys.argv[3])
