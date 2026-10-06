"""Shared helper for lab studies: look up Gamma market info by condition id (batched, cached on disk).

info[cid] = {final: [p_out0, p_out1], closed, closed_ts, finished_ts, start_ts, series, type, title, event_slug, game_id}
"""
import json, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
from polysweeper.collector import get_json, GAMMA, parse_ts  # noqa: E402

CACHE = ROOT / "lab/data/raw/market_info_cache.json"


def _load():
    try:
        return json.loads(CACHE.read_text())
    except (OSError, ValueError):
        return {}


def _save(c):
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(c))


def _one(chunk, closed):
    q = "&".join("condition_ids=" + c for c in chunk)
    return get_json(f"{GAMMA}/markets?{q}&closed={'true' if closed else 'false'}&limit=100") or []


def _row(m):
    ev = (m.get("events") or [{}])[0]
    try:
        px = [float(x) for x in json.loads(m["outcomePrices"])]
    except (KeyError, ValueError, TypeError):
        px = None
    return {"final": px, "closed": bool(m.get("closed")), "closed_ts": parse_ts(m.get("closedTime")) if m.get("closedTime") else None,
            "finished_ts": parse_ts(ev.get("finishedTimestamp")) if ev.get("finishedTimestamp") else None,
            "start_ts": parse_ts(m.get("gameStartTime")) if m.get("gameStartTime") else None,
            "series": ev.get("seriesSlug"), "type": m.get("sportsMarketType"), "title": m.get("question"),
            "event_slug": ev.get("slug"), "game_id": ev.get("gameId") or m.get("gameId"),
            "fee_rate": (m.get("feeSchedule") or {}).get("rate") if isinstance(m.get("feeSchedule"), dict) else None}


def lookup(cids, refresh_open=True):
    """Return {cid: info}. Closed markets are cached for good; open ones are re-fetched each call."""
    cache = _load()
    need = [c for c in set(cids) if c not in cache or (refresh_open and not cache[c].get("closed"))]
    chunks = [need[i:i + 20] for i in range(0, len(need), 20)]
    found = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        for closed in (True, False):
            todo = [ch for ch in chunks]
            for ms in pool.map(lambda ch: _one(ch, closed), todo):
                for m in ms:
                    found[m["conditionId"]] = _row(m) if closed or m["conditionId"] not in found else found[m["conditionId"]]
            # second pass (open) only for those not found closed
            chunks = [[c for c in ch if c not in found] for ch in chunks]
            chunks = [ch for ch in chunks if ch]
    cache.update(found)
    _save(cache)
    return {c: cache[c] for c in cids if c in cache}
