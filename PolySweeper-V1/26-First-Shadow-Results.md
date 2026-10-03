---
title: First Shadow Results (Sep 30 - Oct 3)
tags: [polysweeper, v1, shadow, results]
created: 2026-10-03
---

# First shadow results (Sep 30 - Oct 3)

Back to [[V1-Home]] · Task list: [[24-Task-List]] · Shadow mode: [[21-Shadow-Mode-v2]]

These are pretend trades only. No real money was used.

## What happened

| | Count | Result |
|---|---|---|
| Price-only pretend trades settled | 10 | 9 wins, 1 loss |
| Wins | 9 | +$0.05 to +$0.19 each, +$1.43 in total |
| Loss | 1 | -$4.90 |
| **Net (price only)** | | **about -$3.47** |
| Confirmed-rule trades | 0 | see "Why zero confirmed" below |
| Junk books skipped (A5 filter) | 7 | the filter worked as intended |
| Crashes / errors | 0 | |

All 10 trades were Counter-Strike (CS2).

## The one loss: what went wrong

On Sep 30 (before the junk-book filter existed) the bot "bought" the
**losing** team in *EAC Extra vs MASONIC* (Dust2.dk Ligaen). After the match
ended, a stale sell order was still sitting on the loser's side at a high
price. The price-only rule saw a cheap-looking high price and took it.

- That is exactly the case the junk-book filter (A5) now blocks: if the best
  bid is below 0.50 or the other side's ask is 0.10 or more, the bot skips.
- The confirmed rule would also have blocked it: the results check names
  the winner, so the bot never buys the loser.

**Lesson, again:** one loss wipes out about 25 wins. Price alone is not
enough. This is why the real bot will only use the confirmed rule.

## Why zero confirmed trades

1. **A bug in how shadow mode found matches (fixed 2026-10-03).** It searched
   by the date the match was *listed* on Polymarket, not the date it is
   *played*. Many matches are listed days in advance, so they were never
   watched. A check at 01:00 UTC on Oct 3 showed:

   | League | Matches within ±36 h | Found by the old search |
   |---|---|---|
   | LoL | 9 | 0 |
   | Dota 2 | 6 | 2 |
   | CS2 | 29 | 12 |

   The new search reads all open matches and keeps the ones whose real start
   time falls between 12 hours ago and 45 minutes from now. It now finds all
   of them (CS2 29, LoL 9, Dota 2 6, Valorant 6).
2. **We only have results checks for football and Dota 2.** CS2 has no free
   results source yet, so CS2 can only be tested with the price-only rule.
   Football had few finished matches in the window.
3. **The PC ran only about 22 of 49 hours.** It went to sleep overnight.

## What to do now

- Owner: pull in Obsidian, then run `stop_shadow.bat` and `run_shadow.bat`.
- Owner: Windows Settings → System → Power → Screen and sleep → set "When
  plugged in, put my device to sleep after" to **Never**. Keep the PC plugged in.
- Assistant: find a free results source for CS2 (and LoL) so these
  matches can use the confirmed rule. CS2 is the most active esport.

## Update 2026-10-03 afternoon: first autopilot sync

- 02:00-13:41 UTC: 52 price-only pretend buys, 35 paid out, **35 wins, 0 losses,
  +$5.73**. 59 junk books skipped.
- **0 score-check buys:** all 52 buys happened while the match was still in play.
  Once a match is flagged ended, the price is already above 0.995 (the trades study
  saw the same: after the end the price jumps to 0.999).
- One Overwatch buy had the score already showing the series won while Polymarket
  had not yet flagged it ended: a possible safe window.
- New: the **end-window study** (shadow mode v2.4) records, for every match, the
  winner's price and shares for sale for 15 minutes after the score shows it decided
  or the ended flag appears. Report: `python end_window_report.py`.

## End-window first look (16-minute live check, 2026-10-03 14:07-14:23 UTC)

5 matches were seen going from "playing" to "decided" (Valorant, HoK, CS2 x2, MLBB).
In **all 5**, at the first check after the score showed the series won (checks are
every 15 seconds), the winner had **no sell orders at all**: best bid already
0.99-0.999. The score and the ended flag changed at the same moment.

Meaning, if it holds on the owner's PC data: after the result is known there is
nothing left to buy at 0.96-0.995 (and often nothing even at 0.999). The 0.999 bots
clear the book within seconds. Our price-only pretend buys all happened before the
end, while the match was still being played.

Small sample. The owner's PC data over 1-2 days will confirm or correct it. If it
holds, the V1 plan must change. Options to study:
- a much faster price feed (websocket) to see whether a window of a few seconds exists;
- resting buy orders placed just before the end (maker orders), with strict cancel rules;
- in-play buying only when the result is mathematically locked (needs a live score feed).
