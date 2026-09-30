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

## More alternatives found (second search round)

Still from search summaries; none tested yet (sandbox network blocks them).

### Football / general sports

| Provider | Reported | Fit for us |
|---|---|---|
| Sportmonks | From ~EUR 29/month (entry plan covers only ~5 leagues), 2,300+ competitions, multi-source validation | Solid paid option after backtest |
| API-Football | Free (100 req/day) or ~$19/month | Cheapest upgrade path |
| football-data.org | Free; ~$30/month paid tier for 12 competitions | Good for learning |
| TheSportsDB | Free tier; ~$9/month | Community-maintained, less reliable; use only as a weak extra check |
| iSports API | Claimed balance of cost, coverage, historical depth | Worth testing |
| Goalserve, Highlightly, SportsDataIO | Mentioned as alternatives | Check later |
| Sportradar | Enterprise, custom annual contracts | Too expensive; but note Polymarket uses Sportradar data for MLB |

### Esports

| Provider | Reported | Fit for us |
|---|---|---|
| Liquipedia API | Free tier, many titles, history back to 2000s | Good for results and backtest history; check rate rules |
| OpenDota | Dota 2 pro matches: winner, score, length | Free, Dota only |
| Riot (LoL esports) | Live data from the official lolesports API | Official source for LoL |
| Abios | Industry esports data, 20 titles | Paid |
| PandaScore | See above | Free plan = schedules/results only |
| bo3.gg | Mentioned, few details | Check later |
| OddsPapi | Free esports odds from many bookmakers (incl. Pinnacle) | Price reference, not results |

## Key insight: check the source Polymarket itself uses

Polymarket resolves from a **hierarchy of official sources**: first the
governing body or tournament organiser, then official scorecards and databases,
then major outlets (AP, Reuters, ESPN, BBC Sport) and data providers. Examples:
cricket via ESPN Cricinfo, FIFA World Cup via fifa.com, MLB with official
Sportradar data. So the best "second opinion" is the **official league or
tournament result**, not only a third-party API. Each market's rules text names
its resolution source; our mapper should read it.

## Idea: Kalshi as an extra independent signal (unverified)

Kalshi has a public market-data API (no key for reads) with status stages
"determined" (result known, settlement timer running) and "finalized" (paid).
For the same match, a Kalshi "determined" state could be a third independent
confirmation. Needs testing; Kalshi resolution is typically within hours.

## Speed reminder

Polymarket resolves sports fast (NBA median ~22 minutes; overall median ~41
minutes). The buying window is short, so provider **delay** matters: measure
how many minutes after the real end each provider reports "finished".
