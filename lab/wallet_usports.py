"""Best-wallet copy study (ideas #10/#14), US sports: what the wallet 0x4dDC... buys at 0.95+, when, how big, and whether it lost.

  python3 lab/wallet_usports.py [name=4ddc]       (needs lab/data/raw/wallets/<name>.jsonl from wallet_pull.py)
Times are seconds from Polymarket's own `finishedTimestamp` of the event (what our shadow mode / the Sports WebSocket
would see as 'finished'); negative = before it.
"""
import collections, json, statistics, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lab"))
from mktinfo import lookup  # noqa: E402

NAME = sys.argv[1] if len(sys.argv) > 1 else "4ddc"
BUCKETS = [(-1e12, -1800, "30+ min before"), (-1800, -300, "5-30 min before"), (-300, -60, "1-5 min before"),
           (-60, 0, "last minute before"), (0, 10, "0-10 s after"), (10, 60, "10-60 s after"), (60, 300, "1-5 min after"),
           (300, 1800, "5-30 min after"), (1800, 1e12, "30+ min after")]
GROUP = {"mlb": "MLB", "nfl": "NFL", "cfb": "CFB", "nhl": "NHL", "nba": "NBA", "wnba": "WNBA", "cbb": "NCAAB", "atp": "tennis", "wta": "tennis"}


def group(series):
    s = (series or "").lower()
    for k, v in GROUP.items():
        if s == k or s.startswith(k + "-"):
            return v
    return "soccer" if s.startswith("soccer") or s in ("epl", "ucl", "lal") else (series or "other")


def bucket(sec):
    for lo, hi, name in BUCKETS:
        if lo <= sec < hi:
            return name


def med(x):
    return round(statistics.median(x), 3) if x else None


def main():
    trades = [json.loads(l) for l in (ROOT / f"lab/data/raw/wallets/{NAME}.jsonl").read_text().splitlines() if l.strip()]
    buys = [t for t in trades if t["side"] == "BUY" and float(t["price"]) >= 0.95]
    print("trades", len(trades), "buys>=0.95", len(buys), "span", time.strftime("%Y-%m-%d", time.gmtime(min(t["timestamp"] for t in trades))), "->",
          time.strftime("%Y-%m-%d %H:%M", time.gmtime(max(t["timestamp"] for t in trades))))
    info = lookup([t["conditionId"] for t in buys])
    tkfile = ROOT / f"lab/data/raw/wallets/{NAME}_takeronly.jsonl"
    key = lambda t: (t["transactionHash"], t["asset"], t["side"], round(float(t["size"]), 4), round(float(t["price"]), 4))
    takers = {key(json.loads(l)) for l in tkfile.read_text().splitlines() if l.strip()} if tkfile.exists() else set()
    rows = []
    for t in buys:
        m = info.get(t["conditionId"])
        if not m or not m["final"]:
            continue
        p, size, ts, idx = float(t["price"]), float(t["size"]), int(t["timestamp"]), t["outcomeIndex"]
        pay = m["final"][idx]
        settled = m["closed"] and sorted(m["final"]) in ([0.0, 1.0], [0.5, 0.5])
        rows.append({"grp": group(m["series"]), "type": m["type"], "price": p, "size": size, "ts": ts, "settled": settled,
                     "win": settled and pay == 1.0, "lost": settled and pay == 0.0, "void": settled and pay == 0.5,
                     "dt": (ts - m["finished_ts"]) if m["finished_ts"] else None, "title": t["title"], "slug": t["eventSlug"],
                     "to_start": (ts - m["start_ts"]) if m["start_ts"] else None, "closed_ts": m["closed_ts"],
                     "taker": key(t) in takers})
    print("matched", len(rows), "settled", sum(r["settled"] for r in rows))
    out = {}
    # by group
    print("\nBY SPORT (settled buys)")
    for g, rs in sorted(collections.defaultdict(list, {k: [r for r in rows if r["grp"] == k] for k in {r["grp"] for r in rows}}).items(), key=lambda kv: -len(kv[1])):
        s = [r for r in rs if r["settled"]]
        if not s:
            continue
        dollars = sum(r["price"] * r["size"] for r in s); profit = sum(r["size"] * ((1 if r["win"] else 0.5 if r["void"] else 0) - r["price"]) for r in s)
        print(f"{g:8} buys {len(s):5}  $ {dollars:9.0f}  profit {profit:8.0f}  lost {sum(r['lost'] for r in s):2}  median price {med([r['price'] for r in s])}  median size {med([r['size'] for r in s])}")
        out[g] = {"buys": len(s), "dollars": round(dollars), "profit": round(profit), "lost": sum(r["lost"] for r in s)}
    # US sports by timing
    print("\nUS SPORTS BY TIMING (MLB/NFL/CFB/NHL/NBA), settled buys")
    us = [r for r in rows if r["grp"] in ("MLB", "NFL", "CFB", "NHL", "NBA", "NCAAB", "WNBA") and r["settled"] and r["dt"] is not None]
    for lo, hi, name in BUCKETS:
        rs = [r for r in us if lo <= r["dt"] < hi]
        if rs:
            print(f"{name:20} buys {len(rs):4} shares {sum(r['size'] for r in rs):8.0f} median size {med([r['size'] for r in rs]):7} median price {med([r['price'] for r in rs])}  lost {sum(r['lost'] for r in rs)}")
            out.setdefault("us_timing", {})[name] = {"buys": len(rs), "shares": round(sum(r["size"] for r in rs)), "lost": sum(r["lost"] for r in rs)}
    # after the end, by sport and market type
    print("\nAFTER THE END (dt >= 0), by sport/type")
    aft = [r for r in rows if r["dt"] is not None and r["dt"] >= 0]
    c = collections.Counter((r["grp"], r["type"]) for r in aft)
    for (g, ty), n in c.most_common(12):
        rs = [r for r in aft if r["grp"] == g and r["type"] == ty]
        print(f"  {g:8} {str(ty):16} n={n:3} shares={sum(r['size'] for r in rs):7.0f} median dt={med([r['dt'] for r in rs])} s  median price={med([r['price'] for r in rs])}")
    print("\nAFTER THE END, sorted by seconds (US sports)")
    for r in sorted([r for r in aft if r["grp"] in ("MLB", "NFL", "CFB", "NHL", "NBA")], key=lambda r: r["dt"])[:60]:
        print(f"  +{r['dt']:7.0f}s  {r['grp']:4} {str(r['type']):12} price {r['price']}  size {r['size']:7.1f}  {'LOST' if r['lost'] else 'win ' if r['win'] else '?   '} {r['title'][:50]}")
    (ROOT / f"lab/results/{time.strftime('%Y-%m-%d')}-wallet-usports-{NAME}.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
