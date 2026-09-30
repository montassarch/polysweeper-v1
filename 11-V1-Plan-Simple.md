---
title: V1 Plan in Plain Language
tags: [polysweeper, plan, v1, risk, backtest]
created: 2026-09-30
---

# V1 plan (plain language)

Back to [[README]] · Idea: [[10-Friend-Bot-Brainstorm]] · Data: [[12-Data-Sources]]
· Risks: [[03-Risks]] · Legal: [[06-Legal-and-Compliance]]

## Decisions so far (from the owner)

- Building our **own** logic from scratch (friend's code is not used).
- Owner does **not code**; the assistant writes code and explains it simply.
- **Backtest with fake money, starting at $50.** Real money only later.
- Location: **Tunisia**.
- First sports: **esports and football**; later all sports.
- Goal: **learn and profit**; start very small and simple, improve slowly.
- Risk appetite: **avoid losses as much as possible**.
- Uses **Telegram** (alerts + remote kill switch).
- Will pay for a data API **after** the backtest, then move to a server.

## The honest truth about "not losing"

Nothing can guarantee zero losses. Buying at 0.99 gives about +1% per win and
−99% on a loss, so one loss erases ~99 wins. The design goal is **rare and
small losses**, and a bot that **stops itself** when anything looks wrong.
See [[02-Strategy-and-Math]].

## How the bot makes money (simple example)

1. A match ends. You know who won. Polymarket hasn't paid out yet.
2. The winner's share still sells at $0.99 because payout takes time.
3. Buy 100 shares for $99. After settlement you receive $100. Profit: $1.
4. The fee is tiny at this price (formula below), so ~$0.95 net.
5. The danger: the market does **not** pay $1 (50/50, dispute, wrong data).

## Facts found that shape the design (verify before real money)

- **Tunisia is listed as accessible** (not restricted) by one source. Check the
  official geoblock page. Do not use VPNs to get around blocks (against the
  terms). Funding route (how to get pUSD from Tunisia) is **not researched**.
- **Settlement speed:** median ~41 minutes after the event ended; 90th
  percentile ~6.4 hours; 99th ~4.2 days; ~1% of markets disputed (all
  categories, one 12-month study). Sports are usually faster.
- **50/50 rule (big one):** cancelled or tied matches, and wins by
  **forfeit, walkover or disqualification**, resolve **50/50** ($0.50 per
  share). Postponed matches that are not replayed in ~2 weeks also go 50/50.
  Buying at 0.99 and getting 0.50 is a ~49% loss on that trade.
- **Fee formula:** `fee = shares × rate × price × (1 − price)`. At 0.99 in
  sports (rate 0.05) that is about $0.05 per 100 shares, i.e. ~0.05%. So at
  these prices, paying the taker fee is cheap compared with a ~1% gain.
- **Backtest data limit:** free price history gives **prices only, no order
  book depth**, so it can test the *logic* but not whether you could really
  have bought at that price and size.

## The pipeline (what the bot does, in order)

1. **Watch** open sports markets (esports, football first).
2. **Match** each market to the same match at the results provider.
3. **Wait** until the match is officially finished.
4. **Confirm** with two independent sources and wait a short delay.
5. **Read the market rules**; skip anything with 50/50 or void risk.
6. **Check price** (inside a safe range) and **size** (enough volume).
7. **Risk check** (limits below). If any check fails, do nothing.
8. **Buy**, then track until payout; **log everything**.
9. **Telegram** messages; you can pause or kill it from your phone.

## Risk rules for the $50 fake bankroll (starting values, adjustable)

- Max **$2 per trade** (4% of bankroll). A loss costs at most $2.
- Max **$15 open at once** (30%) across all waiting trades.
- Max **2 trades per match/market**; **no more than $6 per sport** at once.
- **Daily loss limit: $3.** Hit it → bot stops until you say go.
- **Any loss → auto-pause** and Telegram alert; you review before restart
  (during the first weeks).
- Buy only between **0.96 and 0.995** (tunable after backtest).
- Skip if: sources disagree, rules mention 50/50 for this situation, match
  mapping is uncertain, status is anything but finished, or data is stale.
- Enable a sport only after it shows **zero unexplained losses** in testing.

## Kill switch

- Telegram commands: `/status`, `/pause`, `/resume`, `/kill`, `/pnl`.
- Automatic triggers: loss over limit, data sources disagree repeatedly,
  API errors, balance mismatch, unexpected price drop on a "won" position.
- Kill = cancel open orders, stop new ones, alert, keep holding.

## Backtest plan (fake $50)

1. List **resolved sports markets** (esports, football) from past months.
2. For each, get the **real match end time** from the results provider.
3. Get the market's **price history** around that time.
4. Apply the bot's rules: *would it have bought? at what price?*
5. Record: win, loss, 50/50, dispute, time to payout, fee, profit.
6. Report: win rate, total profit on $50 with the sizing rules, worst loss,
   worst streak, count of 50/50 and disputed cases, by sport.
7. **Gate:** only continue if losses are ~zero after filters and net profit
   is positive with **pessimistic fill assumptions** (assume only part fills
   and a worse price than the chart shows).

## Forward test ("shadow mode") — recommended

Because history has no depth, also run the bot **live with no orders**: each
time it would buy, record the real order book and what happened later. This
gives honest numbers for free. Start this as early as possible.

## Improvement ideas (assistant's opinion)

1. **Shadow mode first** (above).
2. **50/50 and void filter** from the rules text (esports forfeits, football
   abandoned/tied cases).
3. **Two-source agreement + confirmation delay**.
4. **"Wait for the proposal" mode (idea, unverified):** only buy after the
   oracle's proposed answer matches our verified result. Safer, but the price
   may already be ~0.995, leaving less profit. Needs testing.
5. **Per-sport switches** and a scoreboard; turn on only proven sports.
6. **Size by order-book depth**, never take more than a small part of the
   visible volume.
7. **Daily report to Telegram** (trades, wins, losses, skipped, why).
8. **Cheap data first:** the bot only needs "match finished + final score",
   not live stats, so cheap APIs may be enough ([[12-Data-Sources]]).
9. **Git branches + tests**: every change tested on past data before merge.
10. **Dedicated wallet, small balance**, no keys in the repo.
11. **Tunisia check:** confirm access on the official page and work out a legal
    funding route before any real money.

## Status

- [x] Research and plan written
- [ ] Choose results providers (football + esports) and test free tiers
- [ ] Build market lister and match mapper
- [ ] Build backtester and first report
- [ ] Build shadow mode
- [ ] Telegram bot (alerts + kill switch)
- [ ] Review results; decide on tiny real money
