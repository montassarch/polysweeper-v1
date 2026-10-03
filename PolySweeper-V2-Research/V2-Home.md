---
title: PolySweeper V2 Research — Home
tags: [polysweeper, v2, research, index]
created: 2026-10-03
---

# PolySweeper V2 research — building a late-band sweeper

Separate project from V1. Goal: **work out how the "PolySweeper V2" approach
works and build our own version, through deep research and testing.** The method
should be discoverable with public data and an AI assistant.

## Notes in this project

- [[V2-01-White-Paper-Review]] — what the V2 investor paper claims, and what doesn't add up
- [[V2-02-Research-Plan]] — how we will reverse-engineer it, step by step
- [[V2-03-League-Census]] — which leagues settle the most matches per day
- [[V2-04-Public-Trades-Study]] — who sweeps, how often high-price buys lose, the real edge (0.15%)

## What we know (from the paper, unaudited)

- Buy-only, holds to payout, no leverage, never sells.
- Buys only **after the result is independently confirmed final**.
- Average edge **0.16% per trade** -> average buy price about **0.998**.
- About **18 settled trades a day** (peak 43), median **1.87 h** until paid.
- **17 data sources, 68 leagues, 11 traditional sports + 5 esports.**
- One narrow price band; long-dated markets excluded; every decision logged.

## Evidence so far (from public trades, 2026-10-03)

- Real late-band sweepers earn about **0.15% per trade** at 0.999, matching the paper.
- **0 losses** on 43,062 buys at 0.999+; every loss at 0.99+ was a buy made before
  the match was really over.
- About $1.4M/day bought at 0.999+ on these sports: crowded and automated.

## Working hypothesis

The V2 bot most likely buys the confirmed winner in the **quiet period after the match
ends and before Polymarket pays out**, at **0.997-0.999**, catching sellers who
want their money now. Edge per trade is tiny; profit comes from volume and from
near-zero result risk.
