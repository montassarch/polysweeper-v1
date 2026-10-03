---
title: Real Data Findings (first look)
tags: [polysweeper, data, findings]
created: 2026-09-30
---

# Real data findings (first look, 2026-09-30)

Back to [[V1-Home]] · Plan: [[11-V1-Plan-Simple]] · Data: [[12-Data-Sources]]

After the network was opened, we queried Polymarket's public APIs directly.
Tiny sample (3 esports matches plus metadata), so treat as **leads, not proof**.

## Connection test

| Host | Result |
|---|---|
| gamma-api.polymarket.com | works |
| clob.polymarket.com | works (needs a normal User-Agent header; default Python one got 403) |
| api.football-data.org | reachable (needs free key for real data) |
| api.opendota.com | works |
| liquipedia.net | reachable but HTTP 429 on a plain request (needs proper User-Agent and rate rules) |
| api.elections.kalshi.com | reachable but HTTP 429 (rate limited) |

## Verified facts from Polymarket's own API

1. **Minimum order size = 5 shares** (`orderMinSize`). At 0.96–0.995 that is
   about **$4.80–$4.98 per trade**, not $2. One loss costs ~10% of a $50
   bankroll. **Config changed:** max stake $5.25, min shares 5, max open
   $15.75 (3 trades), daily loss limit $5.5. A $50 bankroll can only hold 3
   positions, so diversification is very limited.
2. **Each market carries its own fee schedule** (`feeSchedule`): e.g.
   `rate 0.05, rebateRate 0.15` or `rate 0.03, rebateRate 0.25`, `takerOnly`.
   The bot should read this per market instead of assuming one rate.
3. **Official resolution source per league** is listed in `/sports`
   (471 leagues): LoL, Dota 2, Valorant -> Liquipedia; CS2 -> HLTV;
   Premier League -> premierleague.com; LaLiga -> laliga.com; cricket ->
   ESPN Cricinfo; etc. These are the exact sources to cross-check.
4. **Match events include Polymarket's own score feed**: `ended`, `score`
   (e.g. `000-000|2-0|Bo3`, `1-1`), `period` (e.g. `VFT` = full time),
   `startTime`. Match events contain many child markets (Map/Game winners,
   totals, props). Market type field: `sportsMarketType`
   (`moneyline`, `child_moneyline`, `totals`, `soccer_anytime_goalscorer`...).
5. **Resolution status fields exist**: `umaResolutionStatus`, `closedTime`,
   `umaEndDate`, `negRisk`, `orderPriceMinTickSize`.
6. **How to list real matches:** `GET /sports` gives a `series` id per league
   (e.g. CS2 10310, LoL 10311, EPL 10188); then
   `GET /events?series_id=<id>&closed=true&order=endDate&ascending=false`.

## First look at price behaviour (3 CS2 matches, winner token, mid prices)

- Price jumped to ~1.0 and stayed there while the market stayed **open for
  about 1 to 2 hours more** until `closedTime` (resolution), e.g. 1.0 at
  16:30, closed 18:25.
- In one match the price went 0.685 -> 0.979 -> 1.0 within ~30 minutes, so the
  tradable "gap" zone (0.96-0.995) exists mainly in the **last minutes of the
  deciding map**, not for hours after the end.
- The history sample had sparse points (72-114 over the day), so we cannot yet
  say how many minutes the ask sat inside 0.96-0.995, or how much size.
  **Mid price 1.0 does not show the real ask**; depth data is still missing.

## What this means

- The after-the-end window may be **much shorter** (minutes) than hoped, and
  competition is likely high. The realistic opportunity is the decisive
  moments of the last game/map, which raises risk (comebacks).
- The friend's "last minute or after the end" fits this picture.
- Next measurement: for many closed matches, how long was the ask between
  0.96 and 0.995 and what was the profit after fees.

## Next steps

- [x] Build the collector: closed esports/football match events -> moneyline
      market, winner, price history, Polymarket score, `closedTime`.
- [x] Measure the gap window per match (minutes, prices).
- [x] Start shadow mode to record real order books (depth).
- [x] ~~Get a free football-data.org key (store as an environment secret).~~ (not needed)
