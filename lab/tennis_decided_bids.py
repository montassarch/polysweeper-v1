"""Tennis (ATP/WTA): how much cheap supply do resting buy bids see in the last minutes before Polymarket's "finished" stamp, and how
often does a fill land on the loser?  (spin-off of the row-4 "decided-state bid" study, 2026-10-09; read-only, public data.)

Why tennis: ~40 matches a day on Polymarket (US games with cheap decided-state supply: ~5-10 a day). The laptop's feed race
(lab/results/feeds-end-race-summary.json) says free live-score sites report "finished" a median ~160 s (p10 -3 s, p90 350 s) BEFORE
Polymarket's own "ended" flag, so the last ~2-3 minutes before the stamp are mostly AFTER the real end of the match.
  python3 lab/tennis_decided_bids.py pull [days=60]     events + public taker trades [stamp-30min, stamp+15min], price >= 0.9
  python3 lab/tennis_decided_bids.py report             table by time before the stamp and price band -> lab/results/2026-10-09-tennis-decided-bids.json
  python3 lab/tennis_decided_bids.py pegup              price-priority model: a 5-share bid at B joined T seconds before the stamp -> same json
  python3 lab/tennis_decided_bids.py replay joins.jsonl replay live join times ({"slug","join_ts","bid_on"} per line) against the real tape
A "fill" = taker SELL into a resting buy bid. Queue position is NOT modelled.  Raw files: lab/data/raw/tennis_* (git-ignored).
"""
import collections, json, os, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "lab"))
from polysweeper.collector import get_json  # noqa: E402

DATA = "https://data-api.polymarket.com"
# LEAGUE=tennis (default) | cs2 | dota2 | lol | val   -> own event list, tape folder and result file
LEAGUE = os.environ.get("LEAGUE", "tennis")
SERIES = {"tennis": {"ATP": 10365, "WTA": 10366}, "cs2": {"CS2": 10310}, "dota2": {"DOTA2": 10309}, "lol": {"LOL": 10311}, "val": {"VAL": 10369},
          "soccer": {"EPL": 10188, "LAL": 10193, "BUN": 10194, "SEA": 10203, "FL1": 10195, "UCL": 10204, "MLS": 10189, "ELC": 10355, "BRA": 10359}}[LEAGUE]
EVENTS = ROOT / f"lab/data/raw/{LEAGUE}_events.json"
TAPE = ROOT / f"lab/data/raw/{LEAGUE}_tape"
RESULT = ROOT / f"lab/results/2026-10-09-{LEAGUE}-decided-bids.json"
TAPE.mkdir(parents=True, exist_ok=True)


def games():
    out = []
    for e in json.loads(EVENTS.read_text()):
        if e["slug"] != e["game"] or not e.get("finished"):
            continue
        ms = [m for m in e["markets"] if m.get("type") == "moneyline"]
        if LEAGUE != "soccer" and len(ms) != 1:
            continue
        for k, m in enumerate(ms):                       # soccer: three "Will X win / draw?" markets per match, each its own bet
            try:
                px = [float(x) for x in json.loads(m["final"])]
            except Exception:
                continue
            if sorted(px) != [0.0, 1.0]:
                continue
            out.append({"game": e["game"] if LEAGUE != "soccer" else f"{e['game']}-m{k}", "sport": e["sport"], "cid": m["cid"], "fin": e["finished"],
                        "start": e.get("start"), "px": px, "score": e.get("score")})
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
    U.SERIES = SERIES
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
    RESULT.write_text(json.dumps(out, indent=1))
    for k in ("by_time_all_prices_0.95_0.9995", "by_time_cheap_0.96_0.995", "by_time_0.98_0.995"):
        print("\n==", k)
        for kk, v in out[k].items():
            print(f"  {kk:10s} fills {v['fills']:5d} matches {v['games']:4d} loserF {v['loser_fills']:3d} loserM {v['loser_games']:3d} shares {v['shares']:7d} median {v['median_shares']:6.1f} matches>=5sh {v['games_ge5']:4d}")
    for k in ("bands_last_180s", "bands_180_600s"):
        print("\n==", k)
        for kk, v in out[k].items():
            print(f"  {kk:14s} fills {v['fills']:5d} matches {v['games']:4d} loserF {v['loser_fills']:3d} loserM {v['loser_games']:3d}")
    print(out["matches_with_complete_tape"], "matches;", out["sellers_last180s_cheap"])


def pegup(shares=5.0):
    """A bid at price B joined at stamp-T. Every taker SELL arriving later with a print at or below B would have met our bid first
    (price priority; no other bidder above B assumed), so our order fills once such SELLs add up to `shares`.
    Fill price = B (our limit). Counts per match; loser = the filled token did not win. Other pegging bots and our own delay are NOT modelled."""
    gs = games()
    data = []
    for g in gs:
        f = TAPE / f"{g['game']}.json"
        if not f.exists():
            continue
        d = json.loads(f.read_text())
        if d["ok"]:
            data.append((g, d["trades"]))
    out = {"matches": len(data), "model": f"{shares:g}-share bid at B joined T s before the stamp; SELL prints in [0.95, B] after the join fill it first", "cells": {}}
    for B in (0.99, 0.992, 0.995, 0.998):
        for T in (300, 180, 120, 90, 60, 30):
            filled = lost = 0
            fill_wait = []
            for g, tr in data:
                tok_sold = collections.defaultdict(float)
                for t in sorted(tr):
                    if t[1] == "SELL" and 0.95 <= t[2] <= B + 1e-9 and g["fin"] - T <= t[0] < g["fin"]:
                        tok_sold[t[4]] += t[3]
                        if tok_sold[t[4]] >= shares:
                            filled += 1
                            lost += int(g["px"][t[4]] != 1.0)
                            fill_wait.append(t[0] - (g["fin"] - T))
                            break
            fw = sorted(fill_wait)
            out["cells"][f"B={B} T={T}s"] = {"filled_matches": filled, "share_of_matches": round(filled / max(1, len(data)), 3), "loser_fills": lost,
                                             "median_wait_s": (fw[len(fw) // 2] if fw else None), "profit_per_fill_usd": round((1 - B) * shares, 3)}
    prev = json.loads(RESULT.read_text()) if RESULT.exists() else {}
    prev["pegup"] = out
    RESULT.write_text(json.dumps(prev, indent=1))
    print(out["model"], "| matches", out["matches"])
    print(f"{'bid':>7s} {'T':>5s} {'filled':>7s} {'share':>6s} {'losers':>6s} {'med wait':>9s}")
    for k, v in out["cells"].items():
        print(f"{k:>14s} {v['filled_matches']:7d} {v['share_of_matches']:6.3f} {v['loser_fills']:6d} {str(v['median_wait_s']):>9s}")


def replay(path):
    """Replay join times recorded live (JSONL: {"slug": event slug, "join_ts": unix seconds, "bid_on": outcome name or index (optional)}):
    for each match fetch the public tape and report whether a 5-share bid at B would have been filled (price priority, no other bidder above B)
    before Polymarket's finished stamp, and whether it was on the winner. Output lines: lab/results/<LEAGUE>-replay.jsonl"""
    from polysweeper.collector import GAMMA, parse_ts
    outp = ROOT / f"lab/results/{LEAGUE}-replay.jsonl"
    res = []
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        if r.get("slug"):
            ev = get_json(f"{GAMMA}/events?slug={r['slug']}")
        else:                                           # feeds_end_race records carry the Polymarket event id, not the slug
            one = get_json(f"{GAMMA}/events/{r['event']}")
            ev = [one] if isinstance(one, dict) else None
        if not ev:
            continue
        e = ev[0]
        r.setdefault("slug", e.get("slug"))
        ms = [m for m in e.get("markets", []) if m.get("sportsMarketType") == "moneyline"]
        if len(ms) != 1 or not e.get("finishedTimestamp"):
            continue
        m = ms[0]
        px = [float(x) for x in json.loads(m["outcomePrices"])]
        outs = json.loads(m["outcomes"])
        fin = parse_ts(e["finishedTimestamp"])
        bid_on = r.get("bid_on")
        idx = bid_on if isinstance(bid_on, int) else (outs.index(bid_on) if bid_on in outs else (px.index(1.0) if 1.0 in px else None))
        if idx is None:
            continue
        g = {"game": r["slug"], "cid": m["conditionId"], "fin": fin}
        pull_one({**g, "px": px})            # caches the tape
        d = json.loads((TAPE / f"{r['slug']}.json").read_text())
        row = {"slug": r["slug"], "join_ts": r["join_ts"], "stamp": fin, "window_s": fin - r["join_ts"], "token": idx, "won": int(px[idx] == 1.0)}
        for B in (0.99, 0.992, 0.995, 0.998):
            sold = 0.0
            row[f"fill_{B}"] = 0
            for t in sorted(d["trades"]):
                if t[1] == "SELL" and t[4] == idx and 0.95 <= t[2] <= B + 1e-9 and r["join_ts"] <= t[0] < fin:
                    sold += t[3]
                    if sold >= 5.0:
                        row[f"fill_{B}"] = 1
                        row[f"wait_{B}"] = t[0] - r["join_ts"]
                        break
        res.append(row)
    outp.write_text("\n".join(json.dumps(x) for x in res))
    n = len(res)
    for B in (0.99, 0.992, 0.995, 0.998):
        f = sum(x[f"fill_{B}"] for x in res)
        lost = sum(1 for x in res if x[f"fill_{B}"] and not x["won"])
        print(f"B={B}: matches {n} filled {f} ({f / max(1, n):.2f}) filled on a loser {lost}")


if __name__ == "__main__":
    if sys.argv[1] == "pull":
        pull(int(sys.argv[2]) if len(sys.argv) > 2 else 60)
    elif sys.argv[1] == "pegup":
        pegup()
    elif sys.argv[1] == "replay":
        replay(sys.argv[2])
    else:
        report()
