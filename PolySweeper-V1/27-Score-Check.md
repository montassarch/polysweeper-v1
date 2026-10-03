---
title: Check 2 - Polymarket Score Check
tags: [polysweeper, v1, safety, score-check]
created: 2026-10-03
---

# Check 2: Polymarket's own score must agree

Back to [[V1-Home]] · Why: [[26-First-Shadow-Results]] · Strategy: [[25-Zero-Loss-Strategy-Lab]]

## The idea in one line

Before buying a team, read the score Polymarket itself shows for the match.
If the score says the **other** team won, never buy.

## Why we built it

Our only loss so far (Sep 30, *EAC Extra vs MASONIC*, -$4.90) bought the
losing team. Polymarket's own data already showed **0-1, MASONIC won** at the
moment we bought. Check 2 answers "against" for that trade, so it would have
blocked it.

## How it reads the score

- **Esports:** `000-000|2-1|Bo3` means team 1 has won 2 maps and team 2 has
  won 1, best of 3. A team has won when it reaches the majority (2 of 3, 3 of 5,
  4 of 7).
- **Tennis:** `6-3, 5-7, 6-2` means games per set, player 1 first. Counts
  finished sets: 2 sets wins best of 3. An unfinished set or a retirement
  gives no verdict.
- Team 1 and team 2 follow the event title ("A vs B"). The bot matches the
  name to the outcome, so a market that lists the teams in a different order
  is handled correctly.
- Three answers: **agree** (the score says this side won), **against** (the
  score says the other side won: never buy), **unknown** (no score, series not
  finished, retirement, names don't match).

## The big test: finished Polymarket matches (up to 1,500 per league)

| League | Matches paid out | Score agrees | Score disagrees | No verdict |
|---|---|---|---|---|
| CS2 | 1,404 | 1,403 | 0 | 1 |
| LoL | 1,494 | 1,443 | **1** | 50 |
| Dota 2 | 1,422 | 1,326 | 0 | 96 |
| Valorant | 1,498 | 1,496 | 0 | 2 |
| Call of Duty | 325 | 325 | 0 | 0 |
| Rainbow Six | 1,079 | 1,057 | 0 | 22 |
| Overwatch | 456 | 425 | 0 | 31 |
| Mobile Legends | 853 | 762 | **1** | 90 |
| Honor of Kings | 1,055 | 1,003 | **1** | 51 |
| StarCraft II | 495 | 0 | 0 | 495 (no score data) |
| ATP tennis | 1,465 | 1,031 | 0 | 434 |
| WTA tennis | 1,448 | 1,415 | 0 | 33 |
| ITF tennis | 1,477 | 0 | 0 | 1,477 (no score data) |

**About 13,000 agreements and 3 disagreements.**

### The 3 disagreements: all the same fault

| Match | Score field | Paid out | The truth |
|---|---|---|---|
| LOS vs LOUD (LoL, CBLOL playoffs) | 2-3 (LOUD) | LOS | LOS won 3-2 (news reports) |
| Galaxy Phoenix FE vs Galaxy Legends (MLBB) | 2-0 (Phoenix) | Legends | Legends won both game markets |
| Rogue Warriors vs Weibo Gaming (HoK, Bo7) | 4-0 (Rogue) | Weibo | Weibo won all four game markets |

In all three, **the score field had the two teams swapped and the payout was
right**. So the score is wrong about 1 time in 4,000.

## What this means: veto and second opinion, not the only reason to buy

- **As a veto (block a buy):** if the score is wrong, we only miss one good
  trade. Cheap. Always on.
- **As a reason to buy:** a swapped score would point at the real loser. But
  the real loser's price is near $0 after the match, so the price window
  (0.96-0.995) and the junk-book filter (real bids of at least 0.50) would not
  let us buy it. A loss would need the score AND the market price AND the
  order book to all be wrong at once.

## How it runs in shadow mode (v2.3)

- **Every pretend trade** now records the check 2 verdict, so we can see
  which price-only losses it would have blocked.
- **New rule "score" (third rule):** buy only when Polymarket marks the match
  ended, the score says this side has won, the price is 0.96-0.995 with 5
  shares available, and the order book passes the junk filter.
- **Every blocked buy** is logged as `skip_score_against`.
- The dashboard has a third tab: "Score check".
- This gives CS2, LoL and Valorant (no free results source) a result-checked
  rule for the first time.

## Limits and what to watch

- Tested on **final** scores only. During a live match the score could lag
  or briefly show the wrong side. Shadow mode will show whether that happens.
- Football is not covered: its score format differs, and we use ESPN there.
- StarCraft II has no score data: always "unknown".

## Leagues added to shadow mode because of this check

Rainbow Six, Overwatch, Mobile Legends, Honor of Kings, Call of Duty, ATP and
WTA tennis. They have good score data but no other free results source, so
check 2 is what makes them testable. ITF tennis and StarCraft II are left out
(no score data).
