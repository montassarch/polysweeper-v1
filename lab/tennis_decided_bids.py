"""Tennis (ATP/WTA): how much cheap supply do resting buy bids see in the last minutes before Polymarket's "finished" stamp, and how
often does a fill land on the loser?  (spin-off of the row-4 "decided-state bid" study, 2026-10-09; read-only, public data.)

Why tennis: ~40 matches a day on Polymarket (US games with cheap decided-state supply: ~5-10 a day). The laptop's feed race
(lab/results/feeds-end-race-summary.json) says free live-score sites report "finished" a median ~160 s (p10 -3 s, p90 350 s) BEFORE
Polymarket's own "ended" flag, so the last ~2-3 minutes before the stamp are mostly AFTER the real end of the match.
  python3 lab/tennis_decided_bids.py pull [days=60]     events + public taker trades [stamp-30min, stamp+15min], price >= 0.9
  python3 lab/tennis_decided_bids.py report             table by time before the stamp and price band -> lab/results/2026-10-09-tennis-decided-bids.json
A "fill" = taker SELL into a resting buy bid. Queue position is NOT modelled.  Raw files: lab/data/raw/tennis_* (git-ignored).
"""
import collections, json, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "lab"))
from polysweeper.collector import get_json  # noqa: E402

DATA = "https://data-api.polymarket.com"
EVENTS = ROOT / "lab/data/raw/tennis_events.json"
TAPE = ROOT / "lab/data/raw/tennis_tape"
TAPE.mkdir(parents=True, exist_ok=True)


def games():
    out = []
    for e in json.loads(EVENTS.read_text()):
        if e["slug"] != e["game"] or not e.get("finished"):
            continue
        ms = [m for m in e["markets"] if m.get("type") == "moneyline"]
        if len(ms) != 1:
            continue
        try:
            px = [float(x) for x in json.loads(ms[0]["final"])]
        except Exception:
            continue
        if sorted(px) != [0.0, 1.0]:
            continue
        out.append({"game": e["game"], "sport": e["sport"], "cid": ms[0]["cid"], "fin": e["finished"], "start": e.get("start"), "px": px,
                    "score": e.get("score")})
    return out


def pull_one(g):
    f = TAPE / f"{g['game']}.json"
    if f.exists():
        return 0
    rows, off, ok = [], 0, False
    while off <= 10000:
        page = get_json(f"{DATA}/trades?market={g['cid']}&limit=500&offset={off}")
        if not isinstance(page, list) or not page:
            ok = True
            break
        rows += page
        if min(t["timestamp"] for t in page) < g["fin"] - 1800 - 600 or len(page) < 500:
            ok = True
            break
        off += 500
    keep = [[t["timestamp"], t["side"], float(t["price"]), float(t["size"]), t["outcomeIndex"], (t.get("proxyWallet") or "")[:10]]
            for t in rows if g["fin"] - 1800 <= t["timestamp"] <= g["fin"] + 900 and float(t["price"]) >= 0.9]
    f.write_text(json.dumps({"ok": ok, "trades": keep}))
    return len(rows)


def pull(days):
    import usports_events as U
    U.SERIES = {"ATP": 10365, "WTA": 10366}
    U.OUT = EVENTS
    if not EVENTS.exists():
        U.main(days)
    gs = games()
    print("matches with one resolved moneyline + stamp:", len(gs), dict(collections.Counter(g["sport"] for g in gs)), flush=True)
    todo = [g for g in gs if not (TAPE / f"{g['game']}.json").exists()]
    n = 0
    with ThreadPoolExecutor(6) as pool:
        for _ in pool.map(pull_one, todo):
            n += 1
            if n % 200 == 0:
                print("tape", n, "of", len(todo), flush=True)
    print("tape done", flush=True)


BINS = [(0, 60), (60, 120), (120, 180), (180, 300), (300, 600), (600, 1800)]
BANDS = [(0.95, 0.96), (0.96, 0.97), (0.97, 0.98), (0.98, 0.99), (0.99, 0.995), (0.995, 0.9995)]


def report():
    gs = games()
    fills = []
    n_games = 0
    for g in gs:
        f = TAPE / f"{g['game']}.json"
        if not f.exists():
            continue
        d = json.loads(f.read_text())
        if not d["ok"]:
            continue
        n_games += 1
        for t in d["trades"]:
            if t[1] == "SELL" and 0.95 <= t[2] < 0.9995 and t[0] < g["fin"]:
                fills.append({"game": g["game"], "sb": g["fin"] - t[0], "price": t[2], "shares": t[3], "loser": int(g["px"][t[4]] != 1.0), "w": t[5]})

    def stat(sel):
        gs_ = {x["game"] for x in sel}
        return {"fills": len(sel), "games": len(gs_), "loser_fills": sum(x["loser"] for x in sel),
                "loser_games": len({x["game"] for x in sel if x["loser"]}), "shares": round(sum(x["shares"] for x in sel)),
                "median_shares": (sorted(x["shares"] for x in sel)[len(sel) // 2] if sel else 0),
                "games_ge5": len({x["game"] for x in sel if x["shares"] >= 5})}
    out = {"matches_with_complete_tape": n_games, "fills_ge_0.95": len(fills), "by_time_all_prices_0.95_0.9995": {}, "by_time_cheap_0.96_0.995": {},
           "by_time_0.98_0.995": {}, "bands_last_180s": {}, "bands_180_600s": {}}
    for lo, hi in BINS:
        key = f"{lo}-{hi}s"
        sel = [x for x in fills if lo <= x["sb"] < hi]
        out["by_time_all_prices_0.95_0.9995"][key] = stat(sel)
        out["by_time_cheap_0.96_0.995"][key] = stat([x for x in sel if 0.96 <= x["price"] < 0.995])
        out["by_time_0.98_0.995"][key] = stat([x for x in sel if 0.98 <= x["price"] < 0.995])
    for name, (a, b) in (("bands_last_180s", (0, 180)), ("bands_180_600s", (180, 600))):
        for lo, hi in BANDS:
            out[name][f"{lo}-{hi}"] = stat([x for x in fills if a <= x["sb"] < b and lo <= x["price"] < hi])
    # wallets: concentration of the SELLers in the last 180 s, cheap band
    w = collections.Counter(x["w"] for x in fills if x["sb"] < 180 and 0.96 <= x["price"] < 0.995)
    out["sellers_last180s_cheap"] = {"distinct_wallets": len(w), "top3_share": round(sum(v for _, v in w.most_common(3)) / max(1, sum(w.values())), 3)}
    (ROOT / "lab/results/2026-10-09-tennis-decided-bids.json").write_text(json.dumps(out, indent=1))
    for k in ("by_time_all_prices_0.95_0.9995", "by_time_cheap_0.96_0.995", "by_time_0.98_0.995"):
        print("\n==", k)
        for kk, v in out[k].items():
            print(f"  {kk:10s} fills {v['fills']:5d} matches {v['games']:4d} loserF {v['loser_fills']:3d} loserM {v['loser_games']:3d} shares {v['shares']:7d} median {v['median_shares']:6.1f} matches>=5sh {v['games_ge5']:4d}")
    for k in ("bands_last_180s", "bands_180_600s"):
        print("\n==", k)
        for kk, v in out[k].items():
            print(f"  {kk:14s} fills {v['fills']:5d} matches {v['games']:4d} loserF {v['loser_fills']:3d} loserM {v['loser_games']:3d}")
    print(out["matches_with_complete_tape"], "matches;", out["sellers_last180s_cheap"])


if __name__ == "__main__":
    if sys.argv[1] == "pull":
        pull(int(sys.argv[2]) if len(sys.argv) > 2 else 60)
    else:
        report()
