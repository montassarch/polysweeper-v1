"""Read-only live snapshot: open daily-temperature events whose station-local clock is past 18:00 (Highest) or
10:00 (Lowest) on the event date. Brackets >=2 on the dead side of the price favourite (best YES bid): NO ask depth
at <=0.99 / <=0.995 / <=0.998 (shares and $). Lowest bracket excluded (no-data rule risk) and shown apart."""
import json, os, sys, time, urllib.request, datetime as dt
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from weather_cities import TZ, city_kind
from weather_fetch import g

UA = {"User-Agent": "ps-lab/1.0", "Content-Type": "application/json"}


def books(tokens):
    for i in range(3):
        try:
            req = urllib.request.Request("https://clob.polymarket.com/books", data=json.dumps([{"token_id": t} for t in tokens]).encode(), headers=UA)
            return {b["asset_id"]: b for b in json.load(urllib.request.urlopen(req, timeout=60))}
        except Exception:
            time.sleep(2 + 2 * i)
    return {}


now = dt.datetime.now(dt.timezone.utc)
evs = []
for off in (0, 100, 200, 300):
    p = g(f"https://gamma-api.polymarket.com/events?tag_slug=daily-temperature&closed=false&limit=100&offset={off}") or []
    evs += p
    if len(p) < 100:
        break
tot = {"<=0.99": [0, 0], "<=0.995": [0, 0], "<=0.998": [0, 0]}; low_br = [0, 0]; BEST = {}; rows = []; n_ev = 0
for e in evs:
    city, kind = city_kind(e["title"])
    if not city or city not in TZ or not e.get("eventDate"):
        continue
    loc = now.astimezone(ZoneInfo(TZ[city]))
    if loc.date().isoformat() != e["eventDate"] or loc.hour < (18 if kind == "H" else 10):
        continue
    ms = sorted([m for m in e["markets"] if m.get("clobTokenIds")], key=lambda m: int(m["groupItemThreshold"]))
    toks = [json.loads(m["clobTokenIds"]) for m in ms]
    B = books([t for tt in toks for t in tt]); time.sleep(0.3)
    if not B:
        continue
    n_ev += 1
    yb = [max([float(x["price"]) for x in B.get(y, {}).get("bids", [])] or [0]) for y, _ in toks]
    fav = max(range(len(ms)), key=lambda i: yb[i])
    for i, (m, (y, n)) in enumerate(zip(ms, toks)):
        xd = (fav - i) if kind == "H" else (i - fav)
        if xd < 2:
            continue
        asks = [(float(x["price"]), float(x["size"])) for x in B.get(n, {}).get("asks", [])]
        if i == 0:
            s = sum(z for p, z in asks if p <= 0.995); low_br[0] += s; low_br[1] += sum(p * z for p, z in asks if p <= 0.995)
            continue
        for k, lim in (("<=0.99", 0.99), ("<=0.995", 0.995), ("<=0.998", 0.998)):
            tot[k][0] += sum(z for p, z in asks if p <= lim); tot[k][1] += sum(p * z for p, z in asks if p <= lim)
        best = min(asks)[0] if asks else None
        BEST[str(best)] = BEST.get(str(best), 0) + 1
        if best is not None and best <= 0.995:
            rows.append((city, kind, loc.strftime("%H:%M"), m["groupItemTitle"], "fav", ms[fav]["groupItemTitle"], round(yb[fav], 3), "NOask", best,
                         round(sum(z for p, z in asks if p <= 0.995))))
print(now.strftime("%Y-%m-%d %H:%M UTC"), "events past cutoff:", n_ev)
for k, v in tot.items():
    print(f"  dead (>=2 from fav, not lowest) NO asks {k}: {v[0]:.0f} sh ${v[1]:.0f}  edge~${v[0] - v[1]:.1f}")
print(f"  lowest-bracket NO asks <=0.995 (excluded): {low_br[0]:.0f} sh ${low_br[1]:.0f}")
print("  best NO ask on dead brackets (count):", sorted(BEST.items()))
for r in rows[:15]:
    print("  ", r)
