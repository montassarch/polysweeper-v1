---
title: First Real Backtest (esports, mid prices)
tags: [polysweeper, backtest, results, esports]
created: 2026-09-30
---

# First real backtest: esports (2026-08-20 to 2026-09-30)

Back to [[README]] · Findings so far: [[14-Real-Data-Findings]] · Plan: [[11-V1-Plan-Simple]]
· Code: `code/polysweeper/collector.py`, `code/polysweeper/analyze.py`

**Read the caveats at the bottom before trusting any number.**

## What was measured

- 1,013 finished esports match markets (CS2 300, LoL 300, Dota 2 300,
  Valorant 113) from Polymarket, with about 1-minute price history.
- Rule tested: the **first time a token's price entered 0.96 to 0.995** (rising
  into it), buy 1 share and hold to payout. Both teams' tokens counted.
- Fees use each market's own rate. Prices are **mid prices**, not real asks.
- 989 tokens qualified. **17 lost (1.7%)**, 0 resolved 50/50.

## Result 1: overall, it is thin and uncertain

- Average profit **+0.57 cents per share** after fees.
- Statistical range (95%): **-0.24 to +1.38 cents**. That range includes
  zero, so this simple "buy when it crosses 0.96" rule is **not proven**.
- By price bucket: 0.96-0.97 won 97.6% (price 96.3%, good); 0.97-0.98 won
  96.6% (price 97.3%, **negative**); 0.98-0.99 won 100% (n=89); 0.99-0.995 won
  99.7% (n=296).

## Result 2: WHEN you buy matters a lot (most important finding)

Minutes between the buy moment and the market's payout time:

| Buy moment | Trades | Losses | Loss rate | Profit per share |
|---|---|---|---|---|
| More than 120 min before payout (match still going) | 545 | 15 | **2.8%** | **-0.41 cents** |
| 0 to 120 min before payout (match probably over) | 444 | 2 | **0.45%** | about **+1.8 cents** |

Buying **late, after the match is decided**, removed most losses. This matches
the friend's "after the match ends" idea. It supports the plan to trade only
after **verified** match end ([[10-Friend-Bot-Brainstorm]]).

Caveat: here "late" is measured with the payout time, which a live bot does
not know in advance. The real bot must use verified match-end instead. We still
need true match-end times from a results provider to test this properly.

## Result 3: how often and how long

- About **11 late-window chances per day** across the four esports titles
  (453 over 41 days), with **2 losses**.
- Price stays between 0.96 and 0.995 for a **median of about 5 minutes**
  (quartiles about 3 and 15). The window is short.
- With 5 shares (about $4.88 at risk), average profit per late trade is about
  **$0.09**, and one loss costs about **$4.88**. Two losses wipe out about 55
  winning trades.

## Caveats (important)

1. **Mid prices, not asks.** Real buying prices are worse. Result is optimistic.
2. **No depth data.** We don't know if 5 shares were available at that price.
3. **Hindsight in Result 2:** grouped by payout time, unknown to a live bot.
4. **Small numbers:** only 2 losses in the late group; one or two more would
   change the picture a lot.
5. **Other bots compete** for the same window; the real fill may be worse.
6. Only esports so far. Football is still being collected.

## What this changes

- Strategy v1 = **only buy after verified match end**, never mid-match.
- The bot must measure real asks and depth: **shadow mode is now the top
  priority**.
- Expected profit is small (order of $1 per day at best on $50), risk per loss is
  about 10% of the bankroll. Learning value is high; profit is unproven.

## Next steps

- [x] Finish football collection and run the same analysis.
- [x] Get true match-end times (results provider) and redo Result 2 properly.
- [x] Build shadow mode: record real order book at each candidate moment.
- [ ] Re-run with spread/depth assumptions (pessimistic fills).
