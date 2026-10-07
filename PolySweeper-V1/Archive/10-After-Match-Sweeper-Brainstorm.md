---
title: Brainstorm — The "After-the-Match" Sweeper
tags: [polysweeper, brainstorm, sports, architecture]
created: 2026-09-30
---

> **Archived 2026-10-07: history, may be outdated.** Current state: [[V1-Home]], [[24-Task-List]], [[34-Fill-Scoreboard]].

# Brainstorm: the "after-the-match" sweeper

Back to [[V1-Home]] · Sports background: [[09-Sports-Markets]] · Risks: [[03-Risks]]

## Starting idea (second-hand description of a working bot)

- Buys in the **last minute or right after a match ends**, before the market
  settles. Uses **UMA** resolution delay as the window.
- Around **100 trades per day**, across **all sports**.
- Polymarket's own result data is "very bad" right now, so the bot uses a
  **separate sports-results API** to confirm the real score.
- Code lives on **GitHub**: change logic on a branch, test, then merge; no
  need to touch the running main project.
- The **sweep logic** (when to buy) is separate and has to be designed.
- There is a **kill switch**.

Nothing above is verified. It is a concept, not a proven edge.

## Key insight: it changes what you are betting on

| Buy before the end | Buy after the end |
|---|---|
| "Will the team win?" (game risk) | "Is my data right, and will it resolve as expected?" (data + resolution risk) |

Risk moves from the game to the plumbing. Plumbing can be tested and
monitored. That is why this design is safer than a late-game sweep. It is also
why **verification quality is the product**.

## Why a gap can exist

- UMA proposal plus challenge window takes hours ([[03-Risks]]).
- Some holders sell at 0.98–0.998 to free cash.
- Polymarket's own result feed may lag.

Why it may be small: other bots chase the same pennies, and depth at 0.99 is
limited. Expect thin edges.

## Math you must respect

- Buy at 0.985 → win +1.52%, lose −100%.
- Break-even error rate ≈ **1.5%** (before fees). With fees, less.
- So the real failure rate (wrong score, voided game, dispute loss, bad
  market mapping) must be **far below 1%**. At 100 trades/day, one loss a
  week erases weeks of profit.

## Proposed architecture (modules)

1. **Discovery**: list open sports markets and their end times (Gamma API).
2. **Mapper**: link each Polymarket market to the same match at the results
   provider. *Hardest part.* Wrong mapping = wrong bet.
3. **Status watcher**: detect "match finished" per sport (overtime,
   penalties, retirement, walkover, abandoned).
4. **Verifier**: require **two independent sources** to agree, then wait a
   confirmation delay. Any disagreement = skip.
5. **Rules check**: read the market's own resolution rules (void cases,
   spread/total definitions) and compute the exact outcome per market type.
6. **Price and depth check**: only buy if price ≤ limit and enough size.
7. **Risk engine**: position caps, daily loss limit, exposure cap while
   waiting for resolution, circuit breakers.
8. **Executor**: limit orders preferred (maker, no fee).
9. **Redeemer**: claim winnings after resolution.
10. **Journal**: log every decision and outcome (feeds this vault).
11. **Kill switch** (see below) and **paper mode** for everything.

## Kill switch ideas

- **Manual**: a file or env flag the bot checks before every order; also a
  remote command (e.g. Telegram) so you can stop it from your phone.
- **Automatic triggers**: any realized loss beyond X; two sources disagreeing
  more than N times; API errors; unexpected price spike on a "won" market;
  daily loss limit hit; balance drops unexpectedly.
- Stop means: cancel open orders, stop new ones, alert you, keep holding.

## GitHub workflow

- `main` = stable, runs the bot. Changes go through a **branch → test →
  pull request → merge**.
- Keep **strategy rules in a config file**, separate from engine code.
- **Never commit keys**; `.gitignore` excludes `.env`.
- Tests: replay historical matches through the verifier before any release.

## What is missing or worth adding

- Market/match **mapping** logic and its failure handling.
- **Void and edge cases** per sport.
- **Backtest** with real history (how often would "verified final, price ≥
  0.97" have lost?).
- **Paper trading** phase with a scoreboard.
- **Monitoring and alerts**, daily report.
- **Exposure cap** across positions waiting on resolution.
- **Latency/rate-limit handling** and retries that never double-buy.
- **Data source cost and reliability** review; a fallback provider.
- **Wallet safety**: dedicated wallet, small balance.
- **Legal/account check** ([[06-Legal-and-Compliance]]).

## Open questions for the user

See the chat log for the list; answers get recorded in
[[07-Open-Questions-and-Next-Steps]].
