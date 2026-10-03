---
title: PolySweeper V2 Research — Home
tags: [polysweeper, v2, research, index]
created: 2026-10-03
---

# PolySweeper V2 research — rebuilding the friend's strategy ourselves

Separate project from V1. Goal: **work out how the friend's "PolySweeper V2"
works and build our own version, using only public information and our own
research. We do not ask the friend anything.** The friend likely built it with an
AI assistant and little prior experience, so the method should be discoverable.

## Notes in this project

- [[V2-01-Friend-White-Paper-Review]] — what the friend's investor paper claims, and what doesn't add up
- [[V2-02-Research-Plan]] — how we will reverse-engineer it, step by step

## What we know (from the paper, unaudited)

- Buy-only, holds to payout, no leverage, never sells.
- Buys only **after the result is independently confirmed final**.
- Average edge **0.16% per trade** -> average buy price about **0.998**.
- About **18 settled trades a day** (peak 43), median **1.87 h** until paid.
- **17 data sources, 68 leagues, 11 traditional sports + 5 esports.**
- One narrow price band; long-dated markets excluded; every decision logged.

## Working hypothesis

The friend's bot buys the confirmed winner in the **quiet period after the match
ends and before Polymarket pays out**, at **0.997-0.999**, catching sellers who
want their money now. Edge per trade is tiny; profit comes from volume and from
near-zero result risk.
