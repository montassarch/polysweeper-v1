---
title: V2-02 Research Plan
tags: [polysweeper, v2, research, plan]
created: 2026-10-03
---

# V2 research plan

Back to [[V2-Home]]

## Questions to answer (by research, not by asking)

1. **Who sells at 0.997-0.999 after a match ends, how often, and how many shares?**
2. **How long is that window** (from the end, or from the result being final, until payout)?
3. **Which 68 leagues / 16 sports** give the most such chances?
4. **What could the 17 sources be** (official league sites and APIs, ESPN, OpenDota, Liquipedia, HLTV, Sportradar-fed feeds, etc.)?
5. **What confirms "final"** in a way that is "impossible to reverse" per sport?
6. **Is it already being done by other bots** (and how competitive is it)?

## Methods

| # | Method | What it gives |
|---|---|---|
| M1 | **Our own shadow data**: V1 shadow mode already logs real order books up to 0.999 and checks results there too | Real asks, sizes and timing in the late band, on the same matches |
| M2 | **On-chain trade study**: Polymarket's public trade data lets us list who bought the winning side at 0.995+ after a match ended | Find wallets that behave like the friend's bot: timing, sizes, markets, win record, without asking anyone |
| M3 | **Deep web research**: public write-ups, GitHub projects and forums on "resolution sniping", "settlement premium", "end-of-game sweeping" | Known methods, pitfalls, typical sources |
| M4 | **League census**: rank Polymarket's leagues by daily match volume and late-band activity | Which leagues to cover first |
| M5 | **Source census**: for the top leagues, find a free or cheap result source and its delay | A path to "17 sources" |

## Steps

- [ ] M2: build a small script to pull public trades for finished match markets and find late-band buyers
- [ ] M3: deep research write-up (sources, methods, competition)
- [ ] M4: league census from Polymarket data
- [ ] M1: analyse late-band data from the owner's shadow logs once synced
- [ ] M5: source census for the top leagues
- [ ] Write a V2 strategy spec (entry band, confirmation rules, timing, sizing)
- [ ] Shadow-test the V2 spec, then compare with V1

## Ground rules

- No contact with the friend; public information only.
- Same safety standards as V1: shadow test first, no real money until proven.
- Reuse V1 code where it fits (the repo's `code/` folder); keep V2 notes here.
