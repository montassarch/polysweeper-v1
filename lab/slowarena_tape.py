"""Pull the full public tape (all trades) of a list of events (by Gamma event id) to lab/data/raw/slowarena/<id>.json.
  python3 lab/slowarena_tape.py quebec|brazil|peru|ids...
"""
import json, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
from polysweeper.collector import get_json  # noqa: E402

DATA = "https://data-api.polymarket.com"
OUT = ROOT / "lab/data/raw/slowarena"
OUT.mkdir(parents=True, exist_ok=True)


def pull(eid, cap=10000):
    f = OUT / f"{eid}.json"
    rows, off = [], 0
    while off <= cap:
        page = get_json(f"{DATA}/trades?eventId={eid}&limit=500&offset={off}")
        if not isinstance(page, list) or not page:
            break
        rows += page
        if len(page) < 500:
            break
        off += 500
    keep = [{k: t.get(k) for k in ("side", "price", "size", "timestamp", "proxyWallet", "conditionId", "outcomeIndex", "outcome", "title")} for t in rows]
    f.write_text(json.dumps(keep))
    return eid, len(keep), off >= cap


if __name__ == "__main__":
    ids = sys.argv[1:]
    with ThreadPoolExecutor(max_workers=5) as pool:
        for eid, n, capped in pool.map(pull, ids):
            print(eid, n, "CAPPED" if capped else "")
