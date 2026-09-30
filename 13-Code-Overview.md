---
title: Code Overview (plain language)
tags: [polysweeper, code, v1]
created: 2026-09-30
---

# Code overview (plain language)

Back to [[README]] · Plan: [[11-V1-Plan-Simple]] · Data: [[12-Data-Sources]]

Code lives in the `code/` folder of this repo. Nothing in it touches real money
or the internet yet.

## What exists now

| Piece (file) | What it does, in simple words |
|---|---|
| `config.json` | The rulebook: max $ per trade, daily loss limit, price window, which sports. Change numbers here, no coding needed. |
| `verifier.py` | The fact-checker. Says "match is really over and X won" only if **every** data source agrees, the data is fresh, the match ended normally, and 10 minutes passed. |
| `decide.py` | The brain. For each chance it answers **BUY** or **SKIP** and always gives the reason. |
| `risk.py` | The accountant. Tracks fake cash, open trades, daily loss; **pauses the bot after any loss**; works out how many shares are allowed. |
| `fees.py` | Computes the Polymarket fee (formula from secondary sources, verify). |
| `killswitch.py` | The emergency stop. A file that, when present, blocks all buying. The Telegram bot will be able to create it from your phone. |
| `backtest.py` | The time machine. Replays past chances through the brain with fake $50 and prints a report. |
| `make_sample_data.py` | Makes **fake** test data so we can check the machinery. |
| `tests/` | 24 automatic checks that the rules work (e.g. forfeit = skip, sources disagree = skip, loss = pause). |

## How one decision flows

1. Kill switch on? **Skip.**  Paused? **Skip.**  Daily loss hit? **Skip.**
2. Sport and bet type allowed? Market-to-match link certain? Else **skip.**
3. Do all sources agree the match ended normally? Else **skip.**
4. Is this token the winner? Price inside 0.96–0.995? Profit after fee big
   enough? Else **skip.**
5. Enough room under the money limits and enough volume? Else **skip.**
6. Otherwise **BUY** a small amount.

## First test run (on FAKE data, proves nothing about profit)

300 invented chances → 83 bought, 217 skipped with clear reasons (disabled
sport, too early, sources disagreed, bot paused after a loss...). One invented
loss cost $2.00 and paused the bot, exactly as designed.

## What is NOT built yet

- [ ] Downloading **real** Polymarket markets and price history
- [ ] Downloading **real** match results (football, esports)
- [ ] The market-to-match mapper (hardest part)
- [ ] Shadow mode (live run with no orders, recording the order book)
- [ ] Telegram bot (alerts, `/pause`, `/kill`)
- [ ] Real order placement (not before weeks of testing)

## Blocker

The cloud sandbox **cannot reach** `gamma-api.polymarket.com`,
`clob.polymarket.com`, `api.football-data.org` or `api.pandascore.co`
(network policy). Either the environment's allowed hosts must be widened, or
the data download step must run on the owner's own computer.

## Things to verify before any real money

- Real **minimum order size** on Polymarket. If it is higher than our $2
  per-trade cap (e.g. ~5 shares ≈ $4.90), the $50 plan needs changing.
- Current sports **fee rate** (0.03 vs 0.05) and the fee formula.
- Whether "finished" at the results providers matches when Polymarket settles.
