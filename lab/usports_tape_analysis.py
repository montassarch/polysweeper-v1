"""After-the-end supply in US sports from the public tape (all wallets), per sport.

Reads lab/data/raw/usports_events.json + lab/data/raw/usports_tape/*.json (from usports_tape.py).
dt = trade time minus Polymarket's `finished` stamp of the game (what the Sports WebSocket shows as final).
"""
import collections, json, statistics, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
ev = {e["id"]: e for e in json.loads((ROOT / "lab/data/raw/usports_events.json").read_text())}
FAM = sys.argv[1] if len(sys.argv) > 1 else "main"


def final_map(e):
    out = {}
    for m in e["markets"]:
        try:
            px = [float(x) for x in json.loads(m["final"])]
        except (TypeError, ValueError):
            continue
        out[m["cid"]] = (px, m["type"])
    return out


def med(x):
    return round(statistics.median(x), 1) if x else None


def pct(x, q):
    x = sorted(x)
    return round(x[min(len(x) - 1, int(q * len(x)))], 1) if x else None


rows = []
for f in (ROOT / "lab/data/raw/usports_tape").glob("*.json"):
    d = json.loads(f.read_text())
    e = ev.get(f.stem)
    if not e or (FAM == "main" and e["slug"] != e["game"]):
        continue
    fm = final_map(e)
    for t in d["trades"]:
        fin = fm.get(t["conditionId"])
        if not fin:
            continue
        px, typ = fin
        settled = sorted(px) == [0.0, 1.0]
        idx = t["outcomeIndex"]
        rows.append({"sport": e["sport"], "game": e["game"], "day": time.strftime("%Y-%m-%d", time.gmtime(d["finished"])),
                     "dt": t["timestamp"] - d["finished"], "side": t["side"], "p": float(t["price"]), "size": float(t["size"]),
                     "wallet": t["proxyWallet"], "cid": t["conditionId"], "type": typ, "settled": settled,
                     "won": settled and px[idx] == 1.0, "lost": settled and px[idx] == 0.0})
print("tape rows:", len(rows), "games:", len({r["game"] for r in rows}))
days = sorted({r["day"] for r in rows})
ngames = collections.Counter()
for g, s in {(r["game"], r["sport"]) for r in rows}:
    ngames[s] += 1
print("games per sport in tape:", dict(ngames))
BANDS = [("0.96-0.995", 0.96, 0.995), ("0.995-0.999", 0.995, 0.9995), ("0.999+", 0.9995, 1.01)]
for sport in sorted(ngames):
    print(f"\n######## {sport}  ({ngames[sport]} games)")
    after = [r for r in rows if r["sport"] == sport and r["dt"] >= 0]
    before = [r for r in rows if r["sport"] == sport and -60 <= r["dt"] < 0]
    for side in ("BUY", "SELL"):
        for name, lo, hi in BANDS:
            rs = [r for r in after if r["side"] == side and lo <= r["p"] < hi]
            if not rs:
                continue
            games = {r["game"] for r in rs}; mk = {(r["game"], r["cid"]) for r in rs}
            print(f"  after end, {side:4} {name:12} fills {len(rs):5} shares {sum(r['size'] for r in rs):9.0f} games {len(games):3} markets {len(mk):4} "
                  f"median size {med([r['size'] for r in rs])} dt median {med([r['dt'] for r in rs])}s p10 {pct([r['dt'] for r in rs], .1)} p90 {pct([r['dt'] for r in rs], .9)}"
                  f"  lost {sum(r['lost'] for r in rs) if side=='BUY' else '-'}")
    rs = [r for r in before if r["side"] == "BUY" and 0.96 <= r["p"] < 0.995]
    if rs:
        print(f"  LAST 60 s BEFORE the stamp, BUY 0.96-0.995: fills {len(rs)} shares {sum(r['size'] for r in rs):.0f} lost {sum(r['lost'] for r in rs)}")

if len(sys.argv) > 2 and sys.argv[2] == "losses":
    print("\n=== after-end BUYS 0.96-0.995 that LOST ===")
    for r in sorted([r for r in rows if r["dt"] >= 0 and r["side"] == "BUY" and 0.96 <= r["p"] < 0.995 and r["lost"]], key=lambda r: (r["game"], r["dt"])):
        print(f"  {r['sport']:5} {r['game']:36} {str(r['type']):14} dt {r['dt']:7.0f}s p {r['p']} size {r['size']:7.1f} wallet {r['wallet'][:8]} cid {r['cid'][:10]}")
