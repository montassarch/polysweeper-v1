---
title: Data Sources
tags: [polysweeper, data, api]
created: 2026-09-30
---

# Data sources

Back to [[README]] · Plan: [[11-V1-Plan-Simple]]

From search summaries only; prices and limits change. Verify before choosing.

## What the bot needs

The after-the-match sweeper needs only: **match finished? who won? final
score? when did it end?** It does **not** need live in-game stats. That makes
cheap or free sources plausible.

## Polymarket side (free, public)

- **Gamma API**: list markets and events, end dates, rules text.
- **CLOB `/prices-history`**: price over time per outcome token; 1-minute
  fidelity; no API key. Gives **mid prices only**, no order-book depth.
  Old markets may return blank or limited data.
- **WebSocket market channel**: live book updates (useful for shadow mode).
- **Not available for history:** order-book depth. So record it ourselves
  going forward (shadow mode).

## Football results (candidates)

| Provider | Free tier (reported) | Notes |
|---|---|---|
| football-data.org | Free forever, ~12 top competitions, 10 req/min | Good to learn; limited leagues |
| API-Football (API-Sports) | 100 requests/day, 1,200+ leagues | Broad coverage, tight daily cap |
| BALLDONTLIE | Free tier | Also lists several football leagues |

## Esports results (candidates)

| Provider | Reported | Notes |
|---|---|---|
| PandaScore | Free plan: schedules and results ("fixtures"), 1,000 req/hour; **live data from about €1,000 per month per game** | Live not needed for us; check what free "results" really includes and delay |
| BALLDONTLIE | Lists CS2, Valorant, LoL, Dota 2 | Check depth of coverage |

## Multi-sport (for later)

- API-Sports (100 req/day per sport on free).
- BALLDONTLIE: NBA, NFL, MLB, NHL, tennis, golf, F1, MMA and more.
- Others mentioned: iSports API, BrokerSports.

## Selection checklist (to do)

- [ ] Does it give a clear **"finished"** status and **final result**?
- [ ] How many minutes after the real end is the result available?
- [ ] Does it mark forfeits, walkovers, abandoned or cancelled matches?
- [ ] Are team/event names stable enough to map to Polymarket markets?
- [ ] Historical results for backtesting, and at what price?
- [ ] Free-tier limits vs how many markets we watch.
- [ ] A second, independent source per sport for cross-checking.

## Plan for cost

Free tiers for the backtest and shadow mode. Decide on a paid plan only after
results show the edge exists.
