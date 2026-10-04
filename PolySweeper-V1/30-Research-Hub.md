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

## Owner's focus for the next runs (set 2026-10-04)

The lab reads this first and puts these ahead of its own picks. Ideas that need **no speed race** come first.

1. **#15 Our own win probability for US sports** (builds on #10 and #14, [[R-2026-10-04-wallets]]): find public win-probability data or tables (baseball by inning, runs ahead, outs; American football by score gap and time left; hockey by goals ahead and time left). Rebuild the game situation at each 0.99 buy of the best US-sports wallet (0x4dDC7068...). Which situations never lose, and is the price there below the true chance? Buy only when our chance clearly beats the price plus fee plus a margin.
2. **#16 Crypto "Up or Down" markets locked by math:** they settle on a 60-second average price (Chainlink), automatically about 53 s after the window, with no UMA dispute. In the final seconds most of the average is already fixed: how often is the result mathematically certain before the end, is anything still for sale below 0.999 then, and how fast do bots clear it? Measure on public data and live books.
3. **#5 UMA waiting period:** after a result is proposed, are winners still for sale at 0.995-0.998 during the ~2 hours before it is final? How many shares, and how often was a proposal disputed or overturned?
4. **#11 Markets made certain by another result** (e.g. a map market after the series is already won): do they stay cheap, and what do the rules say about matches not played?
5. Still one brand-new out-of-the-box angle per run.

## Idea board

Status: **new** → **researching** → **testing** → **promising** / **rejected**.
The lab updates this table every day.

| # | Idea | Why it could be near zero-loss | Main risk | Status |
|---|---|---|---|---|
| 1 | **Complete set**: buy YES and NO of the same market when together they cost under $1, then merge them into $1 at once | Payout does not depend on the result; merging returns $1 immediately | One side fills and the other does not; rare and contested by bots | rejected (2026-10-03): impossible by design, one shared book; 0 of 6,935 markets under $1 ([[R-2026-10-03]]) |
| 2 | **Multi-outcome basket**: in a market with many options (e.g. tournament winner), buy every YES when they add up to under $1 (or the NO equivalent) | Exactly one option wins, so the basket always pays $1 | Missing or "other" outcomes, voids, many legs to fill | rejected (2026-10-03): 0 of 990 near-term events under $1 after fees; hidden "Other" slots; one-leg fills ([[R-2026-10-03]]) |
| 3 | **Logical gaps between related markets** (e.g. "team wins series" vs "wins 2-0" + "wins 2-1"; match vs map markets) | Prices that break logic can be hedged so every result pays | Different rules or timing between the markets | new (2026-10-03) |
| 4 | **Known but not settled, outside sports**: crypto up/down (result known from the public price at the close), weather, economic releases, elections | Same idea as V1 but maybe less crowded than sports | Source used for settlement differs from ours; still crowded | researching (2026-10-03): weather part tested and rejected (see #13); crypto, economic releases still open |
| 5 | **UMA waiting period**: after a result is proposed, there are about 2 hours before it is final; buy winners at 0.995-0.999 during that time | Result already proposed publicly; only a dispute can change it | Disputes; small profit; capital locked 2 h | new (2026-10-03); 2026-10-04: sports/crypto settle 20-55 min after the result, no 2 h wait seen ([[R-2026-10-04]]) |
| 6 | **Late band with faster information** (0.995-0.999 right after the result) | Result known | 1 of 32 matches had shares; bots faster than Polymarket's score | testing (live feed on PC, note 29) |
| 7 | **Tennis "practically locked"** during play (e.g. a set up and 5-1) | Comebacks from there are very rare | Rare comebacks, retirements; price already near 0.99 | testing (score log on PC, note 29) |
| 8 | **Liquidity rewards / maker rebates**: get paid by Polymarket for resting orders | Income from rewards, not from guessing results | Getting filled at a bad moment; program rules change | new (2026-10-03); next deepening question (sports rebateRate 0.15) |
| 9 | **Holding rewards** on some long markets | Yield for holding | Program details; capital locked for long | new (2026-10-03) |
| 10 | **Learn from profitable sweeper wallets** (Data API: who buys at 0.99+, when, how big, which markets) | Shows where safe flow really is and how fast it must be | Copying the timing may need their speed | **promising lead** (2026-10-04): every timed loss came before the end (0 of 3,856 after); best wallet buys US sports at 0.99 with 0.22% losses ([[R-2026-10-04-wallets]]) |
| 11 | **Markets made certain by another result** (e.g. a map market after the series is already won; "to qualify" after a decisive match) | Outcome fixed by rules once the other result is in | Rule text (not played = void 50/50?) | merged into #17 (2026-10-04) |
| 12 | **Faster or earlier result sources** (official league feeds, sportsbook data, stream delays) | Know the result before the 0.999 bots | Cost, reliability, still too slow from a home PC | new (2026-10-03) |
| 13 | **Weather dead ranges**: buy NO on a temperature range the station has already passed | Daily high can only go up, so a passed range is certain to lose | "No data → lowest range wins" rule; revisions; nothing for sale | rejected (2026-10-03): passed ranges have no NO sellers below 0.999 (166 of 166 checked); ~$7.50/day taken by others after 17:00 ([[R-2026-10-03]]) |
| 14 | **US sports near or after the end at 0.99** (MLB, NFL, college football, NHL) | Slower, less crowded finishes; 0.99 still bought just after the end; one wallet 3 losses in 1,344 | Rare comebacks if bought during play; rain/overtime/postponement rules; shadow mode does not watch these leagues yet | new (2026-10-04) ([[R-2026-10-04-wallets]]) |
| 15 | **Own win-probability model** (US sports first): buy only when our calculated chance clearly beats the price | Edge is measured, not hoped for; picks only situations that history says never lose | Model wrong in rare situations; rules (rain, overtime); small sample | parked (2026-10-04): even 9th inning, 2 outs, lead 4+ loses ~1 in 300-1,000; at 0.99 that is ~100 wins per loss ([[R-2026-10-04]]) |
| 16 | **Crypto Up/Down locked by math**: last seconds of the 60-second settlement average | Most of the average is already fixed; automatic settlement in ~53 s, no disputes | Big price jumps; bots at 0.999 within milliseconds; home PC too slow | rejected (2026-10-04): never locked by arithmetic; stand-in price wrong 7 of 150; neighbour bucket lost 4.7% ([[R-2026-10-04]]) |
| 17 | **Locked lines**: side markets (totals, team totals, first-5/first-half, "run in 1st inning") certain mid-game once the score passes the line | Arithmetic: runs/points can't be removed once they stand; early settlement (20-45 min) | Cancelled game = 50/50; wrong game matched; score reversed on review; almost nothing left at 0.99 after the safe moment | rejected (2026-10-04): 2,270/2,270 settled as arithmetic said, but nothing left to buy: live NFL test, 0 shares for sale on the winner in 154 of 154 snapshots, buyers already at 0.99-0.992 ([[R-2026-10-04]]) |
| — | Resting buy orders before the end (option 2) | — | Fills mostly when we are wrong | rejected (2026-10-03) |
| — | Buying on price during play (price-only rule) | — | Loss rate matches the price: no edge | rejected (2026-10-03) |

## Daily research notes

Folder `Research/`, one note per day: `R-<date>`. Newest first:

- [[R-2026-10-04]] — daily run: locked lines (2,270/2,270 correct, but ~nothing at 0.99 after the safe moment); crypto rejected; win model parked; lab made leaner
- [[R-2026-10-04-wallets]] — early run (owner asked): profitable wallets; 0 losses after the end in 3,856 buys; US sports lead (idea #14)
- [[R-2026-10-03]] — first run: complete set and baskets rejected; weather dead ranges tested and rejected; PC healthy

## Where to change what the lab does

- Ask in any Claude Code session ("change the lab to ..."). The routines can be paused or changed
  under Routines in claude.ai/code.
- The lab never places orders and never touches a wallet. Research and pretend trades only.
