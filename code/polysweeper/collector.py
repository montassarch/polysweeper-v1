"""Download finished sports matches from Polymarket's public APIs.

Usage (from the code/ folder):
  python -m polysweeper.collector LEAGUE [LEAGUE ...] --events 200
Example leagues: cs2 lol dota2 val epl lal ucl
Output: data/real/<league>.jsonl  (one line per moneyline market; resumable)

Only read-only public endpoints are used. Be polite: small pause between calls.
"""
from __future__ import annotations

import argparse
import http.client
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
UA = {"User-Agent": "polysweeper-research/0.1 (read-only data collection)"}
PAUSE = 0.2
OUT_DIR = Path("data/real")


def get_json(url: str, tries: int = 5):
    delay = 2.0
    for attempt in range(tries):
        try:
            time.sleep(PAUSE)
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                wait = float(e.headers.get("Retry-After", delay)) if e.headers else delay
                time.sleep(wait)
                delay *= 2
                continue
            if e.code == 404:
                return None
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException, OSError):
            time.sleep(delay)
            delay *= 2
    return None


def post_json(url: str, payload, tries: int = 4):
    """POST JSON with the same polite retry rules as get_json. Returns parsed JSON or None."""
    delay = 2.0
    body = json.dumps(payload).encode()
    for attempt in range(tries):
        try:
            time.sleep(PAUSE)
            req = urllib.request.Request(url, data=body, method="POST",
                                         headers={**UA, "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                time.sleep(delay)
                delay *= 2
                continue
            return None
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException, OSError):
            time.sleep(delay)
            delay *= 2
    return None


def leagues() -> dict:
    data = get_json(f"{GAMMA}/sports") or []
    return {x["sport"]: x for x in data}


def parse_ts(value):
    """'2026-09-30 18:25:47+00' or ISO 'Z' -> unix seconds (None if unknown)."""
    if not value:
        return None
    v = str(value).replace("Z", "+00:00").replace(" ", "T")
    if len(v) > 3 and v[-3] in "+-" and ":" not in v[-3:]:
        v += ":00"
    try:
        return int(datetime.fromisoformat(v).timestamp())
    except ValueError:
        return None


def price_history(token_id: str, start: int | None = None, end: int | None = None):
    """1-minute-ish history for [start, end]; falls back to the coarse 'max' view."""
    if start and end and end > start:
        start = max(start, end - 12 * 3600)        # keep each request under 12 hours
        h = get_json(f"{CLOB}/prices-history?market={token_id}&startTs={start}&endTs={end}&fidelity=1")
        pts = [[p["t"], p["p"]] for p in (h or {}).get("history", [])]
        if pts:
            return pts
    h = get_json(f"{CLOB}/prices-history?market={token_id}&interval=max&fidelity=1")
    return [[p["t"], p["p"]] for p in (h or {}).get("history", [])]


def market_record(event: dict, m: dict, league: dict) -> dict | None:
    if m.get("sportsMarketType") != "moneyline":
        return None
    try:
        outcomes = json.loads(m["outcomes"])
        finals = [float(x) for x in json.loads(m["outcomePrices"])]
        tokens = json.loads(m["clobTokenIds"])
    except (KeyError, ValueError, TypeError):
        return None
    if len(tokens) != len(outcomes) or len(outcomes) != len(finals):
        return None
    g0 = parse_ts(m.get("gameStartTime")) or parse_ts(event.get("startTime")) or parse_ts(event.get("startDate"))
    c1 = parse_ts(m.get("closedTime"))
    start = g0 - 1800 if g0 else None
    end = c1 + 300 if c1 else None
    toks = []
    for name, final, tok in zip(outcomes, finals, tokens):
        hist = price_history(tok, start, end)
        toks.append({"outcome": name, "final_price": final, "token_id": tok, "history": hist})
    fee = (m.get("feeSchedule") or {}).get("rate")
    return {
        "league": league["sport"],
        "league_name": league.get("name"),
        "resolution_source": league.get("resolution"),
        "event_id": event.get("id"),
        "event_title": event.get("title"),
        "event_start": event.get("startTime") or event.get("startDate"),
        "event_ended": event.get("ended"),
        "event_score": event.get("score"),
        "event_period": event.get("period"),
        "market_id": m.get("id"),
        "question": m.get("question"),
        "game_start": m.get("gameStartTime"),
        "closed_time": m.get("closedTime"),
        "uma_status": m.get("umaResolutionStatus"),
        "min_order_size": m.get("orderMinSize"),
        "fee_rate": fee,
        "tokens": toks,
    }


def collect(league_key: str, max_events: int) -> int:
    lg = leagues().get(league_key)
    if not lg:
        print(f"unknown league '{league_key}'")
        return 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{league_key}.jsonl"
    seen = set()
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                seen.add(json.loads(line)["market_id"])
    written = events_seen = 0
    offset = 0
    with path.open("a") as out:
        while events_seen < max_events:
            url = (f"{GAMMA}/events?series_id={lg['series']}&closed=true&limit=50&offset={offset}"
                   f"&order=endDate&ascending=false")
            batch = get_json(url)
            if not batch:
                break
            for ev in batch:
                events_seen += 1
                for m in ev.get("markets", []):
                    if m.get("id") in seen:
                        continue
                    rec = market_record(ev, m, lg)
                    if rec and all(t["history"] for t in rec["tokens"]):
                        out.write(json.dumps(rec) + "\n")
                        out.flush()
                        seen.add(m.get("id"))
                        written += 1
                if events_seen >= max_events:
                    break
            offset += 50
    print(f"{league_key}: looked at {events_seen} events, wrote {written} new moneyline markets -> {path}")
    return written


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("leagues", nargs="+")
    ap.add_argument("--events", type=int, default=100, help="max events to scan per league")
    args = ap.parse_args(argv)
    for lk in args.leagues:
        collect(lk, args.events)
    return 0


if __name__ == "__main__":
    sys.exit(main())
