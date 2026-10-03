---
title: Strategy Catalog
tags: [polysweeper, strategy, catalog]
created: 2026-09-30
---

# Strategy catalog (all bot types found)

Back to [[V1-Home]] · Deep dive on #1: [[01-What-is-a-Sweeper]], [[02-Strategy-and-Math]]

Source: web-search summaries (see [[Sources]]). Difficulty and "beginner fit"
ratings are my judgement, not from sources. Profit claims in sources are often
from bot sellers; treat with skepticism.

## A. Sweep / resolution family

| # | Strategy | Idea |
|---|---|---|
| 1 | **Endgame sweep** (near-resolution, tail-end, bonding) | Buy the near-certain outcome at 0.95–0.99, hold to $1. See [[02-Strategy-and-Math]]. |
| 2 | **Short-window crypto sweep** (Up/Down markets) | Same idea on 5–15 min BTC/ETH markets: buy the likely side in the final seconds. Needs speed, highest fee rate. |
| 3 | **Sniping** (news/new-market entry) | Enter fast when news lands or a market launches, before the price adjusts. Sources use the word loosely; some mean #1. |

## B. Arbitrage family

| # | Strategy | Idea |
|---|---|---|
| 4 | **Intra-market arbitrage** | Buy YES + NO when together they cost < $1; one pays $1. |
| 5 | **Negative-risk / multi-outcome arbitrage** | In winner-take-all events, buy every YES when all YES prices sum < $1. NegRisk Adapter lets 1 NO convert to YES on every other outcome. Margins wider but legs are thin; net often negative for retail. |
| 6 | **Combinatorial / cross-market (logical) arbitrage** | Related markets priced inconsistently (e.g. "wins state" vs "wins election"). |
| 7 | **Cross-platform arbitrage** | Same event priced differently on Polymarket vs Kalshi; hedge both legs. |
| 8 | **Up/Down short-window arbitrage** | Fast repricing crypto markets; capture inefficiencies before window closes. |

## C. Market-making family

| # | Strategy | Idea |
|---|---|---|
| 9 | **Spread-capture market making** | Quote both sides, earn the spread, manage inventory by skewing quotes. |
| 10 | **Liquidity-rewards farming** | Rest limit orders near the midpoint; daily pUSD rewards, orders need not fill. |
| 11 | **Maker-rebate harvesting** | Get back ~20% (crypto) / ~25% (others) of taker fees on your filled liquidity. Often combined with #9 and #10. |

## D. Signal / information family

| # | Strategy | Idea |
|---|---|---|
| 12 | **Copy trading** | Mirror proven wallets with proportional sizing and stops. |
| 13 | **Fair-value / AI-agent trading** | Build your own probability model (or LLM agent) and trade when price differs from it. |

## Suggested study order

1. #1 Endgame sweep (already covered)
2. #2 Short-window crypto sweep
3. #4 Intra-market arbitrage, then #5 NegRisk
4. #9–11 Market making and rewards
5. #12 Copy trading
6. #13 Fair-value / AI, #6, #7, #3 last

## Notes per strategy

Filled in one by one as we go through them. Status: #1 covered.
