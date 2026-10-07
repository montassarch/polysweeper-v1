"""0.999 buy-order queue (read-only, no orders): if we rested a 5-share buy at 0.999 once a match is over, would it fill?

After a result, almost all safe volume is sellers hitting resting buy orders at 0.999 (R-2026-10-07). This measures
our share of that: how many shares already wait at 0.999 (the queue ahead of us) and how many shares sellers dump
into it afterwards.

Every ~5 s: read the live match list that shadow mode writes on this PC (live.json), batch the order books of every
market in it, and log each side whose best bid is 0.99+ (bid shares at 0.999, best bid, best ask, ended flag).
When a match has been over 20 min (or left the list for 10 min): fetch its public trades (Data API, taker side) and
simulate a 5-share buy joining the back of the 0.999 queue at two moments:
  t_end  first poll with Polymarket's ended flag    (safe moment)
  t_999  first poll with a 0.999 bid on that side   (earlier, NOT safe: for comparison only)
Filled when taker SELL shares at 0.999 after that moment exceed the queue ahead + 5. Cancels ahead of us are
ignored, so the fill estimate is cautious.
Result: lab/data/raw/queue999/<utc date>.jsonl, one line per match.
  py lab/queue999.py [hours=24]        measure (stop with Ctrl-C)
  py lab/queue999.py report            summary of everything recorded so far
"""
import json, sys, time
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
from polysweeper.collector import get_json, post_json, GAMMA, CLOB  # noqa: E402

LIVE = Path(r"C:\Users\LAPTOP\polysweeper-v1\code\data\shadow\live.json")  # the live clone (shadow runs there)
DATA = "https://data-api.polymarket.com"
OUT = ROOT / "lab/data/raw/queue999"
OUT.mkdir(parents=True, exist_ok=True)
SHARES = 5
meta = {}    # market id -> {"cid", "tokens", "title", "league"}
recs = {}    # market id -> {"polls": {token: [[t, ended, q999, best_bid, best_ask], ...]}, "t_end", "seen"}


def market_meta(mid):
    if mid not in meta:
        try:
            m = get_json(f"{GAMMA}/markets/{mid}")
            meta[mid] = {"cid": m["conditionId"], "tokens": json.loads(m["clobTokenIds"]),
                         "outcomes": json.loads(m["outcomes"])}
        except Exception as exc:  # noqa: BLE001
            print("meta error", mid, exc, flush=True)
            return None
    return meta[mid]


def poll():
    try:
        live = json.loads(LIVE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001  (file is rewritten every ~2 s; try again next poll)
        return
    now = time.time()
    tok2 = {}
    for m in live.get("markets", []):
        mm = market_meta(m["mid"])
        if not mm:
            continue
        r = recs.setdefault(m["mid"], {"polls": {}, "t_end": None, "title": m["title"], "league": m["league"]})
        r["seen"] = now
        if m.get("ended") and r["t_end"] is None:
            r["t_end"] = now
        for t in mm["tokens"]:
            tok2[t] = (m["mid"], bool(m.get("ended")))
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
        asks = [(float(x["price"]), float(x["size"])) for x in b.get("asks", [])]
        best_bid = max((p for p, _ in bids), default=None)
        if best_bid is None or best_bid < 0.99:
            continue
        q999 = round(sum(s for p, s in bids if p >= 0.999), 1)
        best_ask = min((p for p, _ in asks), default=None)
        mid, ended = tok2[t]
        recs[mid]["polls"].setdefault(t, []).append([round(now, 1), ended, q999, best_bid, best_ask])


def trades(cid, since):
    out, off = [], 0
    while off < 3000:
        try:
            page = get_json(f"{DATA}/trades?market={cid}&limit=500&offset={off}")
        except Exception as exc:  # noqa: BLE001
            print("trades error", exc, flush=True)
            break
        if not page:
            break
        out += page
        if len(page) < 500 or min(int(x["timestamp"]) for x in page) < since:
            break
        off += 500
        time.sleep(0.5)
    return [x for x in out if int(x["timestamp"]) >= since]


def simulate(polls, sells, t0):
    """Join the back of the 0.999 queue at the first poll at/after t0; fill when sells after it pass queue + 5."""
    first = next((p for p in polls if p[0] >= t0 and p[3] >= 0.999), None)
    if not first:
        return None
    need, got = first[2] + SHARES, 0.0
    for ts, size in sells:
        if ts >= int(first[0]):
            got += size
            if got >= need:
                return {"queue": first[2], "filled": True, "wait_s": round(ts - first[0]), "sold_after": None}
    return {"queue": first[2], "filled": False, "wait_s": None, "sold_after": round(got, 1)}


def finish(mid):
    r, mm = recs.pop(mid), meta.get(mid)
    if not mm or not r["polls"]:
        return
    start = int(min(p[0] for ps in r["polls"].values() for p in ps)) - 5
    tr = trades(mm["cid"], start)
    sides = []
    for t, ps in r["polls"].items():
        sells = sorted((int(x["timestamp"]), float(x["size"])) for x in tr
                       if x.get("asset") == t and x.get("side") == "SELL" and float(x["price"]) >= 0.999)
        t999 = next((p[0] for p in ps if p[3] >= 0.999), None)
        sides.append({"outcome": mm["outcomes"][mm["tokens"].index(t)], "polls": len(ps),
                      "max_queue": max(p[2] for p in ps), "sold_999": round(sum(s for _, s in sells), 1),
                      "at_end": simulate(ps, sells, r["t_end"]) if r["t_end"] else None,
                      "at_999": simulate(ps, sells, t999) if t999 else None})
    line = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "market_id": mid,
            "league": r["league"], "title": r["title"], "t_end": r["t_end"], "trades": len(tr), "sides": sides}
    with open(OUT / f"{datetime.now(timezone.utc):%Y-%m-%d}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(line) + "\n")
    print("done", r["league"], r["title"][:50], [(s["outcome"], s["at_end"]) for s in sides], flush=True)


def report():
    rows = [json.loads(l) for f in sorted(OUT.glob("*.jsonl")) for l in open(f, encoding="utf-8")]
    for key in ("at_end", "at_999"):
        sims = [s[key] for r in rows for s in r["sides"] if s.get(key)]
        filled = [s for s in sims if s["filled"]]
        waits = sorted(s["wait_s"] for s in filled)
        print(f"{key}: {len(sims)} tries, {len(filled)} filled"
              + (f", median wait {waits[len(waits) // 2]} s, median queue "
                 f"{sorted(s['queue'] for s in sims)[len(sims) // 2]:.0f} shares" if waits else ""))
    print("matches:", len(rows))


def main(hours):
    stop = time.time() + hours * 3600
    while time.time() < stop:
        poll()
        now = time.time()
        for mid in [m for m, r in recs.items() if (r["t_end"] and now - r["t_end"] > 1200) or now - r["seen"] > 600]:
            finish(mid)
        time.sleep(5)
    for mid in list(recs):
        finish(mid)


if __name__ == "__main__":
    if sys.argv[1:2] == ["report"]:
        report()
    else:
        main(float(sys.argv[1]) if len(sys.argv) > 1 else 24)
