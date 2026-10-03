---
title: V2-01 White Paper Review (Aug 2026)
tags: [polysweeper, v2, review]
created: 2026-10-01
---

# Review: "PolySweeper V2" investor white paper (August 2026)

Back to [[V2-Home]]

Source: a 6-page investor briefing shared by the owner (the PDF itself is not
stored in this repo). It describes the bot from an early live period;
some things may have changed since. All figures are the paper's own
claims, **unaudited**, and not independently verified by us.

## What it claims

| Claim | Value |
|---|---|
| Live measurement window | 19 Jul - 7 Aug 2026 (about 20 days), real money, small account |
| Positions settled | 360 (peak day 43) |
| Losing settlements | 0 |
| Average edge per position | **0.16%** |
| Median time until paid | 1.87 hours (90% within 4.1 h) |
| Capital recycled during the run | about 42 times |
| Net return in the window | +6% (all profit reinvested) |
| Coverage | 17 independent data sources, 68 leagues, 11 traditional sports + 5 esports |
| Audited trade decisions | 503,735 (every taken or refused trade logged with a reason) |
| Projections | Base +46% year 1 (illustrative, not a forecast) |

## How it works (as described)

Buy-only, no leverage, never sells, holds to payout. Buys the winning side **only
after independent sources agree the result is final** ("structurally settled",
not "priced at 99 cents"). If confirmation fails, no trade. Long-dated markets
(championships, awards, multi-day events) permanently excluded. One narrow entry
price band. The exact confirmation rules, sources and timings are kept secret.

## Same as what we built

- Confirm first, then buy; refuse by default; sources disagree = stand down.
- Short-dated match markets only; narrow price band; hold to payout.
- Logged decisions with reasons (we log entries and skips; a full refusal log
  is a good addition).

## Key differences and what they tell us

1. **Their price band is much higher than ours.** A 0.16% average edge means an
   average buy price of about **0.998** (1 / 1.0016). Our band is 0.96-0.995. So
   their bot most likely buys **after** the price has already passed 0.995, in the
   long quiet period before payout, earning about 0.1-0.3% per trade with very
   low risk of a wrong result.
2. **Our own data on that late zone (mid prices, from 5 minutes after the end
   until payout):** the winner's mid price sat at 0.999 or higher **85% of the
   time for Dota 2 and 98% for football**. A mid of 0.9995 usually means the
   cheapest seller asks 1.000, i.e. nothing to buy. Mid prices between 0.9975 and
   0.999 appeared well under 1% of the time. So the 0.998 opportunities are likely
   **brief**: sellers dumping at 0.997-0.999 for seconds or minutes, which
   1-minute mid prices cannot show. Only real order-book watching (shadow mode)
   can measure it.
3. **Much wider coverage:** 68 leagues and 16 sport types vs our 13 leagues.
   Their throughput (18 settled a day) comes from breadth.

## Things that don't add up (to answer by our own research)

1. **Capital turns per day.** Page 1 says about 10 per day. But "42 times during
   the run" over about 20 days is about **2 per day**. The +6% return fits 2 a day
   (42 x 0.16% = 6.7%), not 10 (10 x 0.16% x 20 days would be about +37%).
   Which is right?
2. **Zero losses is not yet proof.** With 0 losses in 360 trades, the true loss
   rate could still be up to about 0.8% (statistics "rule of three"). At 0.16%
   edge, **one loss wipes out about 600 wins**. To show the loss rate is below
   break-even (0.16%) you need roughly **1,900+ trades with no loss**.
3. **"Hardened rule set, not the earlier development period."** This suggests
   the earlier period had problems (losses?). Worth asking what happened.
4. **"Regulated prediction markets" but "on-chain" payouts.** Polymarket global
   pays on-chain; Polymarket US is the regulated one. Which venue?
5. **Account size and capacity.** No dollar figures. How many shares are really
   available at 0.997-0.999? Does the edge survive larger size?
6. **Fees, rejected orders, and 50/50 resolutions** (forfeits, extra-time rules):
   how are they handled?

## How to verify (our own way)

Polymarket's trade data is public. We can find wallets that trade this way
(buying confirmed winners at 0.995+ after matches end) and study their timing,
sizes and results ourselves. See research method M2 in [[V2-02-Research-Plan]].

## Not advice

If this paper is an invitation to invest, treat the numbers as unaudited claims:
small sample, short window, small account, projections are illustrative. Verify
on-chain before trusting any of it.

## What we should change because of this

- [x] Extend shadow mode to record the **late band 0.995-0.999** for confirmed
      results (real asks and sizes), to measure this strategy.
- [ ] Add a full refusal log (every skipped candidate with its reason).
- [ ] Widen coverage over time (more leagues and sports), each with a results
      source.
