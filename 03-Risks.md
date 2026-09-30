---
title: Risks
tags: [polysweeper, risk]
created: 2026-09-30
---

# Risks

Back to [[README]]

The payoff is asymmetric: **small, frequent gains vs. rare total losses.**
See the break-even math in [[02-Strategy-and-Math]].

## 1. Tail / reversal risk

The "certain" outcome is not certain. A last-second reversal, a rules
technicality, or new information can send a 0.98 position to 0. One loss can
wipe out dozens of wins.

## 2. Oracle and dispute risk (UMA)

Polymarket markets resolve through the UMA Optimistic Oracle (per sources):

- Anyone can propose an outcome; a bond (~$750 per sources) is posted.
- If nobody disputes within ~2 hours, the proposal stands.
- If disputed, it goes to a UMA token vote.

Reported problems:

- Voting power is concentrated; in many disputed markets >50% of votes came
  from the top ten wallets.
- Some voters had financial stakes in the market they judged (~20% of
  disputed outcomes, per one source).
- March 2025 governance attack: an attacker with ~25% of votes pushed a false
  resolution, ~$7M paid out.
- The "Zelenskyy suit" market flipped to NO after ~9 days of disputes.

Implication for a sweeper: a market that looks 99% can still end up resolved
against you, and capital can be **locked for days** during a dispute.

## 3. Capital lockup

Money is stuck until resolution. A 2% gain on a 90-day market is a poor
annualized return. Disputes extend the lock.

## 4. Fees and slippage

Taker fees can consume a large share of a 1–2% edge, especially in crypto
markets. See [[05-Fees-and-Costs]]. Thin order books mean you may not fill at
the displayed price.

## 5. Competition

Many bots chase the same pennies. Edge decays; speed and selection quality
matter. Articles claiming easy daily profit are often promotional.

## 6. Technical risk

- CLOB V2 launched April 28, 2026; stale clients can **silently fail** to
  place orders. Pin the V2 client and test with tiny sizes.
- Rate limits, websocket disconnects, bad order handling, clock drift.
- Bugs that double-buy or never sell.

## 7. Security risk

- Bots hold a **private key**. Never commit it; use env vars and `.gitignore`.
- **This is why the repo must be private and keys must never be in it.**
- Use a dedicated wallet with only the capital you can afford to lose.

## 8. Legal / account risk

See [[06-Legal-and-Compliance]]. Trading from a restricted jurisdiction or
circumventing geoblocks can lead to close-only mode or account closure.

## Rules of thumb for a beginner

- Paper trade / simulate first. No real money until the logic is tested.
- Start with tiny positions.
- Cap exposure per market and per topic.
- Never treat "99%" as "risk-free".
