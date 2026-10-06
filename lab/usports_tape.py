"""Pull the public trade tape around the end of each US-sports game (all wallets), by event id.

For every event with a Polymarket `finished` stamp: trades from 15 min before the stamp up to now (newest first, stop when
older). Saved per event to lab/data/raw/usports_tape/<eventId>.json. Read-only; ~8 requests/s.
  python3 lab/usports_tape.py [families=main|all]
Note: Data API rows are TAKER fills by default (proxyWallet = the side that crossed the spread).
"""
import json, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
from polysweeper.collector import get_json  # noqa: E402

DATA = "https://data-api.polymarket.com"
OUT = ROOT / "lab/data/raw/usports_tape"
OUT.mkdir(parents=True, exist_ok=True)
ev = json.loads((ROOT / "lab/data/raw/usports_events.json").read_text())
families = sys.argv[1] if len(sys.argv) > 1 else "main"
GAME_FIN = {}
for e in ev:
    if e["slug"] == e["game"] and e.get("finished"):
        GAME_FIN[e["game"]] = e["finished"]
todo = []
for e in ev:
    fin = e.get("finished") or GAME_FIN.get(e["game"])
    if not fin:
        continue
    if families == "main" and e["slug"] != e["game"]:
        continue
    if (OUT / f"{e['id']}.json").exists():
        continue
    todo.append((e["id"], e["slug"], fin))
print("events to pull:", len(todo))


def pull(item):
    eid, slug, fin = item
    rows, off = [], 0
    while off <= 10000:
        page = get_json(f"{DATA}/trades?eventId={eid}&limit=500&offset={off}")
        if not isinstance(page, list) or not page:
            break
        rows += page
        if min(t["timestamp"] for t in page) < fin - 900 or len(page) < 500:
            break
        off += 500
    keep = [{k: t.get(k) for k in ("side", "price", "size", "timestamp", "proxyWallet", "conditionId", "outcomeIndex", "title")}
            for t in rows if t["timestamp"] >= fin - 900]
    (OUT / f"{eid}.json").write_text(json.dumps({"slug": slug, "finished": fin, "trades": keep, "pages": off // 500 + 1}))
    return len(keep)


t0 = time.time()
with ThreadPoolExecutor(max_workers=6) as pool:
    done = 0
    for n in pool.map(pull, todo):
        done += 1
        if done % 50 == 0:
            print(done, "events,", round(time.time() - t0), "s", flush=True)
print("done", done, "events in", round(time.time() - t0), "s")
