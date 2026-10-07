---
title: Research Hub (PolySweeper Lab)
tags: [polysweeper, research, lab, ideas]
created: 2026-10-03
---

# Research Hub: the PolySweeper Lab

Back to [[V1-Home]] · Task list: [[24-Task-List]] · Why we look for new ideas: [[26-First-Shadow-Results]]

An automated research team that works every day, writes its findings here, and never trades.

## The target

- **Owner's bar (2026-10-06): 100% wins, never below 98.5%.** Break-even win rate is about the buy price, so
  98.5% only profits when buying at about 0.98 or lower; at 0.999 a single loss wipes out ~1,000 wins.
- An idea only counts if a loss is *structurally* near impossible, not just rare, and it must get **real fills**
  (enough shares, not taken first by faster bots).
- Minimum order 5 shares. Profit grows only with order size and number of matches.

## Until 21 October: one question (owner 2026-10-07)

**"Which method gets filled with zero losses?"** Table and verdicts: [[34-Fill-Scoreboard]], updated daily by the
tester; the 17:00 phone summary starts with it. Every run works on a scoreboard row first.

- **21 Oct:** a method with a YES (200+ pretend fills, 0 losses, the Go-Live bar) goes to a tiny real-money test, owner decides.
  None: rethink the approach.
- **1 Nov:** first real money, $20, only with the owner's yes (plan: [[24-Task-List]], "Road to real money").
- Facts as of 7 Oct: buying during play does not pay; cheap asks after a result are gone within seconds;
  the safe after-result money is at 0.999 and goes to resting buy orders, but the 0.999 queue is long
  ([[R-2026-10-07]], test `lab/queue999.py`, summary in `lab/results/queue999-summary.json`).

## Owner's focus (serves the question above)

1. **Second result source for every sport we would trade (owner 2026-10-06; now required for 0.999):**
   Polymarket's score is wrong ~1 in 4,000, and at 0.999 one loss costs ~1,000 wins. Football (ESPN), Dota 2
   (OpenDota) done; tennis (ESPN, test running on the laptop), MLB/NHL official feeds (recorder running).
   Still needed: CS2, LoL, Valorant and the rest. For each source: free or paid (price), key needed, terms allow
   automated use, coverage of Polymarket's matches, how fast it says "finished". Research only; nothing paid
   without the owner's yes.
2. **Resting (maker) orders:** queue size at 0.999 and 0.98-0.99, how fast it refills, who gets filled, and
   when fills happen on the side that then loses (adverse selection). Scoreboard rows 3 and 4.
3. One brand-new angle per run, only if it answers the question.

Parked until after 21 Oct: #18 paid UMA proposer, MCP servers side task (done 2026-10-06, re-check monthly,
see [[R-2026-10-06]]). Answered: "almost certain" in-play moments (only MLB lead 7+ after 8 survives, now
shadow rule `mlb_lead7`); Flashscore lag (rejected, #20); markets certain by another result (merged into #17).

## The team

Split schedule, one agent per run (Tunisia time): 01:00 analyst, 05:00 ideas (Mon + Thu), 09:00 researcher,
13:00 red team (odd days), 17:00 tester + phone summary, 21:00 health check (even days). ps-reviewer checks every
`code/` change before it goes to main. Steps: `.claude/lab-run.md`; role files: `.claude/agents/ps-*.md`.

## Idea board

Status: **new** → **researching** → **testing** → **promising** / **rejected**.
The lab updates this table every day. Every rejected or parked idea also goes into [[33-Rejected-Ideas]].

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
| 10 | **Learn from profitable sweeper wallets** (Data API: who buys at 0.99+, when, how big, which markets) | Shows where safe flow really is and how fast it must be | Copying the timing may need their speed | parked (2026-10-06): best wallet is a maker plus fast in-play sniper, nothing copyable ([[R-2026-10-06]]) |
| 11 | **Markets made certain by another result** (e.g. a map market after the series is already won; "to qualify" after a decisive match) | Outcome fixed by rules once the other result is in | Rule text (not played = void 50/50?) | merged into #17 (2026-10-04) |
| 12 | **Faster or earlier result sources** (official league feeds, sportsbook data, stream delays) | Know the result before the 0.999 bots | Cost, reliability, still too slow from a home PC | testing (2026-10-06): official feeds show the end 59-294 s before Polymarket's stamp; our latency unmeasured, recorder ready |
| 13 | **Weather dead ranges**: buy NO on a temperature range the station has already passed | Daily high can only go up, so a passed range is certain to lose | "No data → lowest range wins" rule; revisions; nothing for sale | rejected (2026-10-03): passed ranges have no NO sellers below 0.999 (166 of 166 checked); ~$7.50/day taken by others after 17:00 ([[R-2026-10-03]]) |
| 14 | **US sports near or after the end at 0.99** (MLB, NFL, college football, NHL) | Slower, less crowded finishes; 0.99 still bought just after the end; one wallet 3 losses in 1,344 | Rare comebacks if bought during play; rain/overtime/postponement rules; shadow mode does not watch these leagues yet | testing (2026-10-06): promising but tiny, 5-15 moneyline fills/day at ~$0.05; needs official-end shadow rule (card "Official-feed finish") |
| 15 | **Own win-probability model** (US sports first): buy only when our calculated chance clearly beats the price | Edge is measured, not hoped for; picks only situations that history says never lose | Model wrong in rare situations; rules (rain, overtime); small sample | parked (2026-10-04): even 9th inning, 2 outs, lead 4+ loses ~1 in 300-1,000; at 0.99 that is ~100 wins per loss ([[R-2026-10-04]]) |
| 16 | **Crypto Up/Down locked by math**: last seconds of the 60-second settlement average | Most of the average is already fixed; automatic settlement in ~53 s, no disputes | Big price jumps; bots at 0.999 within milliseconds; home PC too slow | rejected (2026-10-04): never locked by arithmetic; stand-in price wrong 7 of 150; neighbour bucket lost 4.7% ([[R-2026-10-04]]) |
| 17 | **Locked lines**: side markets (totals, team totals, first-5/first-half, "run in 1st inning") certain mid-game once the score passes the line | Arithmetic: runs/points can't be removed once they stand; early settlement (20-45 min) | Cancelled game = 50/50; wrong game matched; score reversed on review; almost nothing left at 0.99 after the safe moment | reopen (2026-10-06): full-game lines after the official Final, arithmetic 16,657/16,657 |
| 18 | **Paid UMA proposer**: propose the correct result on slow markets and earn the reward ($3.5-5 non-sports) | No trading, no speed race; answers from official sources | $250-500 deposit lost on a wrong/early proposal; whitelist needed; competition from ~177 proposers | testing (2026-10-05): shadow proposer log first; whitelist path is the first blocker ([[R-2026-10-05]]) |
| 19 | **ML model as an extra veto** (owner idea 2026-10-05): a small model trained on large public history (e.g. years of point-by-point tennis) that can only block a buy, never trigger one | Catches warning signs simple rules miss (momentum, serve, map pool) | Too little of our own data (~240 trades, 7 losses); rare events are where models fail; black box | parked (2026-10-05): only after focus #1 (simple "almost certain" rules) has results; standard library only |
| 20 | **Fast free score sites as a result source** (Flashscore first; later GRID Open Access, LoL live stats): a browser robot or feed reader that sees the end before Polymarket | Free; Flashscore is often seconds behind the real match | Unofficial, blocks bots, breaks on page changes, ~0.3-0.5 GB memory, not standard library; band empties ~74 s before Polymarket's score, so the end signal may still be too late | rejected (2026-10-06): Flashscore ~42 s ahead of the stamp but the band is gone 77 s earlier (319 tennis, 30 esports) |
| 21 | **Slow-arena sweep** (elections first, then box-office/data-index markets): buy the decided side when an official count is uncatchable, while humans still sell at 0.96-0.995 for ~2 h | No speed race; answer fixed by a public number; 0 losses in ~125 sampled markets | Late/mail ballots, recount, runoff, wrong race, revised numbers; more bots on Nov 3; lumpy | researching with guards (2026-10-06): 0 losses in ~2,900 post-close fills but 3.0% over 924 events; needs an official-count lock; Brazil runoff Oct 25 |
| 22 | **Long-tail league atlas**: leagues with no Polymarket result feed (lower soccer, cricket, table tennis) | Asks may linger where bots lack a feed | Abandoned match 50/50, score correction | new (2026-10-06) |
| 23 | **Soccer locked lines** (Over / both-teams-score after goals) | Arithmetic once the score passes the line | VAR reversal, abandoned match; NFL version had nothing left to buy | new (2026-10-06), low prior |
| 24 | **Safe-state atlas part 2** (NBA, NHL, soccer late, LoL/Valorant) | Loss under 1 in 1,000 states | In-play prices were fair in tennis/CS2/NFL | new (2026-10-06), low prior |
| — | Resting buy orders before the end (option 2) | — | Fills mostly when we are wrong | rejected (2026-10-03); reopened as testing 2026-10-06: last 30 min of US-sports games only, bids at 0.98+ |
| — | Buying on price during play (price-only rule) | — | Loss rate matches the price: no edge | rejected (2026-10-03) |

## Daily research notes

Folder `Research/`, one note per day: `R-<date>`. Newest first:

- [[R-2026-10-07]] — 0.999 after-result money goes to resting buy orders; queue test started; one-question goal and scoreboard
- [[R-2026-10-06]] — wallet study (nothing to copy), Flashscore lag fails, slow-arena sweep safe on Quebec (21/21) but tiny; official-feed finish rule is the next candidate
- [[R-2026-10-05]] — daily run + evening "almost certain moments" study (only MLB 7+ after 8 survives): Overwatch Bo3/BO5 score bug fixed; UMA window and liquidity rewards rejected; new #18 paid UMA proposer (shadow test)
- [[R-2026-10-04]] — daily run: locked lines (2,270/2,270 correct, but ~nothing at 0.99 after the safe moment); crypto rejected; win model parked; lab made leaner
- [[R-2026-10-04-wallets]] — early run (owner asked): profitable wallets; 0 losses after the end in 3,856 buys; US sports lead (idea #14)
- [[R-2026-10-03]] — first run: complete set and baskets rejected; weather dead ranges tested and rejected; PC healthy

## Where to change what the lab does

- Ask in any Claude Code session ("change the lab to ..."). The routines can be paused or changed
  under Routines in claude.ai/code.
- The lab never places orders and never touches a wallet. Research and pretend trades only.
