---
title: Fill Scoreboard
tags: [polysweeper, lab, scoreboard]
created: 2026-10-07
---

Back to [[30-Research-Hub]] · [[24-Task-List]]

# One question until 21 October

**Owner, 2026-10-07: "Which method gets filled with zero losses?"** Every lab agent works on this until
**2026-10-21**. The 17:00 tester updates this table every day and the phone summary is this table in short form.
On 21 Oct: a method with real fills and 0 losses goes to a tiny real-money test (owner decides); if none, we rethink.

| # | Method | Fills (pretend) | Losses | Money per day | Verdict | Data / who measures |
|---|---|---|---|---|---|---|
| 1 | Buy during play at 0.96-0.99 (`price_only`) | 400 settled | 13 (3.3%) | +$0.23 in total | **NO** (comebacks; kept only as a yardstick) | shadow, analyst |
| 2 | Buy after the result at 0.96-0.995 (`score`, `confirmed`) | 2 (score) | 0 | +$0.14 | **NOT YET**: almost never fills | shadow, analyst |
| 3 | Rest a buy at 0.999 once the match is over | **0 of 36** at the safe moment | - | pool ~$680/day for all bots, but it goes to orders placed long before | **Leaning NO**: median queue ~119k shares, sellers far fewer (final 2026-10-08) | `lab/queue999.py` on the laptop; summary in `lab/results/queue999-summary.json` (every 3 h); report 2026-10-08 |
| 4 | **MAIN JOB:** rest buys at 0.98+ in the last 30 min of US games | queue_late: 0.98 bid filled 9 of 9 games, 0.99 bid 5 of 9 (public tape: 12 loser fills in 6 of 746 games) | 0 so far (n=9) | ? | **NOT YET**, n far below 200; public tape shows losers do happen: 805 of 1,319 at 0.999, only 118 at 0.98-0.989; our fill rate needs queue_late | R-2026-10-06 lead E; live test `lab/queue_late.py` (laptop, to 21 Oct, summary `lab/results/queue-late-summary.json`) |
| 5 | MLB lead 7+ after 8 innings (`mlb_lead7`) | 0 so far | 0 | ~3 of 81 games qualify | **NOT YET**: too rare to judge | shadow, analyst |
| 6 | Faster result source (ESPN tennis, official MLB/NHL feeds) | ESPN tennis ~140 s ahead, agrees 11/11 | - | 0 shares left at that moment | **NO as a speed edge, YES as a safety check** (tennis) | `lab/tennis_end_race.py`, `lab/official_end_recorder.py`, laptop |
| 7 | Slow markets (elections, small events) | 21/21 right (Quebec) | 0 | $5-550 per market | **NOT YET**: small money | R-2026-10-06 tester |
| 8 | Football, lead of 2+ goals at minute 88+ (owner idea 2026-10-07) | 22 of 62 lead-2 matches had 5+ shares at 0.95-0.99 in 45 days (lead 3+: 1 of 46) | 28 of 3,099 lead-2 leaders failed (0.9%); 1 of 62 in Part B (PSG-Lille, with fills); lead 3+: 0 of 1,970 | far below 200 | **NO**: lead 2 loses 1 in 110; lead 3+ is safe but the cheap fills do not exist | `lab/late_football.py`; [[R-2026-10-08]] |
| 9 | Stock/ETF far strikes, last hour (`lab/stock_ladder_shadow.py`) | 0 real (18 smoke-test fills) | 0 | tiny | **NOT YET**: tape 332 fills, 0 losers; real recorder run Fri 9 Oct | R-2026-10-08 |
| 10 | Tennis "match is over" resting bid on the winner (0.99-0.998, singles, 2 of 3 score sources) | 0 real; model: 35-45% of ~50 matches/day fill even with 60 s delay and 25% of queue (353 matches, 7 days) | 0 modelled | ~$0.9/day | **NOT YET**: rival bots and real queue unmeasured; needs laptop `tennis_end_bids.py record` | [[R-2026-10-09]], `lab/tennis_t1_stress.py` |

**Verdict words:** YES = real fills, 0 losses, enough cases to trust. NO = loses or never fills. NOT YET = not enough data.
A "YES" needs **200+ pretend fills with 0 losses**, the same bar as [[32-Go-Live-Checklist]] (50 fills with 0 losses
would only prove the loss rate is below ~6%). Owner's bar (2026-10-08): fills needed = larger of 200 and 3 / (1 - price), 0 losses; win rate above price + fees (0.99 needs 300, 0.999 needs 3,000).

## Changes
- 2026-10-09 17:00: row 10 added (tennis match-over bid, stress test: NOT YET); row 4 cannot reach 200 by 21 Oct ([[R-2026-10-09]]).
- 2026-10-08 17:00: row 4 queue_late 9 games (9/9 at 0.98, 0 losers); row 9 added, recorder dry run OK ([[R-2026-10-08]]).
- 2026-10-08: row 8 tested (cloud one-off, 16,020 matches + 45 days of trades): NO. Also, 1-goal leads fail 14% at minute 88, not 3-5% ([[R-2026-10-08]]).
- 2026-10-08: owner yes: bar = win rate above price + fees, fills needed = larger of 200 and 3 / (1 - price), 0 losses (replaces 100% / 98.5%).
- 2026-10-07 23:15: row 8 added (owner idea: late football with a 2+ goal lead; 1-goal leads excluded, ~3-5% still fail to win).
- 2026-10-07 17:00: row 4 tested on 114 US games: 0 losers in 1,319 sells into 0.98+ bids, but mostly at 0.999; fill rate unmeasured ([[R-2026-10-07]]).
- 2026-10-07 16:45: owner: row 4 is the main job until 21 Oct; row 3 background only.
- 2026-10-07 10:50: rows 1-3 and 6 updated from overnight tests ([[R-2026-10-07]]).
- 2026-10-07: YES bar raised from 50 to 200+ fills to match the Go-Live Checklist (50 was a mistake).
- 2026-10-07: created (laptop session, owner yes). Numbers from shadow data, R-2026-10-06 and R-2026-10-07.
