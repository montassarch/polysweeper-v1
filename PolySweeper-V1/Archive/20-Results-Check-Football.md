---
title: Results Check - Football (ESPN)
tags: [polysweeper, results, football, backtest]
created: 2026-10-01
---

> **Archived 2026-10-07: history, may be outdated.** Current state: [[V1-Home]], [[24-Task-List]], [[34-Fill-Scoreboard]].

# Results check: football against ESPN

Back to [[V1-Home]] · Dota 2 version: [[19-Results-Check-Dota]] · Data sources: [[12-Data-Sources]]

Code: `code/polysweeper/results_espn.py`, `code/polysweeper/football_check.py`.

## Sources tried (no key, no sign-up)

| Source | Result |
|---|---|
| **ESPN public scoreboard** | Works. Full-time status, score, winner, stoppage clock (e.g. 90'+5'). Unofficial feed: may change without notice. |
| TheSportsDB (free test key) | Works but returns only ~3 random matches a day. Useless on the free key (~$9/month for full). |
| OpenLigaDB | Works, free and solid, but German leagues only. |
| football-data.org | Did not work for the owner (needs a key). Not needed now. |

## Matching 3,442 Polymarket football markets (9 leagues, ~280 days)

- **2,644 matched, and the winner agreed on all 2,644** (after two fixes below).
- 784 not matched (club names written differently, e.g. "Bayern Munchen" vs
  "Bayern Munich"). Unmatched = skipped, which is safe.
- 12 skipped because the match went to extra time or penalties.
- 2 skipped because the club name fitted both teams.

## Two real traps found (now fixed, and rules for the live bot)

1. **Wrong-match trap:** "Paris Saint-Germain" was matched to "Paris FC". The
   checker read the wrong team's result. Rule: **if a name fits both teams,
   skip.** This is exactly the "wrong mapping = wrong bet" risk.
2. **Extra-time trap:** in a Europa League knockout, Polymarket paid on the
   **90-minute result (a draw)**, while ESPN showed the **after-extra-time**
   result (a Bologna win). Rule: **football markets settle on the 90-minute
   result; skip anything that went to extra time or penalties.** Also, the
   buying moment for these markets is the 90-minute whistle, not the end of
   extra time.

## What the winner's price does after the final whistle (mid prices)

End time is estimated: kickoff + 45 + 15 (half time) + 45 + 2 + second-half
stoppage from ESPN's clock. Could be a few minutes off.

| Minutes after estimated end | below 0.96 | 0.96 to 0.995 | above 0.995 | median |
|---|---|---|---|---|
| 0 | 1,126 | 610 | 905 | 0.981 |
| 2 | 805 | 675 | 1,161 | 0.995 |
| 5 | 307 | 540 | 1,794 | 1.000 |
| 10 | 41 | 194 | 2,406 | 1.000 |

- Price passes 0.995 a median **2.2 minutes** after the estimated whistle.
- Polymarket pays out a median **157 minutes** after the whistle.
- So the football "after the whistle" window is **short (a few minutes)**,
  shorter than Dota 2 (about 4 minutes). The bot would need to detect the
  final whistle quickly; ESPN's own delay is not measured yet.

## Honest limits

- ESPN is unofficial and only **one** strong football source; the bot's rule is
  that two independent sources must agree. Free second source exists only for
  German leagues (OpenLigaDB). Elsewhere: Polymarket's own score feed (not
  independent) or a cheap paid source later.
- Mid prices; no depth data. Shadow mode measures real asks and availability.
- End times are estimates; shadow mode's `ended` flag will give real ones.

## Next steps

- [x] Plug ESPN (football) and OpenDota (Dota 2) into shadow mode so it tests
      the real rule: buy only after the result is confirmed.
- [x] Add name aliases (Bayern, Inter, etc.) to raise the match rate.
- [ ] Measure ESPN's delay (minutes from whistle to "full time" in the feed).
