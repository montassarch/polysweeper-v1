---
title: Strategy and Math
tags: [polysweeper, strategy, math]
created: 2026-09-30
---

# Strategy and math

Back to [[README]] · See also [[03-Risks]], [[05-Fees-and-Costs]]

## Core formulas

- Gross return per trade: `r = 1/price - 1`
  - buy at 0.986 → r = 1.42%
  - buy at 0.95 → r = 5.26%
  - buy at 0.99 → r = 1.01%
- Annualized (simple): `APR = (1/price - 1) * 365 / days_to_settlement`
  - Source example: buy at 0.971 with 72 days left → ~23.9% APR.
- **Break-even win rate** ignoring fees: you lose the whole stake when wrong.
  `win_rate_needed = price`. At 0.98 you must win **more than 98 of 100**
  trades just to break even. One loss erases ~49 wins at 98¢.

That last point is the whole game: the strategy is profitable only if your
true probability of being right is **higher than the market price** by more
than fees and costs.

## Typical entry zone

Sources: 0.95–0.99 ("endgame sweep"). Higher yields come from shorter time to
resolution, since capital is recycled faster. Claims of 15–40% annualized on
deployed capital exist but come from promotional sources; verify.

## Time matters more than the spread

A 2% gain resolving in 1 day is very different from 2% resolving in 90 days.
Rank candidate markets by **APR**, not by raw spread, and subtract the risk
that resolution is delayed or disputed.

## Candidate discovery (from sources)

- Gamma API (public, no key) `/markets` and `/events`; sort by
  `closingSoon` or order by `end_date`.
- Filter: price in 0.95–0.995, resolves within N days, decent liquidity and
  order-book depth at that price.
- WebSocket market channel for live book updates.

## Variants mentioned in sources

- **Up/Down crypto markets** (short-duration, e.g. 5–15 minute): bots buy the
  likely side in the last seconds. High tail risk from last-second reversals
  and, for crypto, the highest taker fee rate (see [[05-Fees-and-Costs]]).
- **Provide liquidity instead**: post limit (maker) orders at 0.97–0.98 and
  let impatient sellers hit them. Makers pay no fee and may earn rebates.
- **Arbitrage**: buy YES+NO when the pair costs < $1 (different strategy).

## What a v1 bot would need to decide

1. Which markets qualify (rules, source of truth, time left).
2. Max stake per market and per category (correlation risk).
3. Entry: limit order (maker) vs market order (taker, pays fee).
4. Exit: hold to resolution only, or sell if price drops below a stop.
5. Kill switch and daily loss limit.
