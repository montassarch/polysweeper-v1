"""US-sports after-the-end tape, split by token: WINNER token vs LOSER token, BUY (hit an ask) vs SELL (hit a bid).

Reads lab/data/raw/usports_events.json + usports_tape/*.json. dt = seconds after Polymarket's `finished` stamp.
Band = price 0.96-0.995 ("our band"), and 0.99-0.995 ("the 0.99 bots' level").
Outputs per sport: games, fills, shares, per day, share of games with at least one fill in each time window.
"""
import collections, json, statistics, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
ev = {e["id"]: e for e in json.loads((ROOT / "lab/data/raw/usports_events.json").read_text())}


def med(x):
    return round(statistics.median(x), 1) if x else None


rows, games = [], {}
for f in (ROOT / "lab/data/raw/usports_tape").glob("*.json"):
    d = json.loads(f.read_text()); e = ev.get(f.stem)
    if not e or e["slug"] != e["game"]:
        continue
    fm = {}
    for m in e["markets"]:
        try:
            fm[m["cid"]] = ([float(x) for x in json.loads(m["final"])], m["type"])
        except (TypeError, ValueError):
            pass
    games[e["game"]] = (e["sport"], d["finished"])
    for t in d["trades"]:
        if t["conditionId"] not in fm:
            continue
        px, typ = fm[t["conditionId"]]
        if sorted(px) != [0.0, 1.0]:
            continue
        rows.append({"sport": e["sport"], "game": e["game"], "day": time.strftime("%m-%d", time.gmtime(d["finished"])),
                     "dt": t["timestamp"] - d["finished"], "side": t["side"], "p": float(t["price"]), "size": float(t["size"]),
                     "wallet": t["proxyWallet"], "cid": t["conditionId"], "type": typ,
                     "winner": px[t["outcomeIndex"]] == 1.0})
print("rows", len(rows), "games", len(games))
ndays = len({g[1] // 86400 for g in games.values()})
WIN = [(0, 10, "0-10s"), (10, 60, "10-60s"), (60, 300, "1-5min"), (300, 1800, "5-30min"), (1800, 1e9, "30min+")]
for sport in ("MLB", "NFL", "CFB", "NHL", "WNBA", "NBA"):
    gs = [g for g, (s, _) in games.items() if s == sport]
    if not gs:
        continue
    print(f"\n#### {sport}: {len(gs)} games in tape")
    for label, side, winner in (("hit an ASK: BUY winner token", "BUY", True), ("hit a BID: SELL winner token", "SELL", True),
                                ("BUY of the LOSER token (others' errors / mirror)", "BUY", False)):
        for bname, lo, hi in (("0.96-0.995", 0.96, 0.995), ("0.99-0.995", 0.99, 0.995)):
            rs = [r for r in rows if r["sport"] == sport and r["dt"] >= 0 and r["side"] == side and r["winner"] == winner and lo <= r["p"] < hi]
            if not rs:
                print(f"  {label:50} {bname}: none"); continue
            per = {w: len({r["game"] for r in rs if a <= r["dt"] < b}) for a, b, w in WIN}
            print(f"  {label:50} {bname}: fills {len(rs):4} shares {sum(r['size'] for r in rs):8.0f} games {len({r['game'] for r in rs}):3}/{len(gs)}"
                  f"  games-with-fill by window {per}  median size {med([r['size'] for r in rs])}")

print("\n=== AFTER-END ASK-HITS on the WINNER at 0.96-0.995, all US sports: by market type, wallet, timing ===")
ah = [r for r in rows if r["dt"] >= 0 and r["side"] == "BUY" and r["winner"] and 0.96 <= r["p"] < 0.995]
print("fills", len(ah), "shares", round(sum(r["size"] for r in ah)), "games", len({r["game"] for r in ah}), "of", len(games))
for t, n in collections.Counter(r["type"] for r in ah).most_common(10):
    rs = [r for r in ah if r["type"] == t]
    print(f"  type {str(t):28} fills {n:3} shares {sum(r['size'] for r in rs):7.0f} median size {med([r['size'] for r in rs])}")
print(" wallets:")
for w, n in collections.Counter(r["wallet"] for r in ah).most_common(8):
    rs = [r for r in ah if r["wallet"] == w]
    print(f"  {w[:10]} fills {n:3} shares {sum(r['size'] for r in rs):7.0f}")
dts = sorted(r["dt"] for r in ah)
print(" dt percentiles (s):", [dts[int(q * (len(dts) - 1))] for q in (0, .1, .25, .5, .75, .9, 1)])
sz = sorted(r["size"] for r in ah)
print(" size percentiles:", [sz[int(q * (len(sz) - 1))] for q in (0, .1, .25, .5, .75, .9, 1)])
print(" per day (ask-hits, fills/shares):")
for d, n in sorted(collections.Counter(r["day"] for r in ah).items()):
    print("   ", d, n, round(sum(r["size"] for r in ah if r["day"] == d)))
print(" 0.99-0.995 only, per-day average over", ndays, "days:", round(len([r for r in ah if r["p"] >= 0.99]) / ndays, 1), "fills/day")
