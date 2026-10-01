---
title: Bot Logic Spec v1 and Audit
tags: [polysweeper, logic, spec, audit]
created: 2026-10-01
---

# Bot logic: specification v1 and audit of mistakes

Back to [[README]] · Shadow v2: [[21-Shadow-Mode-v2]] · Friend review: [[22-Friend-White-Paper-Review]]

## The rule in one sentence

**Buy the winning side of a short sports match market only after the result is
confirmed final by independent sources, only at a price that still pays after
fees, only in a size that cannot hurt the account much, and refuse in every
other case.**

## The pipeline (every candidate goes through all stages, in order)

If any stage says no, the bot does nothing and writes down why.

| Stage | Question | Refuse if... |
|---|---|---|
| **0. Safety gates** | Is the bot allowed to trade at all? | Kill switch on; paused after a loss; daily loss limit hit; Polymarket or data feeds failing; clock wrong |
| **1. Discover** | Which markets are candidates? | Not a single-match market (season, award, multi-day, props, spreads, totals are out); sport/league not enabled; market closed or not accepting orders |
| **2. Map to the real match** | Is this market *exactly* this real match? | No unique match; kickoff more than 3 h apart; a team name fits both sides; names not in the alias table |
| **3. Know the settlement rule** | What result does this market pay on? | Rule unknown for this sport. Football = 90 minutes (extra time and penalties excluded). Basketball/American football/hockey/baseball = includes overtime. Esports = series winner. Tennis = check retirement rule. |
| **4. Confirm the result** | Is the result final and normal? | Fewer than 2 independent sources; sources disagree; any source says postponed, abandoned, cancelled, forfeit, walkover, disqualification, extra time (football); data older than 2 minutes; Polymarket not yet flagged "ended"; a UMA proposal disagrees with us or the market is disputed |
| **5. Pick the token** | Which token pays $1? | Winning token cannot be identified exactly (Yes/No markets: "Will X win?" -> Yes if X won, else No; draw markets -> Yes only on a 90-minute draw) |
| **6. Price and size** | Is it worth buying, and can we? | Best ask outside the band; profit after fee below minimum; fewer than 5 shares for sale inside the band (walk the real book) |
| **7. Risk limits** | Can the account afford it? | Over max per trade; already holding this match (max 1 per match); over max per sport; over max open in total; not enough cash |
| **8. Execute** (real money only) | Did the order fill correctly? | Use a limit "fill-or-kill" order at the worst acceptable price, never a market order; unique order id so a retry can never double-buy; check the fill and the balance after |
| **9. Watch until payout** | Is anything going wrong before we get paid? | UMA proposal against us or a dispute -> alert and pause; market paid 50/50 or against us -> pause and alert |
| **10. Log** | Can every decision be explained later? | Every candidate, bought or refused, is written to a log with its reason |

## Audit: mistakes and weak points found in the current code

### A. Problems that affected the running test — ALL FIXED 2026-10-01 (measurement only, no buying-rule change)

| # | Where | Problem | Why it matters | Fix |
|---|---|---|---|---|
| A1 | shadow mode | **One bad reply from the internet can crash the whole run.** There is no error guard around each market. | Your PC run could silently stop for hours. | Catch errors per market, log them, keep running. |
| A2 | shadow mode | **Too slow.** Order books are read one by one with a pause (about 0.5 s each). With 40 matches that is about 40 s per round, not 15 s. | Football's buy window is only about 2 minutes, so many chances are missed or seen late. | Read up to many books in **one request** (tested: 4 books in 0.25 s instead of 1.84 s). |
| A3 | shadow mode | **Polymarket's "ended" flag is refreshed only every 2 minutes.** | The confirmed rule waits for that flag, so it can be up to 2 minutes late, i.e. the whole football window. Recorded end times are also 2 minutes coarse. | Refresh the match state every round for matches that are live or just ended. |
| A4 | shadow mode | **Prices above 0.995 are not recorded at all.** | We learn nothing about the friend's likely band (0.995-0.999) during this test. | Record snapshots up to 0.999 (logging only, no buying rule changes). |

### B. Logic mistakes to fix before any real money

| # | Where | Problem | Fix |
|---|---|---|---|
| B1 | decision rules | **10-minute wait after the end** contradicts the data: the 0.96-0.995 window lasts about 2 min (football) and 4 min (Dota 2). With a 10-minute wait the low band almost never trades. | Choose per band: low band needs fast confirmation (0-2 min, so excellent sources); late band (0.995-0.999) can wait longer. Decide after the shadow comparison. |
| B2 | verifier | **Team names are compared as raw text** between sources ("Man City" vs "Manchester City FC"), so real agreement looks like disagreement. Safe, but the bot would refuse almost everything. | Map every source's team to one internal team ID first, then compare IDs. |
| B3 | decision model | **The decision model assumes "team A vs team B"**, but football markets are Yes/No per team and a separate draw market. Shadow mode handles this, the decision code does not. | Make the candidate "market + token", with the winning token computed by the market-type rule (stage 5). |
| B4 | verifier | **Only one real independent source for football** (ESPN). Polymarket's "ended" flag is a state, not a second opinion on who won. | Add a second source: OpenLigaDB (German leagues, free), or a cheap paid source (API-Football ~$19/month) after the test. Until then: football is test-only. |
| B5 | missing | **No check of UMA**: a market could already have a proposal for the other side, or be disputed. | Read the market's resolution status before buying; refuse if proposed against us or disputed. |
| B6 | missing | **No sport-specific settlement table.** Football excludes extra time; American sports include overtime; tennis has retirement rules. | Add the stage-3 table; refuse sports without an entry. |
| B7 | config | **Up to 2 trades per match allowed.** Doubles the damage of one mistake. | Max **1** per match. |
| B8 | missing | **No real order handling yet** (fill-or-kill, no double-buy, fill check, balance check). | Build before real money; test with tiny size. |
| B9 | missing | **No Telegram alerts or remote stop yet.** | Build before real money. |

### C. Improvements (not mistakes)

1. **Test both price bands on the same matches at the same time**, instead of
   one after the other: the comparison is fairer (same matches, same days).
2. **Full refusal log** (stage 10) so we can see *why* chances were skipped.
3. **Watch UMA for disputes** on held positions (stage 9).
4. **Alias table** for team names to raise the match rate (784 football markets
   were unmatched only because of spelling).
5. **Dashboard: time from "ended" to buy**, and "missed because too slow" count.

## Fix status (2026-10-01)

- **A1 fixed:** errors are caught per market and written to `errors.jsonl`; the run keeps going.
- **A2 fixed:** order books read in batches; tested live: 62 books in about 1 second, full round about 1.5 s (was about 30 s).
- **A3 fixed:** match states (live, ended, score) re-read every round in one batched request (0.7 s for 31 matches).
- **A4 fixed:** prices up to 0.999 recorded, and the result is checked for those matches too, so the friend's band can be studied on the **same matches** without buying there.
- **A5 fixed:** junk books refused (3 real examples refused in the live check).
- Tests: 45 automatic checks pass.

## What does not change during the current test

The buying rules of both strategies stay the same. A1-A4 only make the test
measure correctly; they need a restart of shadow mode.
