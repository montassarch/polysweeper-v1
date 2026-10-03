---
title: Research Hub (PolySweeper Lab)
tags: [polysweeper, research, lab, ideas]
created: 2026-10-03
---

# Research Hub: the PolySweeper Lab

Back to [[V1-Home]] · Task list: [[24-Task-List]] · Why we look for new ideas: [[26-First-Shadow-Results]]

An automated research team that works every day, writes its findings here, and never trades.

## The target: "scraps"

About **$0.01 or more per trade, 40-50 trades a day, zero losses**.

- The minimum order is 5 shares. To make $0.01 on 5 shares, you buy at 0.998 or less (after fees).
- One loss at 0.998 wipes out about 500 wins. So an idea only counts if a loss is *structurally*
  near impossible, not just rare.
- At 5 shares, 50 trades a day make about $0.50. More profit needs bigger orders, which needs
  enough shares for sale. So every test measures **how many shares** are really available.

## The team

| Agent | Job |
|---|---|
| **Lead** (the daily routine) | Runs the team, writes the daily note, updates this board, saves to GitHub |
| **ps-researcher** | The most important one: searches the web, open-source bots, papers and Polymarket's own data for new approaches; writes "idea cards" |
| **ps-red-team** | Attacks every idea: how could it lose money? Verdict: reject / test with guards / promising |
| **ps-tester** | Measures ideas on real Polymarket data (small scripts in the `lab` folder, outside `code`, so the PC is not restarted) |
| **ps-analyst** | Reads the shadow-mode data from the owner's PC: results, live feed, score log, errors |
| **ps-fixer** | Health check: tests, errors, is the PC still sending data? Fixes bugs under strict safety rules |

Role files: `.claude/agents/ps-*.md` in the repo.

**Schedule (Tunisia time):**
- Every day at 05:17: full lab run, with all agents and a new daily note.
- Every day at 17:43: health check (fixer and analyst).

The owner gets a short summary on their phone after each run.

## Idea board

Status: **new** → **researching** → **testing** → **promising** / **rejected**.
The lab updates this table every day.

| # | Idea | Why it could be near zero-loss | Main risk | Status |
|---|---|---|---|---|
| 1 | **Complete set**: buy YES and NO of the same market when together they cost under $1, then merge them into $1 at once | Payout does not depend on the result; merging returns $1 immediately | One side fills and the other does not; rare and contested by bots | rejected (2026-10-03): impossible by design, one shared book; 0 of 6,935 markets under $1 ([[R-2026-10-03]]) |
| 2 | **Multi-outcome basket**: in a market with many options (e.g. tournament winner), buy every YES when they add up to under $1 (or the NO equivalent) | Exactly one option wins, so the basket always pays $1 | Missing or "other" outcomes, voids, many legs to fill | rejected (2026-10-03): 0 of 990 near-term events under $1 after fees; hidden "Other" slots; one-leg fills ([[R-2026-10-03]]) |
| 3 | **Logical gaps between related markets** (e.g. "team wins series" vs "wins 2-0" + "wins 2-1"; match vs map markets) | Prices that break logic can be hedged so every result pays | Different rules or timing between the markets | new (2026-10-03) |
| 4 | **Known but not settled, outside sports**: crypto up/down (result known from the public price at the close), weather, economic releases, elections | Same idea as V1 but maybe less crowded than sports | Source used for settlement differs from ours; still crowded | researching (2026-10-03): weather part tested and rejected (see #13); crypto, economic releases still open |
| 5 | **UMA waiting period**: after a result is proposed, there are about 2 hours before it is final; buy winners at 0.995-0.999 during that time | Result already proposed publicly; only a dispute can change it | Disputes; small profit; capital locked 2 h | new (2026-10-03) |
| 6 | **Late band with faster information** (0.995-0.999 right after the result) | Result known | 1 of 32 matches had shares; bots faster than Polymarket's score | testing (live feed on PC, note 29) |
| 7 | **Tennis "practically locked"** during play (e.g. a set up and 5-1) | Comebacks from there are very rare | Rare comebacks, retirements; price already near 0.99 | testing (score log on PC, note 29) |
| 8 | **Liquidity rewards / maker rebates**: get paid by Polymarket for resting orders | Income from rewards, not from guessing results | Getting filled at a bad moment; program rules change | new (2026-10-03); next deepening question (sports rebateRate 0.15) |
| 9 | **Holding rewards** on some long markets | Yield for holding | Program details; capital locked for long | new (2026-10-03) |
| 10 | **Learn from profitable sweeper wallets** (Data API: who buys at 0.99+, when, how big, which markets) | Shows where safe flow really is and how fast it must be | Copying the timing may need their speed | new (2026-10-03) |
| 11 | **Markets made certain by another result** (e.g. a map market after the series is already won; "to qualify" after a decisive match) | Outcome fixed by rules once the other result is in | Rule text (not played = void 50/50?) | new (2026-10-03) |
| 12 | **Faster or earlier result sources** (official league feeds, sportsbook data, stream delays) | Know the result before the 0.999 bots | Cost, reliability, still too slow from a home PC | new (2026-10-03) |
| 13 | **Weather dead ranges**: buy NO on a temperature range the station has already passed | Daily high can only go up, so a passed range is certain to lose | "No data → lowest range wins" rule; revisions; nothing for sale | rejected (2026-10-03): passed ranges have no NO sellers below 0.999 (166 of 166 checked); ~$7.50/day taken by others after 17:00 ([[R-2026-10-03]]) |
| — | Resting buy orders before the end (option 2) | — | Fills mostly when we are wrong | rejected (2026-10-03) |
| — | Buying on price during play (price-only rule) | — | Loss rate matches the price: no edge | rejected (2026-10-03) |

## Daily research notes

Folder `Research/`, one note per day: `R-<date>`. Newest first:

- [[R-2026-10-03]] — first run: complete set and baskets rejected; weather dead ranges tested and rejected; PC healthy

## Where to change what the lab does

- Ask in any Claude Code session ("change the lab to ..."). The routines can be paused or changed
  under Routines in claude.ai/code.
- The lab never places orders and never touches a wallet. Research and pretend trades only.
