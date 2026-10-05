"""Summarise shadow-mode results: python -m polysweeper.shadow_report"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path

PATH = Path("data/shadow/trades.jsonl")
EVENTS_PATH = Path("data/shadow/events.jsonl")


def local_day(ts: str) -> date:
    """Date of an ISO timestamp in the PC's own time zone (Tunisia on the owner's PC)."""
    return datetime.fromisoformat(ts).astimezone().date()


def today_lines(rows: list[dict], today: date) -> list[str]:
    """Today's pretend buys: settled results per rule, and buys still waiting for payout."""
    entries, settled = {}, {}
    for r in rows:
        k = (r.get("rule", "price_only"), r.get("key"))
        if r.get("type") == "entry":
            entries[k] = r
        elif r.get("type") == "settled":
            settled[k] = r
    lines = [f"TODAY ({today.isoformat()}, PC time)"]
    done_today = {k: s for k, s in settled.items() if local_day(s["ts"]) == today}
    if not done_today:
        lines.append("  no pretend buy paid out today yet")
    for rule in sorted({k[0] for k in done_today}):
        group = [s for k, s in done_today.items() if k[0] == rule]
        wins = sum(s["result"] == "win" for s in group)
        losses = sum(s["result"] == "loss" for s in group)
        pnl = sum(s["pnl"] for s in group)
        lines.append(f"  {rule}: paid out {len(group)} (win {wins}, loss {losses}), fake P&L ${pnl:+.2f}")
    open_now = [e for k, e in entries.items() if k not in settled]
    lines.append(f"  still waiting for payout: {len(open_now)}")
    for e in open_now:
        lines.append(f"    - {e.get('outcome')} at {e.get('vwap', 0):.3f} ({e.get('rule', 'price_only')}): {e.get('question')}")
    return lines


def live_feed_line(events_path: Path = EVENTS_PATH) -> str:
    """Last live-feed health line written by shadow mode."""
    last = None
    if events_path.exists():
        for line in events_path.read_text().splitlines():
            if '"live_feed_status"' in line:
                last = line
    if last is None:
        return "LIVE FEED: no status yet"
    s = json.loads(last)
    state = "connected" if s.get("connected") else "NOT connected"
    agree = s.get("book_checks_agree_pct")
    agree_txt = f"{agree:.0f}% agree with normal reads" if agree is not None else "no checks yet"
    return f"LIVE FEED ({s.get('ts', '?')[:16]} UTC): {state}, errors {s.get('errors', 0)}, {agree_txt}"


def main():
    try:                                         # team names with unusual characters crashed the Windows console
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if not PATH.exists():
        print("no shadow data yet")
        return
    rows = [json.loads(line) for line in PATH.read_text().splitlines() if line.strip()]
    for line in today_lines(rows, datetime.now().astimezone().date()):
        print(line)
    print(live_feed_line())
    print()
    print("SINCE THE START")
    entries, settled, thin, bad = {}, {}, [], []
    for r in rows:
        if r["type"] == "entry":
            entries[r["key"]] = r
        elif r["type"] == "settled":
            settled[r["key"]] = r
        elif r["type"] == "skip_thin":
            thin.append(r)
        elif r["type"] == "skip_bad_book":
            bad.append(r)
    print(f"entries: {len(entries)} | settled: {len(settled)} | skipped because the book was too thin: {len(thin)}"
          f" | skipped because the book looked fake: {len(bad)}")
    groups = [("CONFIRMED RESULT rule", lambda r: r.get("rule") == "confirmed"),
              ("SCORE CHECK rule (Polymarket score says this side won)", lambda r: r.get("rule") == "score"),
              ("MLB LEAD 7+ rule (7+ runs ahead after 8 innings, game still on)", lambda r: r.get("rule") == "mlb_lead7"),
              ("PRICE ONLY rule, match flagged ended", lambda r: r.get("rule", "price_only") == "price_only" and r["event_ended_flag"] is True),
              ("PRICE ONLY rule, match still in play", lambda r: r.get("rule", "price_only") == "price_only" and r["event_ended_flag"] is not True)]
    for label, test in groups:
        keys = [k for k, r in entries.items() if test(r)]
        done = [k for k in keys if k in settled]
        wins = sum(settled[k]["result"] == "win" for k in done)
        losses = sum(settled[k]["result"] == "loss" for k in done)
        splits = len(done) - wins - losses
        pnl = sum(settled[k]["pnl"] for k in done)
        avg_fill = sum(entries[k]["vwap"] for k in keys) / len(keys) if keys else 0
        print(f"  {label}: entries {len(keys)}, settled {len(done)} (win {wins}, loss {losses}, 50/50 {splits}), "
              f"fake P&L ${pnl:+.2f}, avg fill {avg_fill:.3f}")
    if thin:
        print("  thin-book skips: the price looked right but fewer than the minimum shares were for sale at that price")


if __name__ == "__main__":
    main()
