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

## Road to 1 November (owner, 2026-10-05): goes first

Real money starts **1 Nov 2026 with $20** (plan: [[24-Task-List]], "Road to real money"). Lab priorities until then: (1) best-wallet copy study for US sports after the end (#10/#14): sports, seconds after the end, sizes, fills/day at ~0.99; (2) Flashscore lag test (#20); (3) from mid-October, red-team the chosen rule and its whole buy path.

## Owner's focus for the next runs (set 2026-10-05)

The lab reads this first and puts these ahead of its own picks. Ideas that need **no speed race** come first.

1. **"Almost certain" moments (new, owner 2026-10-05):** the safe rules made 0 buys because the 0.96-0.995 band empties ~74 s before Polymarket's score says "ended" and ~40 s before the free Sports WebSocket does (R-2026-10-05). Fast bots buy at match point / last round. Using the PC's score log (`code/data/shadow/daily/`, both books at every score change), end windows and the 7 losses, find per sport the in-play situations (tennis: sets and games ahead, serving; CS2/Valorant/LoL: maps and rounds ahead; US sports: lead and time left) where (a) shares were still for sale in our band and (b) the leader never lost, with enough cases to bound the loss rate. Pass bar: loss rate clearly below the ~1 in 30 that breaks even at 0.97 (aim for 1 in 1,000+), checked on public history too (#15 found baseball 9th-inning leads of 4+ still lose ~1 in 300-1,000). Report the rule, the count, and how many shares/day it would buy. Red team it before any shadow rule. **Answered 2026-10-05 ([[R-2026-10-05]]):** in-play prices are fair (tennis, CS2, LoL/Dota, NFL states in our band lose 1 in 6 to 1 in 70). Only MLB lead 7+ after 8 innings survives (0 in 5,408 games); supply ~3 of 81 games; shadow-rule candidate.
2. **#20 Flashscore lag test (owner 2026-10-05):** in the cloud, never on the owner's PC, watch ~20 live matches on Flashscore (tennis and CS2 first) and log the moment it shows the final point/round and "finished", next to the Polymarket Sports WebSocket (`wss://sports-api.polymarket.com/ws`) and the winner's book. Pass bar: Flashscore at least 60-90 s ahead of Polymarket's score field AND ahead of the moment our 0.96-0.995 band empties; otherwise drop it. Also note how often its score was corrected. Measuring only; no browser robot is built for the bot unless it passes.
3. **#11 Markets made certain by another result** (e.g. a map market after the series is already won): do they stay cheap, and what do the rules say about matches not played?
4. **#18 Paid UMA proposer:** whitelist path, then the 3-day shadow proposer log.
5. Still one brand-new out-of-the-box angle per run.

**Side task (owner 2026-10-06, keep aside, small; do it once in the next research run, then re-check monthly):
MCP servers that would really help PolySweeper.** Search GitHub (and the official MCP registry / Anthropic's
lists) for MCP servers useful here: faster live sports results, sports data, Polymarket/prediction-market *read-only*
data, market news, data analysis. Only list ones that are **popular and trusted**: high GitHub stars (aim 1,000+; say
the number), many users, updated in the last 3 months, a known owner (official company, Anthropic, or well-known
developer), open code. **Reject** anything that places orders, holds wallet keys or private keys, needs a paid plan
(note any price), or looks new/unknown/scammy. Write a short table in the day's note (name, link, stars, last update,
owner, what it gives us, free or paid, verdict) and one line on the idea board. **Research only: never install;**
the owner decides.

## Idea board

Status: **new** → **researching** → **testing** → **promising** / **rejected**.
The lab updates this table every day.

| # | Idea | Why it could be near zero-loss | Main risk | Status |
|---|---|---|---|---|
| 1 | **Complete set**: buy YES and NO of the same market when together they cost under $1, then merge them into $1 at once | Payout does not depend on the result; merging returns $1 immediately | One side fills and the other does not; rare and contested by bots | rejected (2026-10-03): impossible by design, one shared book; 0 of 6,935 markets under $1 ([[R-2026-10-03]]) |
| 2 | **Multi-outcome basket**: in a market with many options (e.g. tournament winner), buy every YES when they add up to under $1 (or the NO equivalent) | Exactly one option wins, so the basket always pays $1 | Missing or "other" outcomes, voids, many legs to fill | rejected (2026-10-03): 0 of 990 near-term events under $1 after fees; hidden "Other" slots; one-leg fills ([[R-2026-10-03]]) |
| 3 | **Logical gaps between related markets** (e.g. "team wins series" vs "wins 2-0" + "wins 2-1"; match vs map markets) | Prices that break logic can be hedged so every result pays | Different rules or timing between the markets | new (2026-10-03) |
| 4 | **Known but not settled, outside sports**: crypto up/down (result known from the public price at the close), weather, economic releases, elections | Same idea as V1 but maybe less crowded than sports | Source used for settlement differs from ours; still crowded | researching (2026-10-03): weather part tested and rejected (see #13); crypto, economic releases still open |
| 5 | **UMA waiting period**: after a result is proposed, there are about 2 hours before it is final; buy winners at 0.995-0.999 during that time | Result already proposed publicly; only a dispute can change it | Disputes; small profit; capital locked 2 h | rejected (2026-10-05): ~5 markets/day trade the proposed winner at 0.985 or less in the 2 h window, but overturns happen (loser at 0.999 once); 73% of fills in first 30 min ([[R-2026-10-05]]) |
| 6 | **Late band with faster information** (0.995-0.999 right after the result) | Result known | 1 of 32 matches had shares; bots faster than Polymarket's score | testing (live feed on PC, note 29) |
| 7 | **Tennis "practically locked"** during play (e.g. a set up and 5-1) | Comebacks from there are very rare | Rare comebacks, retirements; price already near 0.99 | testing (score log on PC, note 29) |
| 8 | **Liquidity rewards / maker rebates**: get paid by Polymarket for resting orders | Income from rewards, not from guessing results | Getting filled at a bad moment; program rules change | rejected (2026-10-05): $156k/day pool but two-sided quotes get picked off on news; no near-zero-risk version ([[R-2026-10-05]]) |
| 9 | **Holding rewards** on some long markets | Yield for holding | Program details; capital locked for long | new (2026-10-03) |
| 10 | **Learn from profitable sweeper wallets** (Data API: who buys at 0.99+, when, how big, which markets) | Shows where safe flow really is and how fast it must be | Copying the timing may need their speed | **promising lead** (2026-10-04): every timed loss came before the end (0 of 3,856 after); best wallet buys US sports at 0.99 with 0.22% losses ([[R-2026-10-04-wallets]]) |
| 11 | **Markets made certain by another result** (e.g. a map market after the series is already won; "to qualify" after a decisive match) | Outcome fixed by rules once the other result is in | Rule text (not played = void 50/50?) | merged into #17 (2026-10-04) |
| 12 | **Faster or earlier result sources** (official league feeds, sportsbook data, stream delays) | Know the result before the 0.999 bots | Cost, reliability, still too slow from a home PC | new (2026-10-03) |
| 13 | **Weather dead ranges**: buy NO on a temperature range the station has already passed | Daily high can only go up, so a passed range is certain to lose | "No data → lowest range wins" rule; revisions; nothing for sale | rejected (2026-10-03): passed ranges have no NO sellers below 0.999 (166 of 166 checked); ~$7.50/day taken by others after 17:00 ([[R-2026-10-03]]) |
| 14 | **US sports near or after the end at 0.99** (MLB, NFL, college football, NHL) | Slower, less crowded finishes; 0.99 still bought just after the end; one wallet 3 losses in 1,344 | Rare comebacks if bought during play; rain/overtime/postponement rules; shadow mode does not watch these leagues yet | new (2026-10-04) ([[R-2026-10-04-wallets]]) |
| 15 | **Own win-probability model** (US sports first): buy only when our calculated chance clearly beats the price | Edge is measured, not hoped for; picks only situations that history says never lose | Model wrong in rare situations; rules (rain, overtime); small sample | parked (2026-10-04): even 9th inning, 2 outs, lead 4+ loses ~1 in 300-1,000; at 0.99 that is ~100 wins per loss ([[R-2026-10-04]]) |
| 16 | **Crypto Up/Down locked by math**: last seconds of the 60-second settlement average | Most of the average is already fixed; automatic settlement in ~53 s, no disputes | Big price jumps; bots at 0.999 within milliseconds; home PC too slow | rejected (2026-10-04): never locked by arithmetic; stand-in price wrong 7 of 150; neighbour bucket lost 4.7% ([[R-2026-10-04]]) |
| 17 | **Locked lines**: side markets (totals, team totals, first-5/first-half, "run in 1st inning") certain mid-game once the score passes the line | Arithmetic: runs/points can't be removed once they stand; early settlement (20-45 min) | Cancelled game = 50/50; wrong game matched; score reversed on review; almost nothing left at 0.99 after the safe moment | rejected (2026-10-04): 2,270/2,270 settled as arithmetic said, but nothing left to buy: live NFL test, 0 shares for sale on the winner in 154 of 154 snapshots, buyers already at 0.99-0.992 ([[R-2026-10-04]]) |
| 18 | **Paid UMA proposer**: propose the correct result on slow markets and earn the reward ($3.5-5 non-sports) | No trading, no speed race; answers from official sources | $250-500 deposit lost on a wrong/early proposal; whitelist needed; competition from ~177 proposers | testing (2026-10-05): shadow proposer log first; whitelist path is the first blocker ([[R-2026-10-05]]) |
| 19 | **ML model as an extra veto** (owner idea 2026-10-05): a small model trained on large public history (e.g. years of point-by-point tennis) that can only block a buy, never trigger one | Catches warning signs simple rules miss (momentum, serve, map pool) | Too little of our own data (~240 trades, 7 losses); rare events are where models fail; black box | parked (2026-10-05): only after focus #1 (simple "almost certain" rules) has results; standard library only |
| 20 | **Fast free score sites as a result source** (Flashscore first; later GRID Open Access, LoL live stats): a browser robot or feed reader that sees the end before Polymarket | Free; Flashscore is often seconds behind the real match | Unofficial, blocks bots, breaks on page changes, ~0.3-0.5 GB memory, not standard library; band empties ~74 s before Polymarket's score, so the end signal may still be too late | testing (2026-10-05): cloud lag test first, owner focus #2 |
| 21 | **Slow-arena sweep** (elections first, then box-office/data-index markets): buy the decided side when an official count is uncatchable, while humans still sell at 0.96-0.995 for ~2 h | No speed race; answer fixed by a public number; 0 losses in ~125 sampled markets | Late/mail ballots, recount, runoff, wrong race, revised numbers; more bots on Nov 3; lumpy | new (2026-10-06) ([[R-2026-10-06]]) |
| 22 | **Long-tail league atlas**: leagues with no Polymarket result feed (lower soccer, cricket, table tennis) | Asks may linger where bots lack a feed | Abandoned match 50/50, score correction | new (2026-10-06) |
| 23 | **Soccer locked lines** (Over / both-teams-score after goals) | Arithmetic once the score passes the line | VAR reversal, abandoned match; NFL version had nothing left to buy | new (2026-10-06), low prior |
| 24 | **Safe-state atlas part 2** (NBA, NHL, soccer late, LoL/Valorant) | Loss under 1 in 1,000 states | In-play prices were fair in tennis/CS2/NFL | new (2026-10-06), low prior |
| — | Resting buy orders before the end (option 2) | — | Fills mostly when we are wrong | rejected (2026-10-03) |
| — | Buying on price during play (price-only rule) | — | Loss rate matches the price: no edge | rejected (2026-10-03) |

## Daily research notes

Folder `Research/`, one note per day: `R-<date>`. Newest first:

- [[R-2026-10-05]] — daily run + evening "almost certain moments" study (only MLB 7+ after 8 survives): Overwatch Bo3/BO5 score bug fixed; UMA window and liquidity rewards rejected; new #18 paid UMA proposer (shadow test)
- [[R-2026-10-04]] — daily run: locked lines (2,270/2,270 correct, but ~nothing at 0.99 after the safe moment); crypto rejected; win model parked; lab made leaner
- [[R-2026-10-04-wallets]] — early run (owner asked): profitable wallets; 0 losses after the end in 3,856 buys; US sports lead (idea #14)
- [[R-2026-10-03]] — first run: complete set and baskets rejected; weather dead ranges tested and rejected; PC healthy

## Where to change what the lab does

- Ask in any Claude Code session ("change the lab to ..."). The routines can be paused or changed
  under Routines in claude.ai/code.
- The lab never places orders and never touches a wallet. Research and pretend trades only.
