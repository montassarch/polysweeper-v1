"""Backup study (market making), part 4: pretend-quote recorder (a paper market maker). Read-only.

Nothing here can place an order: it only reads public books and trades and keeps virtual quotes in memory.

Every cycle (~20 s) it reads the books of the watched markets (CLOB POST /books, one call) and their new public
trades (Data API /trades, takerOnly=true). Per market it runs two virtual quote policies side by side, each with
its own queue position, inventory and P&L:
  A "join": bid at the best bid and ask at the best ask (or at mid +- v/2 when the best is outside the reward band);
  B "back": one tick behind A on each side (still inside the reward band).
Quote size = max(reward min size, 5) shares. A virtual order fills only after the displayed size ahead of it at
that price has traded (queue model; cancellations ahead of us are assumed, which is a little optimistic), or at
once when a trade prints through its price. After a fill the side is re-posted at the back of the queue.
Every minute our virtual orders are scored with Polymarket's reward formula against the real book
(docs.polymarket.com/programs/liquidity-rewards) and we accrue daily_rate / 1440 x our share.
Inventory limit: a side stops quoting when the position on that side reaches 3 quote sizes.
Sports (clearBookOnStart): quotes stop 10 min before game start; leftover inventory is marked at the last
pre-game mid ("exit") and also held to the result ("hold").
Outputs: lab/results/mm-recorder-summary.json (every 10 min), raw events lab/data/raw/mm/recorder-<date>.jsonl.

Usage: py -3 lab/mm_recorder.py --hours 24 [--max 30]   (picks markets from lab/data/raw/mm/scan-rows.json and the
       Gamma cache written by lab/mm_scan.py; run mm_scan.py first)
"""
import argparse, bisect, collections, datetime, json, math, os, random, sys, time, urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, "data", "raw", "mm")
OUT = os.path.join(ROOT, "results", "mm-recorder-summary.json")
UA = {"User-Agent": "polysweeper-research/0.1 (read-only data collection)"}


def req(url, body=None, tries=3):
    for i in range(tries):
        try:
            h = dict(UA)
            data = None
            if body is not None:
                h["Content-Type"] = "application/json"
                data = json.dumps(body).encode()
            return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=h, data=data), timeout=30))
        except Exception:
            time.sleep(1 + i)
    return None


def iso_ts(s):
    try:
        return datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


PLAN = {"politics_long_dated": 6, "politics_short_dated": 6, "stock_finance": 5, "crypto_ladder_other": 5,
        "sports_futures": 4, "sports_game_moneyline": 4, "culture_tech_econ": 4, "weather": 4}


sys.path.insert(0, ROOT)
from mm_scan import mtype  # noqa: E402


def pick_markets(nmax):
    """Per type: half the slots to the biggest reward pools, half to random reward markets (seeded), only
    two-sided books with mid 0.12-0.88; sports games must start 3-30 h from now (quotes stop 10 min before)."""
    rows = json.load(open(os.path.join(RAW, "scan-rows.json"), encoding="utf-8"))
    ev = {m["cid"]: m for m in json.load(open(os.path.join(RAW, "gamma-open-markets.json"), encoding="utf-8"))}
    now = time.time()
    cands = collections.defaultdict(list)
    for r in rows:
        if r.get("empty_side") or (r.get("rate") or 0) < 2:
            continue
        m = ev.get(r.get("cid"))
        if not m or not (0.12 <= r["mid"] <= 0.88):
            continue
        r = dict(r, type=mtype(m))
        g = iso_ts(m["game"]) if m.get("game") else None
        if r["type"].startswith("sports_game"):
            if not g or g - now < 3 * 3600 or g - now > 30 * 3600:
                continue
        else:
            g = None
        cands[r["type"]].append((r, m, g))
    rnd = random.Random(8)
    chosen = []
    for t, n in PLAN.items():
        lst = sorted(cands.get(t, []), key=lambda x: -x[0]["rate"])
        top = lst[:(n + 1) // 2]
        rest = lst[(n + 1) // 2:]
        pick = top + rnd.sample(rest, min(n - len(top), len(rest)))
        for r, m, g in pick:
            chosen.append({"cid": m["cid"], "tok": m["tok"], "q": m["q"][:80], "type": t, "rate": r["rate"],
                           "v": r["v"], "mn": r["mn"], "tick": float(m.get("tick") or 0.01), "game": g,
                           "fee": m.get("fee"), "qbook0": r["qbook"], "vol24": r["vol24"]})
    return chosen[:nmax]


class Side:
    def __init__(self):
        self.price = None
        self.ahead = 0.0
        self.left = 0.0


class Policy:
    def __init__(self, name, size):
        self.name, self.size = name, size
        self.bid, self.ask = Side(), Side()
        self.inv = 0.0      # YES shares (+ long YES, - long NO)
        self.cash = 0.0     # pUSD flow in YES terms
        self.reward = 0.0
        self.fills = 0
        self.fill_sh = 0.0
        self.peak_cap = 0.0
        self.worst = 0.0
        self.mtm = 0.0
        self.exit_mtm = None


def level_size(levels, price):
    for p, s in levels:
        if abs(p - price) < 1e-9:
            return s
    return 0.0


def score_side(levels, mid, v, mn):
    tot = 0.0
    for p, s in levels:
        d = abs(p - mid) * 100
        if s >= mn and d < v:
            tot += ((v - d) / v) ** 2 * s
    return tot


def q_combine(q1, q2, mid):
    if mid < 0.10 or mid > 0.90:
        return min(q1, q2)
    return max(min(q1, q2), max(q1, q2) / 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=24)
    ap.add_argument("--max", type=int, default=40)
    ap.add_argument("--cycle", type=float, default=20)
    a = ap.parse_args()
    mk = pick_markets(a.max)
    if not mk:
        print("no markets picked; run lab/mm_scan.py first")
        return
    print("watching", len(mk), collections.Counter(m["type"] for m in mk))
    start = time.time()
    day = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    log = open(os.path.join(RAW, f"recorder-{day}.jsonl"), "a", encoding="utf-8")
    st = {}
    for m in mk:
        size = max(float(m["mn"] or 0), 5.0)
        st[m["cid"]] = {"m": m, "pol": {"A": Policy("A", size), "B": Policy("B", size)}, "seen": set(),
                        "last_mid": None, "last_trade_ts": start - 5, "stopped": False, "samples": 0,
                        "book_q": [], "mids": []}
    last_reward = 0.0
    last_sum = 0.0
    while time.time() - start < a.hours * 3600:
        t_cycle = time.time()
        books = {}
        toks = [s["m"]["tok"] for s in st.values()]
        for i in range(0, len(toks), 40):
            d = req("https://clob.polymarket.com/books", [{"token_id": t} for t in toks[i:i + 40]])
            for b in d or []:
                books[b.get("asset_id")] = b
        now = time.time()
        do_reward = now - last_reward >= 60
        if do_reward:
            last_reward = now
        for cid, s in st.items():
            m = s["m"]
            b = books.get(m["tok"])
            if not b:
                continue
            bids = sorted(((float(x["price"]), float(x["size"])) for x in b.get("bids", [])), key=lambda t: -t[0])
            asks = sorted(((float(x["price"]), float(x["size"])) for x in b.get("asks", [])), key=lambda t: t[0])
            if not bids or not asks:
                continue
            v, mn, tick = float(m["v"]), float(m["mn"]), m["tick"]
            bb, ba = bids[0][0], asks[0][0]
            abb = next((p for p, z in bids if z >= mn), bb)
            aba = next((p for p, z in asks if z >= mn), ba)
            mid = (abb + aba) / 2
            s["last_mid"] = mid
            s["mids"].append((round(now), round(mid, 4)))
            pre_stop = bool(m.get("game")) and now >= m["game"] - 600
            # 1) new trades -> fills
            tr = req(f"https://data-api.polymarket.com/trades?market={cid}&limit=100&takerOnly=true") or []
            new = []
            for x in tr:
                k = (x.get("transactionHash"), x.get("proxyWallet"), x.get("side"), x.get("size"))
                if k in s["seen"] or x["timestamp"] < s["last_trade_ts"] - 120:
                    continue
                s["seen"].add(k)
                new.append(x)
            new.sort(key=lambda x: x["timestamp"])
            for x in new:
                p = float(x["price"])
                sz = float(x["size"])
                sd = 1 if x["side"] == "BUY" else -1
                if int(x.get("outcomeIndex", 0)) == 1:
                    p, sd = 1 - p, -sd
                s["last_trade_ts"] = max(s["last_trade_ts"], x["timestamp"])
                for pol in s["pol"].values():
                    side = pol.ask if sd == 1 else pol.bid
                    if side.price is None or side.left <= 0:
                        continue
                    through = (p > side.price + 1e-9) if sd == 1 else (p < side.price - 1e-9)
                    at = abs(p - side.price) < 1e-9
                    got = 0.0
                    if through:
                        got = side.left
                    elif at:
                        eat = sz - side.ahead
                        side.ahead = max(0.0, side.ahead - sz)
                        if eat > 0:
                            got = min(eat, side.left)
                    if got > 0:
                        side.left -= got
                        if sd == 1:   # we sold YES (or bought NO) at our ask
                            pol.inv -= got
                            pol.cash += got * side.price
                        else:         # we bought YES at our bid
                            pol.inv += got
                            pol.cash -= got * side.price
                        pol.fills += 1
                        pol.fill_sh += got
                        log.write(json.dumps({"ts": x["timestamp"], "cid": cid[:12], "pol": pol.name,
                                              "side": "sell" if sd == 1 else "buy", "px": side.price, "sh": round(got, 2),
                                              "inv": round(pol.inv, 2), "mid": round(mid, 4)}) + "\n")
            # 2) quotes (re-post / move), cancellations ahead of us
            for pol in s["pol"].values():
                for side, lv in ((pol.bid, bids), (pol.ask, asks)):
                    if side.price is not None:
                        side.ahead = min(side.ahead, level_size(lv, side.price))
                if pre_stop or s["stopped"]:
                    if pre_stop and pol.exit_mtm is None:
                        pol.exit_mtm = pol.cash + pol.inv * mid - abs(pol.inv) * 0.05 * mid * (1 - mid)  # exit as taker
                    pol.bid.price = pol.ask.price = None
                    continue
                # targets
                tb = bb if (mid - bb) * 100 < v else math.floor((mid - v / 200) / tick) * tick
                ta = ba if (ba - mid) * 100 < v else math.ceil((mid + v / 200) / tick) * tick
                if pol.name == "B":
                    tb, ta = tb - tick, ta + tick
                tb, ta = round(tb, 4), round(ta, 4)
                ok_b = (mid - tb) * 100 < v and tb < ba and tb > 0 and pol.inv < 3 * pol.size
                ok_a = (ta - mid) * 100 < v and ta > bb and ta < 1 and -pol.inv < 3 * pol.size
                for side, tgt, ok, lv in ((pol.bid, tb, ok_b, bids), (pol.ask, ta, ok_a, asks)):
                    if not ok:
                        side.price = None
                        continue
                    if side.price is None or abs(side.price - tgt) > 1e-9 or side.left <= 0:
                        side.price, side.ahead, side.left = tgt, level_size(lv, tgt), pol.size
                cap = (pol.size * pol.bid.price if pol.bid.price else 0) + (pol.size * (1 - pol.ask.price) if pol.ask.price else 0)
                cap += max(pol.inv, 0) * mid + max(-pol.inv, 0) * (1 - mid)
                pol.peak_cap = max(pol.peak_cap, cap)
                pol.mtm = pol.cash + pol.inv * mid
                pol.worst = min(pol.worst, pol.mtm)
            # 3) reward sample once a minute
            if do_reward and not pre_stop:
                q1b = score_side(bids, mid, v, mn)
                q2b = score_side(asks, mid, v, mn)
                qbook = q_combine(q1b, q2b, mid)
                s["samples"] += 1
                s["book_q"].append(round(qbook, 1))
                for pol in s["pol"].values():
                    o1 = score_side([(pol.bid.price, pol.bid.left)] if pol.bid.price and pol.bid.left >= mn else [], mid, v, mn)
                    o2 = score_side([(pol.ask.price, pol.ask.left)] if pol.ask.price and pol.ask.left >= mn else [], mid, v, mn)
                    qo = q_combine(o1, o2, mid)
                    if qo > 0:
                        pol.reward += float(m["rate"]) / 1440 * qo / (qbook + qo)
        # 4) summary
        if time.time() - last_sum > 600:
            last_sum = time.time()
            hrs = (time.time() - start) / 3600
            per = []
            tot = collections.defaultdict(float)
            for cid, s in st.items():
                m = s["m"]
                row = {"q": m["q"][:60], "type": m["type"], "rate": m["rate"], "v": m["v"], "size": s["pol"]["A"].size,
                       "samples": s["samples"], "median_book_q": sorted(s["book_q"])[len(s["book_q"]) // 2] if s["book_q"] else None}
                for name, pol in s["pol"].items():
                    row[name] = {"reward": round(pol.reward, 3), "fills": pol.fills, "fill_sh": round(pol.fill_sh, 1),
                                 "inv": round(pol.inv, 1), "mtm": round(pol.mtm, 3), "worst": round(pol.worst, 3),
                                 "exit_mtm": None if pol.exit_mtm is None else round(pol.exit_mtm, 3),
                                 "peak_cap": round(pol.peak_cap, 1)}
                    tot[name + "_reward"] += pol.reward
                    tot[name + "_mtm"] += pol.mtm
                    tot[name + "_cap"] += pol.peak_cap
                    tot[name + "_fills"] += pol.fills
                per.append(row)
            json.dump({"started": datetime.datetime.fromtimestamp(start, datetime.timezone.utc).isoformat(),
                       "hours": round(hrs, 2), "markets": len(st),
                       "totals": {k: round(v, 3) for k, v in tot.items()},
                       "per_day_if_linear": {k: round(v / max(hrs, 0.01) * 24, 2) for k, v in tot.items() if k.endswith(("reward", "mtm"))},
                       "per_market": per}, open(OUT, "w"), indent=1)
            log.flush()
            print(f"{hrs:.2f} h", {k: round(v, 2) for k, v in tot.items()}, flush=True)
        time.sleep(max(1.0, a.cycle - (time.time() - t_cycle)))


if __name__ == "__main__":
    main()
