"""Who takes the in-band (0.96-0.995) asks within -120..+120 s of the OFFICIAL end in US sports (public tape, all wallets)?
Per wallet: fills, shares, median size, median seconds from the official end, fills on the LOSING token, PnL on those fills (1 - price per winning share, -price per losing share, no fees)."""
import collections, json, statistics, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
ev = {e["id"]: e for e in json.loads((ROOT / "lab/data/raw/usports_events.json").read_text())}
end = {}
for f in ("espn_official_end_cache.json", "mlb_official_end_cache.json"):
    for k, v in json.loads((ROOT / "lab/data" / "raw" / f).read_text()).items():
        if v:
            end[k] = v["end"]
rows = []
games = set()
for f in (ROOT / "lab/data/raw/usports_tape").glob("*.json"):
    e = ev.get(f.stem)
    if not e or e["slug"] != e["game"] or e["game"] not in end:
        continue
    games.add(e["game"])
    d = json.loads(f.read_text())
    fm = {}
    for m in e["markets"]:
        try:
            px = [float(x) for x in json.loads(m["final"])]
        except (TypeError, ValueError):
            continue
        if sorted(px) == [0.0, 1.0]:
            fm[m["cid"]] = px
    for t in d["trades"]:
        px = fm.get(t["conditionId"])
        dt = t["timestamp"] - end[e["game"]]
        if not px or t["side"] != "BUY" or not (-120 <= dt < 120) or not (0.96 <= float(t["price"]) < 0.995):
            continue
        win = px[t["outcomeIndex"]] == 1.0
        p, s = float(t["price"]), float(t["size"])
        rows.append({"w": t["proxyWallet"], "p": p, "s": s, "dt": dt, "win": win, "pnl": s * ((1 - p) if win else -p), "sport": e["sport"]})
print("games", len(games), "fills", len(rows), "wallets", len({r["w"] for r in rows}))
by = collections.defaultdict(list)
for r in rows:
    by[r["w"]].append(r)
tot_f = len(rows)
print("top wallets by fills (all US sports, -120..+120 s of the official end, price 0.96-0.995):")
cum = 0
for w, rs in sorted(by.items(), key=lambda kv: -len(kv[1]))[:12]:
    cum += len(rs)
    lost = sum(1 for r in rs if not r["win"])
    print(f"  {w[:10]} fills {len(rs):4} shares {sum(r['s'] for r in rs):7.0f} median size {statistics.median(r['s'] for r in rs):6.1f} median dt {statistics.median(r['dt'] for r in rs):6.1f}s  losing-token fills {lost:2}  PnL ${sum(r['pnl'] for r in rs):8.2f}  sports {dict(collections.Counter(r['sport'] for r in rs).most_common(3))}")
print(f"  top-12 share of all fills: {cum/tot_f:.0%}; wallets with >=5 fills: {sum(1 for rs in by.values() if len(rs)>=5)}; wallets with <5 fills: {sum(1 for rs in by.values() if len(rs)<5)}")
small = [rs for rs in by.values() if statistics.median(r['s'] for r in rs) <= 10 and len(rs) >= 5]
print(f"  'scrap-size' wallets (median size <= 10 sh, >= 5 fills): {len(small)}; their fills {sum(len(rs) for rs in small)}, losing-token fills {sum(1 for rs in small for r in rs if not r['win'])}, PnL ${sum(r['pnl'] for rs in small for r in rs):.2f}")
allp = sum(r["pnl"] for r in rows)
print(f"  ALL fills PnL ${allp:.2f} on {sum(r['s'] for r in rows):.0f} shares; loser-token fills {sum(1 for r in rows if not r['win'])} ({sum(r['s'] for r in rows if not r['win']):.0f} sh, ${sum(r['pnl'] for r in rows if not r['win']):.2f})")
print(" by sport: " + ", ".join(f"{s}: fills {len(x)} pnl ${sum(r['pnl'] for r in x):.0f} lost-token {sum(1 for r in x if not r['win'])}" for s, x in ((s, [r for r in rows if r['sport']==s]) for s in sorted({r['sport'] for r in rows}))))

top = []
for w, rs in sorted(by.items(), key=lambda kv: -len(kv[1]))[:15]:
    top.append({"wallet": w[:10], "fills": len(rs), "shares": round(sum(r["s"] for r in rs)), "median_size": statistics.median(r["s"] for r in rs),
                "median_s_from_end": statistics.median(r["dt"] for r in rs), "losing_token_fills": sum(1 for r in rs if not r["win"]), "pnl_no_fees": round(sum(r["pnl"] for r in rs), 2)})
(ROOT / "lab/results" / f"{time.strftime('%Y-%m-%d')}-usports-wallets-near-end.json").write_text(json.dumps({"games": len(games), "fills": len(rows), "wallets": len(by), "gross_pnl": round(allp, 2), "top": top}, indent=1))
