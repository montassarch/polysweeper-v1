"""Out-of-sample check of the row-9 card test (stock/ETF far-strike sweep) on days AFTER the 8 Oct study (ps-researcher, 2026-10-10).

Reuses lab/stock_ladder_tape.py (same Yahoo stand-in, same z rule). Needs the raw tape of the new days:
  python3 lab/stock_ladder_pull.py 2026-10-06 2026-10-10 ; python3 lab/stock_ladder_yahoo.py ; python3 lab/stock_ladder_yahoo.py daily
Then: python3 lab/stock_ladder_oos.py   -> prints a table per settlement day, writes lab/results/2026-10-10-stock-ladder-oos.json

Card test (R-2026-10-08): public BUY trades of 5+ shares at 0.98-0.995 in the last 90 min before the 20:00 UTC close of the final
day, on the side the stock price makes certain ("right side"), strike 6+ normal moves away (z). A "loser" = that token paid 0.
Read-only; no orders.
"""
import collections, json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lab"))
import stock_ladder_tape as T  # noqa: E402


def stat(sel):
    losers = [r for r in sel if not r["won"]]
    return {"fills": len(sel), "markets": len({(r["slug"], r["g"]) for r in sel}), "shares": round(sum(r["sz"] for r in sel)),
            "wallets": len({r["w"] for r in sel}), "losers": len(losers),
            "avg_price": round(sum(r["p"] for r in sel) / len(sel), 4) if sel else None}


def main():
    rows, valid, valid_mis = T.main()
    band = lambda r: 0.98 <= r["p"] <= 0.995
    out = {"by_day": {}}
    days = sorted({r["end"] for r in rows})
    print("day       | last-90 band 0.98-0.995 5+sh, right side: z>=6 | z 4-6 | z 2-4 | z<2 | wrong-side (trap) buys")
    for d in days:
        sel = [r for r in rows if r["end"] == d and band(r) and 0 <= r["min_to_end"] <= 90 and r["sz"] >= 5]
        right = [r for r in sel if r["right"]]
        wrong = [r for r in sel if not r["right"]]
        tab = {"z>=6": stat([r for r in right if r["z"] >= 6]), "z4-6": stat([r for r in right if 4 <= r["z"] < 6]),
               "z2-4": stat([r for r in right if 2 <= r["z"] < 4]), "z<2": stat([r for r in right if r["z"] < 2]),
               "wrong_side": stat(wrong)}
        # also the whole final day / any time, band, 5+ shares, right side z>=6 (the supply is not only in the last hour)
        anyt = [r for r in rows if r["end"] == d and band(r) and not r["post"] and r["sz"] >= 5 and r["right"] and r["z"] >= 6]
        tab["z>=6_any_time_before_close"] = stat(anyt)
        out["by_day"][d] = tab
        print(d, "|", *[f"{k}: {v['fills']} fills/{v['markets']} mkts/{v['losers']} lost" for k, v in tab.items()], sep="  ")
    # families on the new out-of-sample days (8 and 9 Oct)
    oos = [r for r in rows if r["end"] in ("2026-10-08", "2026-10-09") and band(r) and 0 <= r["min_to_end"] <= 90 and r["sz"] >= 5 and r["right"] and r["z"] >= 6]
    out["oos_8_9_oct_z6"] = stat(oos)
    out["oos_by_family"] = {f: stat([r for r in oos if r["fam"] == f]) for f in sorted({r["fam"] for r in oos})}
    out["oos_by_ticker"] = {f: stat([r for r in oos if r["tk"] == f]) for f in sorted({r["tk"] for r in oos})}
    # distance floor variant: z>=6 AND at least 1% away
    out["oos_z6_dist1pct"] = stat([r for r in oos if r["dist"] >= 1.0])
    # right-side losers anywhere in the cheap band on these days (any z), for a closer look
    out["right_side_losers_any_z"] = [dict(slug=r["slug"], g=r["g"], p=r["p"], sz=r["sz"], z=round(r["z"], 2), dist=round(r["dist"], 3),
                                          min_to_end=round(r["min_to_end"], 1), end=r["end"], fam=r["fam"])
                                      for r in rows if r["end"] in ("2026-10-08", "2026-10-09") and band(r) and not r["post"] and r["right"] and not r["won"]][:60]
    # trap buys (the wrong side) in the band: how often does the market sell "right looking" but wrong asks?
    out["yahoo_vs_settlement"] = {fam: {f"{b}|{'ok' if ok else 'MISMATCH'}": n for (b, ok), n in sorted(c.items())} for fam, c in valid.items()}
    out["yahoo_mismatches"] = valid_mis[:30]
    (ROOT / "lab/results/2026-10-10-stock-ladder-oos.json").write_text(json.dumps(out, indent=1))
    print("oos 8-9 Oct z>=6:", out["oos_by_family"] and out["oos_8_9_oct_z6"])
    print("by family:", {k: (v["fills"], v["losers"]) for k, v in out["oos_by_family"].items()})
    print("z>=6 and >=1% away:", out["oos_z6_dist1pct"])
    print("right-side losers in band (any z), 8-9 Oct:", len(out["right_side_losers_any_z"]))


if __name__ == "__main__":
    main()
