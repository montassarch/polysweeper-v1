---
title: V2-04 Public Trades Study (M2)
tags: [polysweeper, v2, research, trades, m2]
created: 2026-10-03
---

# V2-04 Public trades study (method M2)

Back to [[V2-Home]] · Plan: [[V2-02-Research-Plan]]

## What we did

Polymarket publishes every trade (price, size, wallet, time). We downloaded
**all trades on 1,075 finished match-winner markets from the last 8 days**
(Sep 25 - Oct 3): CS2, LoL, Dota 2, Valorant, Rainbow Six, Mobile Legends,
Honor of Kings, Overwatch, ATP, WTA, ITF, table tennis (Setka Cup), MLB, NFL
and NHL. Then we looked at every **buy at $0.90 or more**: did it win or lose,
how much money traded, how long before payout, and who was buying.

Script: `code/trades_study.py`. Summary data: `code/data/trades_study/summary.json`.

Gaps: football (soccer) markets were not picked up by the script (different
market layout, to fix). NBA is in its off-season.

## Result 1: how often a high-price buy loses

| Price band | Buys | Matches | Money traded | Losing buys | Loss rate | Break-even loss rate |
|---|---|---|---|---|---|---|
| 0.90-0.95 | 36,648 | 732 | $8.3M | 1,901 | 5.2% | 10% |
| 0.95-0.96 | 6,855 | 565 | $1.6M | 142 | 2.1% | 5% |
| 0.96-0.98 | 12,337 | 635 | $3.3M | 296 | 2.4% | 4% |
| 0.98-0.99 | 5,628 | 588 | $1.5M | 44 | 0.8% | 2% |
| 0.99-0.995 | 6,219 | 729 | $1.6M | 32 | 0.5% | 1% |
| 0.995-0.999 | 2,708 | 349 | $1.3M | 3 | 0.1% | 0.5% |
| **0.999+** | **43,062** | **775** | **$11.3M** | **0** | **0%** | 0.1% |

"Break-even loss rate" = the loss rate at which buying in that band makes
zero profit. Every band is (just) below break-even on average, so the market is
priced fairly. **The money is not in the price; it is in avoiding the losers.**

## Result 2: every loss at 0.99+ was a buy BEFORE the match was really over

We checked all five matches where someone lost buying at 0.99 or more:

| Match | What happened |
|---|---|
| Luminosity vs BIG (CS2, Bo3) | A wallet bought BIG at 0.99 (23 fills, $4,723) **while map 3 was still being played**; the real price at that moment was 0.45-0.75. BIG lost. Looks like a bot acting on a wrong signal. |
| 1win vs Natus Vincere (Dota 2, Bo3) | Wallets bought NaVi at 0.99-0.999 **after NaVi won game 1**, as if the series were over. 1win won games 2 and 3. The "incomplete series" mistake. |
| Team Phantasma vs The Secret Club (LoL) | Bought at 0.99 about 79 min before payout, during play; lost. |
| BetBoom vs OG (Dota 2) | Small buy at 0.99 during play; lost. |
| Falei vs Sidorova (WTA) | Bought at 0.995 about 111 min before payout, during play; lost. |

And by time before payout (buys at 0.96+):

| Bought ... before payout | Buys | Losing buys |
|---|---|---|
| 0-15 minutes | 9,112 | **0** |
| 15-60 minutes | 42,909 | 69 |
| 1-3 hours | 15,149 | 302 |
| 3 hours+ | 2,784 | 4 |

**Lesson:** a price of 0.99 during play is not certainty. Buys made after the
match is truly over did not lose. Bots that buy on a wrong or early signal do.

## Result 3: who sweeps (the competition)

Wallets buying at 0.99+ in the most matches over the 8 days:

| Wallet (public name) | Matches | Money in | Losing buys | Profit (8 days) | Typical price | Sports |
|---|---|---|---|---|---|---|
| owlgorithm-beta | 146 | $207,903 | 0 | +$313 | 0.999 | CS2, LoL, R6, Dota 2 |
| (unnamed 0x4dDC…) | 115 | $33,049 | 0 | +$261 | 0.99 | ATP, MLB, WTA, NFL |
| jiafanpomarke001 | 100 | $282,594 | 17 | **-$3,543** | 0.999 | Dota 2, Valorant, LoL, ATP |
| antec | 97 | $116,091 | 0 | +$139 | 0.999 | CS2, LoL, MLB, Valorant |
| InterzoneCo | 96 | $76,837 | 0 | +$117 | 0.999 | CS2, R6, LoL, Dota 2 |
| 467j6yj | 89 | $97,967 | 0 | +$906 | 0.99 | R6, LoL, CS2, Valorant |
| ~15 tennis wallets (Kudri, rickjodar, noator, KexShmex, Geek32, …) | ~80 each | ~$13,000 each | 0 | ~+$13 each | 0.999 | ATP, WTA, ITF |

What this tells us:

- **Late-band sweeping is real and crowded.** About $1.4M a day is bought at
  0.999+ on these sports. Most of it is in the last hour before payout.
- **Margins are tiny.** owlgorithm-beta turned over $208k for $313 profit
  (0.15%), which matches the V2 paper's "0.16% per trade" almost exactly.
- **One mistake erases weeks.** jiafanpomarke001 had 100 matches of
  0.1% gains, then bought the loser at 0.99 in one match and is down $3,543.
- **The ~15 tennis wallets behave identically** (same sizes, prices, timing:
  about 31 minutes before payout, about $13 profit each). Almost certainly
  **one operator running many wallets**.
- 467j6yj makes more per trade by buying at 0.99, but the same wallet lost
  about $11,400 buying a LoL team at 0.96 (Ruddy Sack vs Hangry Knights). The
  cheaper band pays more but bites harder.

## Result 4: timing and capacity

- In the last 15 minutes before payout, nearly all buying is at **0.999+**.
  After a match ends the price jumps to 0.999 fast; cheaper sellers (0.96-0.995)
  are rare once the result is clear.
- The band 0.995-0.999 had about **$112,000 a day** of buys 15-60 minutes
  before payout, with **0 losses**. That is the window the V2 approach targets.
- At $50, buying 5 shares at 0.997 earns about **$0.015** per trade. This
  strategy only pays at scale (thousands of dollars per trade).

## What this means for the V2 strategy

1. The V2 paper's numbers are believable: an average edge of about 0.16% is exactly what
   the real late-band sweepers here earn.
2. The edge comes from **certainty, not price**: buy only after an independent
   source says the match is over (full series, normal finish).
3. Competition at 0.999 is heavy and automated. Getting fills at
   0.995-0.998 needs speed (being first right after the end) or resting buy
   orders.
4. With a small bankroll the profit per trade is cents. V2 makes sense only
   once there is real capital, and only after V1 proves the safety rules.

## Next steps

- [ ] Fix the script for football markets and add them
- [ ] M1: use the owner's shadow logs (exact "ended" times) to measure, per
      league, how long after the real end the price reaches 0.999, and how
      much is for sale at 0.995-0.998 in that gap
- [ ] Follow a few top wallets over time (do they ever lose? which leagues?)
- [ ] M3 deep research write-up
