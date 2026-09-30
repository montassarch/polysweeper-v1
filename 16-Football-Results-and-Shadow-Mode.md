---
title: Football Results and Shadow Mode
tags: [polysweeper, backtest, football, shadow]
created: 2026-09-30
---

# Football results and shadow mode

Back to [[README]] · Esports results: [[15-First-Real-Backtest]] · Code overview: [[13-Code-Overview]]

## Football backtest (mid prices, buy when price first rises into 0.96-0.995)

Data: 9 leagues (Premier League, LaLiga, Bundesliga, Serie A, Ligue 1,
Champions League, Europa League, Portugal, Netherlands), about 280 days,
3,442 markets (winner and draw markets), 3,500 qualifying tokens.

- **101 losses out of 3,500 (2.9%)**, 0 resolved 50/50.
- Average profit: **-0.30 cents per share** after fees. At best break-even,
  and this uses optimistic mid prices.
- By league: LaLiga +1.4c, Europa League +1.0c, Champions League +0.5c, Premier
  League +0.3c, Netherlands +0.3c; France -0.4c, Bundesliga -1.1c, Serie A
  -1.3c, Portugal -1.6c. Small samples per league; don't over-read.
- Price buckets: 0.96-0.97 won 96.0% (price 96.3%); 0.97-0.98 won 97.7%;
  0.98-0.99 won 97.3% (price 98.3%, negative); 0.99-0.995 won 99.5%.

### The "buy late" test does NOT work for football (with this proxy)

For esports, buying within ~2 hours of payout removed most losses. For football
the same split shows no clean pattern (within 120 min of payout: 1,000 trades,
22 losses, +0.3c, range -0.6c to +1.2c). Reason: football markets pay out
**soon after the final whistle**, so "minutes before payout" cannot tell
in-play from finished. Losses seen within 30 minutes of payout were late-game
comebacks (e.g. a team at 0.965 that lost).

To test "after the match is really over" for football we need **true match-end
times**, which shadow mode will record (Polymarket's `ended` flag) or which a
results provider gives.

## Esports update (56 days, after adding Valorant)

- Buying within 90-120 min of payout: about 400-470 trades, 2 losses,
  +1.7 to +1.8 cents per share.
- Caveat: with so few losses the statistical range looks tighter than it really
  is. "Rule of three": 2 losses in 469 trades is still consistent with a true
  loss rate of roughly 1.5%, which is close to break-even.

## Conclusion so far

- **Esports:** promising but unproven, and only for buying after the match is
  decided.
- **Football:** no edge visible at mid prices; needs true end times first.
- Both use mid prices, so real results will be worse. **Shadow mode is the
  next real test.**

## Shadow mode (built)

Code: `code/polysweeper/shadow.py`, report: `shadow_report.py`.
It places **no orders**. It only reads public data.

What it does:
1. Every 2 minutes lists live/starting matches (esports and football leagues).
2. Every 15 seconds reads the **real order book** of each match-winner token.
3. When a token's real best ask is between 0.96 and 0.995, it "pretends" to
   buy 5 shares by **walking the real book** and records the average fill
   price, fee, available size, and whether Polymarket flagged the match as
   `ended` at that moment.
4. If fewer than 5 shares are for sale in range, it records a **thin-book
   skip** (a big unknown until now).
5. When the market closes it records win/loss/50-50 and the fake profit.
6. Logs: `data/shadow/snapshots.jsonl` (books), `trades.jsonl` (entries,
   skips, settlements), `state.json` (resume after restart).
7. **Kill switch:** create the file `data/shadow/STOP` and it stops cleanly.

Run it: `cd code && python3 -m polysweeper.shadow --leagues cs2 lol dota2 val
ucl uel --minutes 60` (or `--forever`). Report: `python3 -m polysweeper.shadow_report`.

### Where to run it

It must run for **days or weeks** to collect enough cases. The cloud sandbox
stops background jobs after at most a couple of hours, so the long run needs
**your own computer left on, or a small cheap server**. Setup steps to be
written when you choose.

## Next steps

- [ ] Review the first shadow test run.
- [ ] Decide where shadow mode runs long term (PC or server).
- [ ] Add a results provider (true match end time + second source).
- [ ] After 1-2 weeks of shadow data, decide on the rules and any real money.
