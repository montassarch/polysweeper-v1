---
name: idea-methods
description: Idea-generation methods for PolySweeper strategy brainstorming (inversion, analogies from other markets, follow the money, constraint removal, timeline walk, category swap, and more), with prompts tuned to Polymarket. Use when generating new strategy ideas, mainly by the ps-ideas agent.
---

# Idea methods for PolySweeper

Use several methods per run; different methods give different ideas. Write every idea down before
judging it. Judge only after the list is long.

## 1. Timeline walk
Pick any market and walk its whole life: listing → first trades → news events → the real-world
outcome → Polymarket's result → UMA proposal → 2-hour liveness → dispute window → payout. At each step
ask: who knows something here that the order book doesn't show yet? Who is forced to sell or buy?

## 2. Follow the money
Who loses money on Polymarket every day, and why? (Impatient sellers who want cash now, people who
forget positions, market makers widening spreads, people who misread the rules.) Each one is a
possible counterparty. Check the most profitable wallets in the Data API: what do they do that others
don't? Copy the pattern, not the trade.

## 3. Inversion
Instead of "how do we win?", ask "how does a near-certain trade still lose?" (void, rule wording,
score error, dispute, late result, one leg not filling). Then look for markets where those causes
are structurally impossible.

## 4. Constraint removal
Take a limit we assumed and drop it: "we must buy after the result", "we must use sports", "we must be
a taker", "we must hold to $1", "one market at a time". What becomes possible? Then check if the
constraint really holds.

## 5. Analogies from other markets
Ideas that work elsewhere: merger arbitrage, index rebalancing, closing auctions, bond pull-to-par,
betting exchange "trading out", sports-book line shopping, ETF creation/redemption, calendar spreads.
What is the Polymarket version?

## 6. Category swap
Take what we know about sports end windows and move it to other categories: crypto up/down markets,
weather, economic data releases, elections and counts, awards, box office, app rankings, "will X
tweet", mentions markets. Which ones have an official, public, fast result and few sweepers?

## 7. Logic and structure
Related markets that must agree: YES+NO, multi-outcome (negRisk) baskets, "A wins series" vs map
markets, "over X" ladders, date ladders ("by June" ≥ "by May"). Any price that breaks the logic is a
possible zero-risk basket. Mind fees and both legs filling.

## 8. Rewards and rules
Polymarket's liquidity rewards, maker rebates, holding rewards, fee-free markets, new-market
promotions. Can a near-certain position also earn rewards?

## 9. Wild card
Deliberately silly first: "what if we were the 0.999 bot?", "what if we only traded one minute a day?",
"what if we sold instead of bought?". Then look for the sensible core.

## Quick kill checks (after the list is long)
- Needs to beat fast bots by seconds? → usually dead for us.
- One surprise can lose the whole stake, and surprises happen more than ~1 in 1,000? → dead.
- Nobody would sell to us at our price? → dead (check the order books).
- Profit after fees under $0.01 per 5 shares? → dead.
- Already dropped on the idea board with no new twist? → dead.
