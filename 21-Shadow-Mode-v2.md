---
title: Shadow Mode v2 - confirmed results
tags: [polysweeper, shadow, results]
created: 2026-10-01
---

# Shadow mode v2: testing the real rule

Back to [[README]] · Football check: [[20-Results-Check-Football]] · Dota check: [[19-Results-Check-Dota]] · Dashboard: [[18-Dashboard]]

Shadow mode now records **two pretend strategies side by side** for every match:

| Strategy | When it pretends to buy 5 shares |
|---|---|
| **Confirmed result** (the real bot's rule) | Real ask is 0.96-0.995, 5 shares are for sale, an outside source confirms a **normal finish** with **this team as winner**, and Polymarket has **flagged the match ended** |
| **Price only** (for comparison) | Real ask is 0.96-0.995 and 5 shares are for sale. No result check |

Outside sources (all free, no key):
- **Football** (Premier League, LaLiga, Bundesliga, Serie A, Ligue 1, Champions
  League, Europa League, Portugal, Netherlands): **ESPN** public scores feed.
- **Dota 2**: **OpenDota**.
- **CS2, LoL, Valorant**: no source yet, so only "price only" is recorded there.

Safety rules built in (never guess): extra time or penalties = skip; club name
fits both teams = skip; incomplete series = skip; no unique match = skip.

## Checked against real finished matches (2026-10-01)

The confirmation step was run on recently finished Champions League, Premier
League and Dota 2 markets: **9 confirmations, all agreed with what Polymarket
paid; 2 correctly skipped** (a name spelling, and an incomplete Dota series).
A 9-minute live run found **no live matches** (Thursday evening, quiet), so the
first real confirmed pretend-buys will come from your PC.

## What you need to do

1. **Pull** in Obsidian.
2. **Restart shadow mode** so it uses the new code: double-click
   `stop_shadow.bat`, wait for the window to say it stopped, then double-click
   `run_shadow.bat` again. Earlier results are kept.
3. The dashboard now has two buttons at the top of the shadow section:
   **Confirmed result** and **Price only**.

## What we will learn

- How often the confirmed rule finds a buy before the price reaches 0.995.
- Whether confirmed buys ever lose (they should essentially never).
- How many minutes after Polymarket's "ended" flag ESPN/OpenDota confirm.
- Real fill prices and how often 5 shares are not available.
