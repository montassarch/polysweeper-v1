"""Quebec 5 Oct 2026 per-riding winner markets: in-band buys after the 'decided' moment, and did the bought token win?
  python3 lab/qc_slowarena_check.py   -> lab/results/2026-10-06-test-quebec-slowarena.json
Winner of a market = the resolved Yes token (outcomePrices [1,0]). Read-only."""
import json, sys, time, urllib.parse
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
from polysweeper.collector import get_json, GAMMA, parse_ts  # noqa: E402
DATA = "https://data-api.polymarket.com"
TCLOSE = parse_ts("2026-10-06T00:00:00Z")      # polls close 20:00 ET
seen = {}
for q in ["quebec national assembly election winner", "national assembly election winner riding quebec", "Quebec riding winner 2026", "quebec-national-assembly-election-winner"]:
    for st in ("closed", "active"):
        r = get_json(f"{GAMMA}/public-search?q={urllib.parse.quote(q)}&limit_per_type=100&events_status={st}") or {}
        for e in r.get("events", []):
            if "quebec-national-assembly-election-winner" in e["slug"]:
                seen[e["id"]] = e
        time.sleep(0.3)
print("ridings", len(seen), flush=True)
out = []
for e in list(seen.values()):
    fresh = get_json(f"{GAMMA}/events?slug={e['slug']}")
    if fresh:
        e = fresh[0]
    rows, off = [], 0
    while off <= 10000:
        p = get_json(f"{DATA}/trades?eventId={e['id']}&limit=500&offset={off}")
        if not isinstance(p, list) or not p:
            break
        rows += p
        if len(p) < 500:
            break
        off += 500
        time.sleep(0.2)
    res = {}
    for m in e["markets"]:
        try:
            px = [float(x) for x in json.loads(m["outcomePrices"])]
        except Exception:
            continue
        res[m["conditionId"]] = (m.get("groupItemTitle") or m["question"][:40], px)
    winners = [(c, v) for c, v in res.items() if v[1][0] >= 0.97]   # provisional: most are not yet UMA-resolved
    rec = {"slug": e["slug"], "markets": len(e["markets"]), "resolved_yes_winners": [v[0] for c, v in winners], "trades": len(rows)}
    if len(winners) == 1:
        wc, (wn, _) = winners[0]
        wr = sorted([t for t in rows if t["conditionId"] == wc and t["timestamp"] >= TCLOSE], key=lambda t: t["timestamp"])
        first = next((t["timestamp"] for t in wr if t["outcomeIndex"] == 0 and float(t["price"]) >= 0.95), None)
        rec["final_yes_prices"] = res[wc][1]
        rec["decided_min_after_close"] = None if first is None else round((first - TCLOSE) / 60)
        # in-band BUYs (0.96-0.995) after close, on ANY market of the event, split by whether the bought token won
        good = bad = 0; gsh = bsh = 0.0; late_good_sh = 0.0; badlist = []
        for t in rows:
            if t["timestamp"] < TCLOSE or t["side"] != "BUY":
                continue
            p, sz = float(t["price"]), float(t["size"])
            if not 0.96 <= p < 0.995:
                continue
            c = t["conditionId"]
            if c not in res:
                continue
            won = res[c][1][t["outcomeIndex"]] >= 0.97
            if won:
                good += 1; gsh += sz
                if first is not None and t["timestamp"] >= first:
                    late_good_sh += sz
            else:
                bad += 1; bsh += sz; badlist.append([res[c][0], t["outcomeIndex"], p, sz, round((t["timestamp"] - TCLOSE) / 60)])
        rec.update(inband_win_fills=good, inband_win_shares=round(gsh), inband_loss_fills=bad, inband_loss_shares=round(bsh), shares_after_decided=round(late_good_sh), losing_buys=badlist[:10])
    out.append(rec)
    print(rec["slug"][:45], {k: v for k, v in rec.items() if k not in ("slug", "losing_buys")}, flush=True)
(ROOT / "lab/results/2026-10-06-test-quebec-slowarena.json").write_text(json.dumps(out, indent=1))
