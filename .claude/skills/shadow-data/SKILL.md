---
name: shadow-data
description: How to read PolySweeper's shadow-mode data (pretend trades, end-window watches, live-feed health, daily score log) and report results correctly. Use before any results check, analysis or report on code/data/shadow/.
---

# Reading shadow-mode data

The owner's PC writes these files; the autopilot syncs them to GitHub every 3 hours and on each code
update. **Read only: never edit them by hand.** `git pull --rebase` first so you read the newest sync.

## Files (`code/data/shadow/`)

| File | Record `type`s | What it is |
|---|---|---|
| `trades.jsonl` | `entry`, `settled`, `skip_bad_book`, `skip_thin`, `skip_second_buy`, `skip_score_against` | Pretend buys (5 shares) and why chances were skipped |
| `events.jsonl` | `live_feed_status`, `end_window`, `end_window_live` | Live-feed health; the winner's book for 15 min after a match is decided |
| `errors.jsonl` | any | Crashes and errors (should be empty) |
| `daily/<date>.jsonl` | `score` | Every Polymarket score change, with both books at that moment |

## Counting pretend trades correctly

- An `entry` and its `settled` share the same **(rule, key)**. Key = `<market_id>:<token_idx>`. The same
  key can appear under several rules (`confirmed`, `score`, `price_only`), so always match on both.
- Old records may lack `rule`: treat them as `price_only`.
- Open buy = an entry with no settled record yet. `settled.result` is `win`, `loss` or a 50/50.
- `entry.event_ended_flag` false = bought during play (the risky kind). Say which kind every loss was.
- Quick summary: `cd code && py -3 -m polysweeper.shadow_report` (Windows) or `python3 -m polysweeper.shadow_report`.

## End-window fields worth reporting

- `max_shares_096_0995` / `max_shares_0995_0999`: shares for sale in our band / the late band after the result.
- `live_trades_v1_after`, `live_trades_late_after`, `live_trades_late_shares_after`: real trades seen by the live
  feed after the result (only when `live_samples` > 0).
- `seconds_watched` short + `closed_because` "shadow mode stopped" = watch cut by a restart: say so, don't count it as "nothing for sale".

## Live-feed health (`live_feed_status`)

Healthy = `connected` true, `errors` 0, `book_checks_agree_pct` near 100. The newest line's `ts` also shows how
fresh the PC data is: older than ~4 hours means the PC may be off or asleep.

## Reporting to the owner

Plain words, short. Lead with: wins / losses / pretend profit (today and since the start), any new loss and why,
whether the safe rules (`confirmed`, `score`) bought anything, PC data freshness. Times in Tunisia time (UTC+1).
Write findings into the vault (task list, session log, research note), not only in chat.
