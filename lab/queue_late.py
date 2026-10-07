"""Late US-games resting bids (read-only, no orders): would a 5-share buy resting at 0.98 or 0.99 fill, and on which side?

Scoreboard row 4 (34-Fill-Scoreboard): public data shows sellers hitting bids at 0.96-0.99 in the last 30 min of
US games, rarely on the side that then loses. This measures what WE would get: every ~5 s, for every US game in the
live list shadow mode writes (live.json), it logs each side whose best bid is 0.97+: period, score, the shares
already bid at 0.98+ and 0.99+. When the game is done it fetches the public trades and simulates a 5-share buy
joining at 0.98 and at 0.99 the first time the best bid reaches that price:
  filled when taker SELL shares at or above our price after joining pass everything bid at or above it + 5.
Cancels ahead of us are ignored (cautious); new higher bids arriving later are ignored (generous). The report
later checks the real winner on Gamma, so every fill on a side that lost shows up.
Result: lab/data/raw/queue_late/<utc date>.jsonl (local); summary pushed every 3 h to
lab/results/queue-late-summary.json (cloud lab can read it).
  py lab/queue_late.py [hours=72]     measure (stop with Ctrl-C)
  py lab/queue_late.py report         summary (also resolves winners)
"""
import json, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "lab"))
from polysweeper.collector import get_json, post_json, GAMMA, CLOB  # noqa: E402
from queue999 import LIVE, market_meta, trades  # noqa: E402

US = {"mlb", "nhl", "nfl", "cfb", "nba", "wnba"}
LEVELS = (0.98, 0.99)
SHARES = 5
OUT = ROOT / "lab/data/raw/queue_late"
OUT.mkdir(parents=True, exist_ok=True)
SUMMARY = "lab/results/queue-late-summary.json"
recs, done = {}, set()


def poll():
    try:
        live = json.loads(LIVE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001  (rewritten every ~2 s)
        return
    now, tok2 = time.time(), {}
    for m in live.get("markets", []):
        if m.get("league") not in US or m["mid"] in done:
            continue
        mm = market_meta(m["mid"])
        if not mm:
            continue
        r = recs.setdefault(m["mid"], {"polls": {}, "t_end": None, "title": m["title"], "league": m["league"]})
        r["seen"] = now
        if m.get("ended") and r["t_end"] is None:
            r["t_end"] = now
        for t in mm["tokens"]:
            tok2[t] = (m["mid"], bool(m.get("ended")), m.get("period"), m.get("score"))
    if not tok2:
        return
    try:
        books = post_json(f"{CLOB}/books", [{"token_id": t} for t in tok2])
    except Exception as exc:  # noqa: BLE001
        print("books error", exc, flush=True)
        return
    for b in books or []:
        t = b.get("asset_id")
        if t not in tok2:
            continue
        bids = [(float(x["price"]), float(x["size"])) for x in b.get("bids", [])]
        best = max((p for p, _ in bids), default=None)
        if best is None or best < 0.97:
            continue
        mid, ended, period, score = tok2[t]
        q = [round(sum(s for p, s in bids if p >= lv - 1e-9), 1) for lv in LEVELS]
        recs[mid]["polls"].setdefault(t, []).append([round(now, 1), ended, period, score, best] + q)


def simulate(polls, sells, lv, qi):
    first = next((p for p in polls if p[4] >= lv - 1e-9), None)
    if not first:
        return None
    need, got = first[5 + qi] + SHARES, 0.0
    out = {"join_t": first[0], "period": first[2], "score": first[3], "ended": first[1], "queue": first[5 + qi]}
    for ts, size, price in sells:
        if ts >= int(first[0]) and price >= lv - 1e-9:
            got += size
            if got >= need:
                return dict(out, filled=True, wait_s=round(ts - first[0]))
    return dict(out, filled=False, sold_after=round(got, 1))


def finish(mid):
    r, mm = recs.pop(mid), meta_of(mid)
    done.add(mid)
    if not mm or not r["polls"]:
        return
    start = int(min(p[0] for ps in r["polls"].values() for p in ps)) - 5
    tr = trades(mm["cid"], start)
    sides = []
    for t, ps in r["polls"].items():
        sells = sorted((int(x["timestamp"]), float(x["size"]), float(x["price"])) for x in tr
                       if x.get("asset") == t and x.get("side") == "SELL")
        sides.append({"token": t, "outcome": mm["outcomes"][mm["tokens"].index(t)], "polls": len(ps),
                      **{f"at_{lv}": simulate(ps, sells, lv, i) for i, lv in enumerate(LEVELS)}})
    line = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "market_id": mid, "cid": mm["cid"],
            "league": r["league"], "title": r["title"], "t_end": r["t_end"], "trades": len(tr), "sides": sides}
    with open(OUT / f"{datetime.now(timezone.utc):%Y-%m-%d}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(line) + "\n")
    print("done", r["league"], r["title"][:50], [(s["outcome"], s["at_0.98"], s["at_0.99"]) for s in sides], flush=True)


def meta_of(mid):
    return market_meta(mid)


def winners(mid):
    """Winning token per market from Gamma once resolved (outcomePrices '1'/'0'), else None."""
    try:
        m = get_json(f"{GAMMA}/markets/{mid}")
        prices = [float(x) for x in json.loads(m.get("outcomePrices") or "[]")]
        toks = json.loads(m["clobTokenIds"])
        if m.get("closed") and prices and max(prices) > 0.99:
            return toks[prices.index(max(prices))]
    except Exception:  # noqa: BLE001
        pass
    return None


def summary():
    rows = [json.loads(l) for f in sorted(OUT.glob("*.jsonl")) for l in open(f, encoding="utf-8")]
    out = {"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "games": len(rows)}
    for lv in LEVELS:
        k = f"at_{lv}"
        tries = filled = lost = unresolved = 0
        by, losers = {}, []
        for r in rows:
            win = winners(r["market_id"])
            time.sleep(0.2)
            for s in r["sides"]:
                sim = s.get(k)
                if not sim:
                    continue
                tries += 1
                b = by.setdefault(r["league"], [0, 0, 0])
                b[0] += 1
                if sim["filled"]:
                    filled += 1
                    b[1] += 1
                    if win is None:
                        unresolved += 1
                    elif win != s["token"]:
                        lost += 1
                        b[2] += 1
                        losers.append([r["league"], r["title"][:60], s["outcome"], sim["period"], sim["score"]])
        out[k] = {"tries": tries, "filled": filled, "filled_on_loser": lost, "filled_unresolved": unresolved,
                  "by_league_tries_filled_lost": by, "loser_fills": losers}
    return out


def publish():
    f = ROOT / SUMMARY
    f.write_text(json.dumps(summary(), indent=1) + "\n", encoding="utf-8")
    git = ["git", "-C", str(ROOT)]
    try:
        subprocess.run(git + ["add", SUMMARY], check=True, capture_output=True)
        if subprocess.run(git + ["diff", "--cached", "--quiet", "--", SUMMARY]).returncode == 0:
            return
        subprocess.run(git + ["commit", "-q", "-m", "Lab: late US-games resting-bid test summary (laptop)", "--", SUMMARY],
                       check=True, capture_output=True)
        for _ in range(3):
            subprocess.run(git + ["pull", "-q", "--rebase", "--autostash"], capture_output=True)
            if subprocess.run(git + ["push", "-q"], capture_output=True).returncode == 0:
                print("summary pushed", flush=True)
                return
            time.sleep(10)
        print("summary push failed (will retry next time)", flush=True)
    except Exception as exc:  # noqa: BLE001
        print("publish error", exc, flush=True)


def main(hours):
    for f in OUT.glob("*.jsonl"):
        done.update(json.loads(l)["market_id"] for l in open(f, encoding="utf-8"))
    stop, next_pub = time.time() + hours * 3600, time.time() + 3 * 3600
    while time.time() < stop:
        if time.time() > next_pub:
            publish()
            next_pub = time.time() + 3 * 3600
        poll()
        now = time.time()
        for mid in [m for m, r in recs.items() if (r["t_end"] and now - r["t_end"] > 1200) or now - r["seen"] > 600]:
            finish(mid)
        time.sleep(5)
    for mid in list(recs):
        finish(mid)
    publish()


if __name__ == "__main__":
    if sys.argv[1:2] == ["report"]:
        print(json.dumps(summary(), indent=1))
    else:
        main(float(sys.argv[1]) if len(sys.argv) > 1 else 72)
