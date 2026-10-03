"""Read-only analysis of cached daily-temperature taker trades (from weather_fetch.py).
'NO-side buy' = taker BUY of No at 0.95-0.998, or taker SELL of Yes at 0.002-0.05 (same position, NO price = 1-p).
Groups by distance to the final winner (dead side = below winner for Highest, above winner for Lowest),
bracket type, market kind, station-local hour. Also an EX-ANTE test: bracket >=2 on the dead side of the
price-implied favourite at trade time (last trade prices), which is what a bot could actually know.
Writes lab/results/<date>-weather-deadbucket.json and prints a summary."""
import json, os, sys, glob, datetime as dt
from collections import defaultdict
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from weather_cities import TZ, city_kind

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "data", "raw", "weather")
evs = {e["id"]: e for e in json.load(open(os.path.join(RAW, "events_closed.json")))}


def hb(h):  # local-hour bucket relative to 00:00 of the event date
    for lim, name in ((0, "a<day"), (6, "b00-06"), (10, "c06-10"), (12, "d10-12"), (14, "e12-14"), (16, "f14-16"),
                      (17, "g16-17"), (18, "h17-18"), (20, "i18-20"), (22, "j20-22"), (24, "k22-24")):
        if h < lim:
            return name
    return "l>=24(after day)"


def new():
    return {"n": 0, "win": 0, "loss": 0, "sh": 0.0, "cost": 0.0, "pnl": 0.0, "loss_sh": 0.0}


def add(g, sh, p, fee, won):
    g["n"] += 1; g["sh"] += sh; g["cost"] += sh * p
    if won:
        g["win"] += 1; g["pnl"] += sh * (1 - p) - fee
    else:
        g["loss"] += 1; g["pnl"] -= sh * p + fee; g["loss_sh"] += sh


by_dist = defaultdict(new); by_type = defaultdict(new); by_hour_loss = defaultdict(new)
exante = defaultdict(new); dead_hour = defaultdict(lambda: {"sh": 0.0, "cost": 0.0, "edge": 0.0, "n": 0, "pmin": 1.0,
                                                           "sh_le_99": 0.0, "sh_le_995": 0.0, "sh_gt_998": 0.0, "n_gt_998": 0})
daily = defaultdict(lambda: {"sh": 0.0, "cost": 0.0, "edge": 0.0, "n": 0, "ev": set()})
daily_L = defaultdict(lambda: {"sh": 0.0, "cost": 0.0, "edge": 0.0, "n": 0})
losers = []; exante_losers = []
nev = 0; days = set()
for f in sorted(glob.glob(os.path.join(RAW, "trades", "*.json"))):
    e = evs.get(os.path.basename(f)[:-5])
    if not e:
        continue
    city, kind = city_kind(e["title"])
    tz = ZoneInfo(TZ[city])
    ms = sorted(e["markets"], key=lambda m: int(m["groupItemThreshold"]))
    nb = len(ms)
    w = [i for i, m in enumerate(ms) if json.loads(m["outcomePrices"])[0] == "1"][0]
    idx = {m["conditionId"]: i for i, m in enumerate(ms)}
    rate = {m["conditionId"]: (m.get("feeSchedule") or {}).get("rate") or 0 for m in ms}
    day0 = dt.datetime.fromisoformat(e["eventDate"]).replace(tzinfo=tz)
    nev += 1; days.add(e["eventDate"])
    last = [None] * nb  # last YES price per bracket (from trade stream)
    for t in sorted(json.load(open(f)), key=lambda t: t["timestamp"]):
        i = idx.get(t["conditionId"])
        if i is None:
            continue
        p = float(t["price"]); sh = float(t["size"])
        yes = p if t["outcome"] == "Yes" else 1 - p
        if t["outcome"] == "No" and t["side"] == "BUY" and p >= 0.95:
            pany = p
        elif t["outcome"] == "Yes" and t["side"] == "SELL" and p <= 0.05:
            pany = 1 - p
        else:
            pany = None
        pno = pany if (pany is not None and pany <= 0.998) else None
        if pany is not None and pany > 0.998 and kind == "H" and ((w - i) >= 2):
            h9 = (dt.datetime.fromtimestamp(t["timestamp"], tz) - day0).total_seconds() / 3600
            d = dead_hour[hb(h9)]; d["sh_gt_998"] += float(t["size"]); d["n_gt_998"] += 1
        if pno is not None:
            won = i != w
            fee = sh * rate[t["conditionId"]] * pno * (1 - pno)
            dd = (w - i) if kind == "H" else (i - w)  # >0: dead side of the final winner
            ddk = str(max(-3, min(3, dd))).replace("3", "3+") if abs(dd) >= 3 else str(dd)
            typ = "lowest" if i == 0 else ("highest" if i == nb - 1 else "middle")
            loc = dt.datetime.fromtimestamp(t["timestamp"], tz)
            h = (loc - day0).total_seconds() / 3600
            add(by_dist[f"{kind} dd={ddk}"], sh, pno, fee, won)
            add(by_type[f"{kind} {typ}"], sh, pno, fee, won)
            if not won:
                add(by_hour_loss[f"{kind} {hb(h)}"], sh, pno, fee, won)
                losers.append({"date": e["eventDate"], "city": city, "kind": kind, "bracket": ms[i]["groupItemTitle"],
                               "type": typ, "local": loc.strftime("%m-%d %H:%M"), "h": round(h, 2), "p_no": round(pno, 3),
                               "shares": round(sh, 1), "via": "NObuy" if t["outcome"] == "No" else "YESsell"})
            # ex-ante: favourite = bracket with highest last YES price (needs >=3 brackets priced)
            known = [(last[j], j) for j in range(nb) if last[j] is not None]
            if len(known) >= 3:
                fav = max(known)[1]
                xd = (fav - i) if kind == "H" else (i - fav)
                late = (h >= 17) if kind == "H" else (h >= 10)
                key = f"{kind} {'late' if late else 'early'} xd={'2+' if xd >= 2 else xd if xd >= -1 else '<=-2'}"
                add(exante[key], sh, pno, fee, won)
                if not won and xd >= 2:
                    exante_losers.append({"date": e["eventDate"], "city": city, "kind": kind, "bracket": ms[i]["groupItemTitle"],
                                          "fav_then": ms[fav]["groupItemTitle"], "fav_yes": round(max(known)[0], 3),
                                          "local": loc.strftime("%m-%d %H:%M"), "p_no": round(pno, 3), "shares": round(sh, 1)})
            # timing proxy: Highest market, >=2 below the FINAL winner
            if kind == "H" and dd >= 2:
                d = dead_hour[hb(h)]
                d["n"] += 1; d["sh"] += sh; d["cost"] += sh * pno; d["edge"] += sh * (1 - pno) - fee; d["pmin"] = min(d["pmin"], pno)
                d["sh_le_99"] += sh if pno <= 0.99 else 0; d["sh_le_995"] += sh if pno <= 0.995 else 0
                if 17 <= h and pno <= 0.995:
                    y = daily[e["eventDate"]]; y["n"] += 1; y["sh"] += sh; y["cost"] += sh * pno; y["edge"] += sh * (1 - pno) - fee; y["ev"].add(city)
            if kind == "L" and dd >= 2 and 10 <= h and pno <= 0.995:
                y = daily_L[e["eventDate"]]; y["n"] += 1; y["sh"] += sh; y["cost"] += sh * pno; y["edge"] += sh * (1 - pno) - fee
        last[i] = yes


def rnd(d):
    return {k: (round(v, 2) if isinstance(v, float) else (len(v) if isinstance(v, set) else v)) for k, v in d.items()}


out = {"events": nev, "days": sorted(days),
       "by_distance": {k: rnd(v) for k, v in sorted(by_dist.items())},
       "by_type": {k: rnd(v) for k, v in sorted(by_type.items())},
       "losses_by_local_hour": {k: rnd(v) for k, v in sorted(by_hour_loss.items())},
       "exante": {k: rnd(v) for k, v in sorted(exante.items())},
       "exante_losers_first50": exante_losers[:50],
       "dead_H_dd2plus_by_hour": {k: rnd(v) for k, v in sorted(dead_hour.items())},
       "daily_H_dd2plus_after17_le995": {k: rnd(v) for k, v in sorted(daily.items())},
       "daily_L_dd2plus_after10_le995": {k: rnd(v) for k, v in sorted(daily_L.items())},
       "losers_by_bracket": None}
agg = defaultdict(lambda: {"n": 0, "shares": 0.0, "p_min": 1.0, "first": "99", "last": ""})
for x in losers:
    a = agg[f'{x["date"]} {x["city"]} {x["kind"]} {x["bracket"]} ({x["type"]})']
    a["n"] += 1; a["shares"] = round(a["shares"] + x["shares"], 1); a["p_min"] = min(a["p_min"], x["p_no"])
    a["first"] = min(a["first"], x["local"]); a["last"] = max(a["last"], x["local"])
out["losers_by_bracket"] = dict(sorted(agg.items()))
json.dump(sorted(losers, key=lambda x: (x["date"], x["city"])), open(os.path.join(RAW, "losers_all.json"), "w"))
dst = os.path.join(HERE, "results", f"{dt.date.today().isoformat()}-weather-deadbucket.json")
json.dump(out, open(dst, "w"), indent=1)
print("events", nev, "days", len(days), "->", dst)
for sec in ("by_distance", "by_type", "losses_by_local_hour", "exante", "dead_H_dd2plus_by_hour",
            "daily_H_dd2plus_after17_le995", "daily_L_dd2plus_after10_le995"):
    print("==", sec)
    for k, v in out[sec].items():
        print(" ", k, v)
print("== exante losers", len(exante_losers))
for x in exante_losers[:15]:
    print(" ", x)
print("== losers", len(losers), "shares", round(sum(x["shares"] for x in losers)))
