import json, sys, collections
for f in sys.argv[1:]:
    d = json.load(open(f)); rows = d["rows"]
    print("==", f, "markets", d["n_markets"], "studied", len(rows), "disputed", len(d["disputed"]))
    by = collections.defaultdict(list)
    for r in rows: by[(r["tag"], r["live"])].append(r)
    for k, v in sorted(by.items(), key=lambda x: -len(x[1])):
        n = len(v); wb = [r for r in v if r["n_band"] > 0]
        sh = sum(r["band_shares"] for r in v); pr = sum(r["band_usd_profit"] for r in v)
        lose = sum(1 for r in v if r["loser_buys_window_over_0.01"] > 0)
        cheap = sum(1 for r in v if r["min_wp_window"] < 0.985)
        print(f"{k}: n={n} with_band_trades={len(wb)} band_shares={sh} gross_profit=${pr:.2f} mkts_with_winner_trade<0.985_in_window={cheap} window_trades_total={sum(r['n_window'] for r in v)}")
    ex = sorted(rows, key=lambda r: -r["band_usd_profit"])[:6]
    for r in ex: print("  ", r["tag"], r["q"][:60], r["band_shares"], r["band_usd_profit"], r["min_wp_window"], r["band_minutes_after_prop"][:5])
    lows = [r for r in rows if r["min_wp_window"] < 0.9]
    for r in lows[:6]: print("  LOW", r["tag"], r["q"][:60], r["min_wp_window"], r["n_window"])
