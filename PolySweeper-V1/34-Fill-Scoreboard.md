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
| 1 | Buy during play at 0.96-0.99 (`price_only`) | 370 settled | 12 (3.2%) | +$0.35 in total | **NO** (comebacks; kept only as a yardstick) | shadow, analyst |
| 2 | Buy after the result at 0.96-0.995 (`score`, `confirmed`) | 1 (score) | 0 | +$0.03 | **NOT YET**: almost never fills | shadow, analyst |
| 3 | Rest a buy at 0.999 once the match is over | test running | - | pool ~$680/day for all bots (Oct 5-6) | **NOT YET**: queue is long (one MLB game ~1M shares) | `lab/queue999.py` on the laptop; summary in `lab/results/queue999-summary.json` (every 3 h); report 2026-10-08 |
| 4 | Rest buys at 0.98+ in the last 30 min of US games | 1,688 public fills in 270 games | 3 on losers (0.2%), 0 in moneyline | ? | **NOT YET**: needs a game clock and a shadow test | R-2026-10-06 lead E |
| 5 | MLB lead 7+ after 8 innings (`mlb_lead7`) | 0 so far | 0 | ~3 of 81 games qualify | **NOT YET**: too rare to judge | shadow, analyst |
| 6 | Faster result source (ESPN tennis, official MLB/NHL feeds) | test running | - | ? | **NOT YET**: helps 2 and 3 if faster | `lab/tennis_end_race.py`, `lab/official_end_recorder.py`, laptop |
| 7 | Slow markets (elections, small events) | 21/21 right (Quebec) | 0 | $5-550 per market | **NOT YET**: small money | R-2026-10-06 tester |

**Verdict words:** YES = real fills, 0 losses, enough cases to trust. NO = loses or never fills. NOT YET = not enough data.
A "YES" needs **200+ pretend fills with 0 losses**, the same bar as [[32-Go-Live-Checklist]] (50 fills with 0 losses
would only prove the loss rate is below ~6%). Owner's bar: 100% wins, never below 98.5%.

## Changes
- 2026-10-07: YES bar raised from 50 to 200+ fills to match the Go-Live Checklist (50 was a mistake).
- 2026-10-07: created (laptop session, owner yes). Numbers from shadow data, R-2026-10-06 and R-2026-10-07.
