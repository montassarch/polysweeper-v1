"""Pull one wallet's public trades (newest ~10,500; the Data API refuses offsets past ~10,000) to lab/data/raw/wallets/.

  python3 lab/wallet_pull.py 0xWALLET [name]
Read-only (public Data API), polite pauses.
"""
import json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
from polysweeper.collector import get_json  # noqa: E402

DATA = "https://data-api.polymarket.com"
OUT = ROOT / "lab/data/raw/wallets"


def pull(wallet, max_offset=10000):
    rows, off = [], 0
    while off <= max_offset:
        page = get_json(f"{DATA}/trades?user={wallet}&limit=500&offset={off}&takerOnly=false")
        if not isinstance(page, list) or not page:
            break
        rows += [t for t in page if t.get("proxyWallet", "").lower() == wallet.lower()]
        if len(page) < 500:
            break
        off += 500
        time.sleep(0.15)
    return rows


if __name__ == "__main__":
    w = sys.argv[1].lower()
    name = sys.argv[2] if len(sys.argv) > 2 else w[:10]
    OUT.mkdir(parents=True, exist_ok=True)
    rows = pull(w)
    path = OUT / f"{name}.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf8")
    ts = [int(r["timestamp"]) for r in rows]
    print(name, len(rows), "trades", time.strftime("%Y-%m-%d %H:%M", time.gmtime(min(ts))), "->", time.strftime("%Y-%m-%d %H:%M", time.gmtime(max(ts))))
