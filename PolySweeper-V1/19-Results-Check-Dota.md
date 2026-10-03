---
title: Results Check - Dota 2 with true end times
tags: [polysweeper, results, dota2, backtest]
created: 2026-10-01
---

# Results check: Dota 2 with true end times

Back to [[V1-Home]] · Data sources: [[12-Data-Sources]] · Earlier backtests: [[15-First-Real-Backtest]]

Code: `code/polysweeper/results_opendota.py`, `code/polysweeper/dota_end_test.py`.
OpenDota is free and needs no key. It gives each game's start time and length,
so we can compute when a series really ended, and compare it with Polymarket.

## Matching Polymarket to OpenDota

- 300 Polymarket Dota 2 match markets (about 56 days).
- **169 matched** to a complete OpenDota series; **131 did not** (incomplete
  game data in OpenDota, lower-tier events, or team-name differences).
- **Winner agreement on the matched ones: 169 of 169.**
- Lesson: one early run showed 1 "disagreement". It was an incomplete series
  (1 game recorded of a best-of-3), not an error in either source. Rule added:
  **incomplete series are skipped, never guessed.** This is the same rule the
  live verifier uses.

## What the price does after the true end (mid prices)

Median price of the winner N minutes after the computed series end:

| Minutes after end | below 0.96 | 0.96 to 0.995 | above 0.995 | median price |
|---|---|---|---|---|
| 0 | 134 | 32 | 3 | 0.865 |
| 2 | 128 | 38 | 3 | 0.880 |
| 5 | 107 | 58 | 4 | 0.915 |
| 10 | 86 | 55 | 28 | 0.958 |
| 15 | 48 | 61 | 60 | 0.990 |
| 30 | 4 | 1 | 164 | 1.000 |

- In **163 of 169 matches** the winner sat inside 0.96-0.995 at some point after
  the end. Time inside that window after the end: median **4 minutes**
  (quartiles 2 and 8, max 18).
- Price first exceeded 0.995 about **16 minutes** after the computed end
  (quartiles 12 and 18). Polymarket paid out about 79 minutes after the end
  (quartiles 50 and 130).
- Many markets were already above 0.90 before the end (median 5 minutes before
  it), meaning the series was often decided earlier than its last second.

## What it suggests, and what to be careful about

- The "buy after the verified end" window looks real for Dota 2: it exists in
  almost every match and lasts a few minutes, with no loser-side surprises in
  this sample (winners agreed on both sources).
- **Caution 1, timing:** the typical 16-minute lag to reach 0.995 is steady
  (narrow spread), which could mean either a slow market or a fixed offset in my
  "true end" computation (OpenDota start time + game length). Shadow mode
  records Polymarket's own `ended` flag time, which will settle this.
- **Caution 2, mid prices:** a real buy pays the ask, and may find fewer than 5
  shares for sale. Shadow mode measures that.
- **Caution 3, coverage:** only 56% of Dota markets matched, so a live bot
  would trade fewer matches than exist. Other esports (CS2, LoL, Valorant) need
  their own result sources.
- Dota alone is about 3 chances a day; each is worth cents, not dollars.

## Football next: needs a free key

football-data.org gives finished-match results only with a free API key. When
you have the key, follow the steps in the chat. **Never paste the key in chat or
save it in the repo.** The code will read it from an environment variable called
`FOOTBALL_DATA_KEY`.

## Next steps

- [x] ~~Get a football-data.org key and store it safely.~~ (not needed)
- [x] Build the football results check the same way.
- [ ] Use shadow mode's `ended` timestamps to confirm the true end times.
- [ ] Find free result sources for CS2, LoL and Valorant.
