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

## Update 2026-10-03 15:11 UTC sync

The PC ran without a break all day (no gap longer than 45 minutes since 01:00 UTC). 0 errors.

**Price-only rule** (the only rule that has bought anything):

| | Since start (Sep 30) | Today (02:00-15:11 UTC) |
|---|---|---|
| Pretend buys | 70 | 60 |
| Paid out | 57: 55 wins, 2 losses | 47: 46 wins, 1 loss |
| Net so far | -$0.80 | +$2.68 |
| Waiting for payout | 13 | 13 |

A **second loss is already certain** but not yet paid out: Leo Team vs ENJOY (CS2).
Counting it, today is about **-$2.13** and the total about **-$5.61**.

**Both new losses look the same.** In a CS2 best-of-3, one team led 1-0 in maps and
was priced at 0.96. The bot bought that team, and the other team came back to win 2-1:
- Esport Academy Copenhagen vs Wildcard (FOX Legacy Cup): bought at 0.96 at 1-0, lost -$4.81.
- Leo Team vs ENJOY (CCT Europe): bought ENJOY at 0.96 at 1-0, ENJOY lost 2-1 (-$4.81 when it pays out).

In both matches the bot then also bought the *other* team at 1-1 (0.98 and 0.99).
That breaks B7 "max 1 trade per match", which shadow mode does not enforce yet.

Today's buys, grouped by the state of the match at the moment of buying:

| Match state when bought | Paid out | Losses |
|---|---|---|
| Esports, series not yet won (e.g. 1-0 in a Bo3) | 20 | **2 (10%)** |
| Tennis, during play | 25 | 0 |
| Series already won (score shows it) | 1 | 0 |

At 0.96 a single loss costs about 30 average wins (+$0.16 each). Losing 1 trade in 10
is far worse than the ~1 in 25 needed just to break even. **Buying an esports series
before it is won is not safe**, which is what notes 25 and 26 predicted.

**End-window study** (the key question: is there anything left to buy *after* the
result is known?). It counts only the 9 matches recorded after the 14:07 fix (CS2 x4,
WTA x2, MLBB, Dota 2, ATP); the 34 earlier rows are noisy (see below).
- **8 of 9:** at the first check after the result, the winner had **no sell orders at
  all**, with the best bid at 0.99-0.999.
- **1 of 9** (Rybakina vs Charaeva, WTA China Open, a big match): about 8,700 shares were
  for sale at 0.996-0.999 at the first check. About 4,200 were left at 17 s (best ask 0.998),
  and none by 39 s.
  Nothing at 0.96-0.995.
- In every case the score and the "ended" flag changed at the same moment.
- Together with the first look: **0 of 14 matches had anything for sale at 0.96-0.995
  after the result.** The late band (0.995-0.999) sometimes has shares on big matches.

**Data quality notes:**
- 6 of the 9 windows were cut short because shadow mode restarted. The autopilot restarts
  it after **every** push to `main`, even a note edit. Fewer pushes make for cleaner data.
- `seconds_observed` shows 0 when the book never changes (it measures to the last
  *change*, not to the end of the watch), so it cannot tell how long a window lasted.
- `end_window_report.py` still counts rows written before the fix. Its "atp 2 (28%) with
  0.96-0.995 for sale" is one cancelled match (score 0-0, price 0.51, heading for a 50/50
  payout) counted twice. It was not a real chance.

## Update 2026-10-03 16:31 UTC sync

- The ENJOY loss paid out as expected (-$4.81).
- **A third loss today, this time in tennis:** Rybakina vs Charaeva (WTA China Open). The bot
  bought Rybakina at 0.96 when she led **2-1 in games in the first set**. She lost 6-3, 4-6, 3-6.
  -$4.81. Tennis today: 30 wins, 1 loss.
- Today (02:00-16:31 UTC): 64 buys, 58 wins, 3 losses, 3 waiting, net **-$4.94**.
  Since Sep 30: 67 wins, 4 losses, net **-$8.42**. Every loss was a buy made during play.
- End window: 16 clean matches now, still **0 with anything for sale at 0.96-0.995** after the
  result. One (the same Rybakina match) had shares at 0.995-0.999.

**Fixes made the same day:** shadow mode now makes at most 1 pretend buy per match per rule
(the second chance is logged as `skip_second_buy`); the end-window rows record how long the
watch really ran (`seconds_watched`); the report leaves out rows from before the 14:07 fix;
and the autopilot no longer restarts shadow mode for notes-only updates ([[28-Autopilot]]).
