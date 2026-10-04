"""Read-only 'does the price lag reality' check. Open Highest-temperature events for the station's current local day:
observed max so far from aviationweather.gov METAR (station = site= in resolutionSource), compared with brackets.
For brackets whose upper edge is already passed (margin in market units), record NO best ask/size and YES best bid
from the CLOB. Appends one JSON line per run to lab/data/raw/weather/obs_vs_price.jsonl and prints a summary.
Note: METAR max is a proxy for the resolution source (NOAA timeseries / Wunderground)."""
import json, os, re, sys, time, urllib.request, datetime as dt
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from weather_cities import TZ, city_kind
from weather_fetch import g, RAW

UA = {"User-Agent": "ps-lab/1.0 (read-only research)", "Content-Type": "application/json"}


def books(tokens):
    for i in range(3):
        try:
            req = urllib.request.Request("https://clob.polymarket.com/books", data=json.dumps([{"token_id": t} for t in tokens]).encode(), headers=UA)
            return {b["asset_id"]: b for b in json.load(urllib.request.urlopen(req, timeout=60))}
        except Exception:
            time.sleep(2 + 2 * i)
    return {}


def upper(title):  # upper edge of bracket in market units; None for the open-top bracket
    if "or higher" in title or "or above" in title:
        return None
    nums = [int(x) for x in re.findall(r"(?<!\d)-?\d+", title)]
    return max(nums) if nums else None


now = dt.datetime.now(dt.timezone.utc)
evs = []
for off in (0, 100, 200, 300):
    p = g(f"https://gamma-api.polymarket.com/events?tag_slug=daily-temperature&closed=false&limit=100&offset={off}") or []
    evs += p
    if len(p) < 100:
        break
rows, summ = [], []
for e in evs:
    city, kind = city_kind(e["title"])
    src = e.get("resolutionSource") or (e["markets"][0].get("resolutionSource") if e["markets"] else "") or ""
    m = re.search(r"site=([a-zA-Z0-9]{4})", src)
    if kind != "H" or city not in TZ or not m:
        continue
    tz = ZoneInfo(TZ[city]); loc = now.astimezone(tz)
    if loc.date().isoformat() != e.get("eventDate"):
        continue
    sid = m.group(1).upper()
    met = g(f"https://aviationweather.gov/api/data/metar?ids={sid}&format=json&hours=30") or []
    time.sleep(0.3)
    d0 = dt.datetime.fromisoformat(e["eventDate"]).replace(tzinfo=tz).timestamp()
    temps = [x["temp"] for x in met if x.get("temp") is not None and x.get("obsTime", 0) >= d0]
    if not temps:
        continue
    mx_c = max(temps)
    ms = sorted([x for x in e["markets"] if x.get("clobTokenIds")], key=lambda x: int(x["groupItemThreshold"]))
    unit_f = "°F" in ms[0]["groupItemTitle"]
    mx = round(mx_c * 9 / 5 + 32) if unit_f else round(mx_c)
    toks = [json.loads(x["clobTokenIds"]) for x in ms]
    B = books([t for tt in toks for t in tt]); time.sleep(0.3)
    passed = 0
    for i, (mk, (y, n)) in enumerate(zip(ms, toks)):
        u = upper(mk["groupItemTitle"])
        if u is None or mx - u < 1:
            continue
        passed += 1
        asks = sorted((float(a["price"]), float(a["size"])) for a in B.get(n, {}).get("asks", []))
        yb = max([float(b["price"]) for b in B.get(y, {}).get("bids", [])] or [0])
        rows.append({"city": city, "local": loc.strftime("%H:%M"), "obs_max": mx, "unit": "F" if unit_f else "C",
                     "bracket": mk["groupItemTitle"], "margin": mx - u, "lowest": i == 0,
                     "no_ask": asks[0][0] if asks else None, "no_ask_sz": asks[0][1] if asks else 0,
                     "no_sz_le_995": round(sum(s for p, s in asks if p <= 0.995), 1),
                     "no_sz_le_998": round(sum(s for p, s in asks if p <= 0.998), 1), "yes_bid": yb,
                     "accepting": mk.get("acceptingOrders")})
    summ.append((city, loc.strftime("%H:%M"), sid, mx, passed))
rec = {"ts": now.isoformat(), "events": summ, "rows": rows}
with open(os.path.join(RAW, "obs_vs_price.jsonl"), "a") as f:
    f.write(json.dumps(rec) + "\n")
print(now.strftime("%Y-%m-%d %H:%M UTC"), "H events with METAR today:", len(summ), " passed brackets:", len(rows))
cheap = [r for r in rows if r["no_ask"] is not None and r["no_ask"] <= 0.998]
print(" passed brackets with NO ask <=0.998:", len(cheap), " empty NO book:", sum(1 for r in rows if r["no_ask"] is None),
      " at 0.999:", sum(1 for r in rows if r["no_ask"] == 0.999))
for r in cheap[:20]:
    print("  ", r)
