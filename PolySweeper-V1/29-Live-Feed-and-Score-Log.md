---
title: Live Feed and Score Log (shadow mode v2.6)
tags: [polysweeper, v1, shadow, livefeed, research]
created: 2026-10-03
---

# Live feed and score log (shadow mode v2.6)

Back to [[V1-Home]] · Task list: [[24-Task-List]] · Why: [[26-First-Shadow-Results]] · Autopilot: [[28-Autopilot]]

Watching only. No orders, no money.

## Why

The results so far (note 26): buying during play loses money, and after the result there was
nothing to buy at 0.96-0.995 in 27 of 27 matches. Shadow mode only looked every 15 seconds,
so a gap of a few seconds after the result would be invisible. The owner chose (2026-10-03):

1. **Option 1:** find out whether such a gap exists, with live prices.
2. **Data for option 3:** record every score change, to test "practically locked" rules
   (tennis first) on real data later.
3. Option 2 (resting buy orders before the end) is dropped. After the result, other buyers
   already offered 0.99-0.999 in 27 of 27 matches. A 0.97 order would only fill before the
   result, and mostly when the seller knows something we don't.

## What shadow mode now does

| Part | What it does |
|---|---|
| Live feed | Polymarket's live order-book feed (websocket), in the background. Every change of the order book and every trade, as it happens. For the favourite side of each match (price 0.85+) it remembers the last 20 minutes. |
| 2-second checks | Matches near the end (a side bid 0.85+, started, not ended) get their score re-read every 2 seconds instead of 15. The moment one is decided or ended, its order book is read and the three rules run at once. |
| After-match records | Each end-window record gets `live_*` numbers: how long 5+ shares stayed for sale at 0.96-0.995 and 0.995-0.999 after we saw the result, when the winner's bid hit 0.99, and how many shares **others** bought in those price ranges after the result. |
| Daily file | `code/data/shadow/daily/<date>.jsonl`: every score change of every watched match with each side's best price at that moment (`"type": "score"`), plus the second-by-second detail of each after-match window (`"type": "end_window_live"`, from 3 minutes before to 15 minutes after). A new file each day keeps every file small. The autopilot syncs the folder. |
| Status line | In `events.jsonl` 5 minutes after start, then hourly (`"type": "live_feed_status"`): connected or not, messages, tokens with a live book, how often the live prices matched the normal 15-second read, 2-second checks run, score lines written. |

If the live feed cannot connect or misreads something, shadow mode carries on exactly as
before (15-second reads and the same rules). Feed problems go to `errors.jsonl`, at most 5
lines per hour. To run without it: `python -m polysweeper.shadow --forever --no-live`.

## How it was tested (2026-10-03)

- 10 new automatic tests (72 in total). They include a small fake websocket server on the same
  machine (handshake, subscription, books, a split message, ping/pong), a server that is not
  there (no crash, retries), and a fake GitHub for the daily folder sync.
- Two real runs of 3-4 minutes against live Polymarket data in the cloud sandbox. The sandbox
  is not allowed to reach the live feed, so this also tested the "feed refused" path: no crash,
  5 error lines, status line written. The 2-second checks ran 46 times in 3 minutes and score
  lines were written.
- **First real 2-second catch:** Valorant, Misa Esports vs NKVT. The bot saw the result about
  2 seconds after Polymarket's score showed it, read the book at once, and found **no sell
  orders at all** (best bid 0.999). Even this fast, nothing was left. The bots that clear the
  book seem to act on something faster than Polymarket's own score.
- **Tested against Polymarket's real server (2026-10-03, after the owner gave the cloud full
  network access):** connected first time, 361 messages in 25 s, 58 of 60 markets with a live book,
  live best prices matched a normal book read in 38 of 38 markets. A 2-minute shadow run with the
  feed: 26,239 messages, 28 of 28 markets with a book, 99.5% agreement over 196 checks, 0 errors.
  The owner's PC will show the same in its first `live_feed_status` line.

## What to look at after 1-2 days

- `python end_window_report.py`: the new "Live feed" section.
- If after the result there is never anything at 0.96-0.995, even with live prices: the
  after-match sweeper (V1 as planned) is not possible for us. Then the choice is between the
  late band and option 3.
- Score log: test tennis "locked" rules (for example "a set up and 5-1 in the second") on the
  recorded scores and prices. Also note retirements: one match ended 6-3, 1-0 "FT" (a retirement),
  so tennis settlement rules matter (B6).
