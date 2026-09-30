---
title: What is a Polymarket Sweeper?
tags: [polysweeper, basics]
created: 2026-09-30
---

# What is a Polymarket sweeper?

Back to [[README]] · Next: [[02-Strategy-and-Math]]

## Polymarket in one paragraph

Polymarket is a prediction market. Each market is a question ("Will X happen
by date Y?"). Each outcome is a token priced between $0.00 and $1.00 that
equals the market's implied probability. When the market resolves, the
winning token pays **$1.00** and the losing one pays **$0**.

## The sweeper idea

A "sweeper" bot (also called an **endgame sweep**, **near-resolution bot**,
**tail-end trading** or **bonding** strategy) buys the outcome that is
*almost certainly* going to win while it still trades slightly under $1.
It then holds until resolution and redeems at $1.

Example from the research: buy at 98.6¢, redeem at $1.00 → about 1.4¢ gross
per contract. Do it across many markets, repeatedly, and small gains add up.

## Why the gap exists

Sources claim the winning side often does not trade at exactly 1.00 until
the very end, because:

- Some holders sell early at 0.997–0.999 to free up cash or avoid stress.
- Capital is tied up until resolution, so sellers accept a small discount.
- Resolution takes time (oracle process, see [[03-Risks]]).

The bot is essentially being paid a small premium for **providing liquidity
and waiting**, and for **bearing the risk that the "sure thing" is not
sure**.

## Important: the term is informal

"Sweeper" is community slang, not an official Polymarket feature. Sources
mostly describe it as the near-certain-outcome strategy above. If you meant
something different (e.g. sweeping dust balances, or sweeping order books for
arbitrage), tell me and this note should be revised.

## Glossary

- **Token / share**: one outcome position, pays $1 or $0.
- **CLOB**: central limit order book, Polymarket's order matching system.
- **Resolution**: the official determination of the winning outcome.
- **Redeem**: exchanging a winning token for $1 of collateral.
- **pUSD**: Polymarket's collateral token (since CLOB V2, April 2026).
- **Tail risk**: a rare event that causes a large loss.
