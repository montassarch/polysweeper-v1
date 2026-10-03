---
title: Zero-Loss Strategy Lab
tags: [polysweeper, strategy, risk, lab]
created: 2026-10-02
---

# Zero-Loss Strategy Lab

Back to [[V1-Home]] · Logic and audit: [[23-Bot-Logic-Spec-and-Audit]] · Tasks: [[24-Task-List]] · Risks: [[03-Risks]]

A living section for one goal: **win almost every trade, and make the rare loss
as small and as rare as possible.** New ideas get added at the bottom; tested
ideas move up with their result.

---

## 1. The honest math: "99% winning" is not enough

When you buy at price `p` and the share pays $1, one loss costs about `p` and one
win earns about `1 - p`. So the **break-even win rate is about equal to the
price** (a bit higher after fees).

| Buy price | Profit per win | Wins needed per loss | Break-even win rate | Is 99% enough? |
|---|---|---|---|---|
| 0.96 | 4 cents | 24 | 96.0% | Yes |
| 0.97 | 3 cents | 32 | 97.0% | Yes |
| 0.98 | 2 cents | 49 | 98.0% | Yes, barely |
| 0.99 | 1 cent | 99 | 99.0% | **No (break-even)** |
| 0.998 | 0.2 cents | 499 | 99.8% | **No** |

**Target:** the loss rate must be far below `1 - price`, not just "about 1%".
For the low band (0.96-0.99) that means well under 1%. For the late
band (0.998) it means under about 1 in 500, and in practice close to zero.

**Two ways to win this game:**
1. **Make losses rarer** (better confirmation): sections 3 and 4.
2. **Make each loss cheaper** (lose less than the full stake): section 5.

---

## 2. Where a "confirmed" trade can still lose (failure list)

| # | How it fails | Guard | Status |
|---|---|---|---|
| F1 | **Wrong match** (name fits two teams, rematch same day, wrong date) | Unique match by team + kickoff + competition; name-fits-both-sides = skip | Built (football, Dota); team IDs planned (B2) |
| F2 | **Wrong result data** (feed error, late correction) | 2+ independent sources must agree; data must be fresh | Partly (football has 1 strong source: B4) |
| F3 | **Different settlement rule** (90 min vs extra time; overtime included; tennis retirement) | Sport-by-sport rules table; unknown = skip | Football rule built; table planned (B6) |
| F4 | **50/50 payout** (cancelled, postponed, forfeit, walkover, tie) | Abnormal finish = skip | Built |
| F5 | **Polymarket/UMA settles differently** (wrong proposal, dispute, voter error) | Check UMA status; skip if proposal against us or disputed | Planned (B5) |
| F6 | **Match not really over** (suspended, abandoned, protest) | Source status must be a clean "full time"; Polymarket "ended" flag too | Built |
| F7 | **Junk or stale order book** | Book sanity check (real bids, other side cheap) | Built (A5) |
| F8 | **Execution mistake** (wrong token, double buy, partial fill) | Fill-or-kill limit orders, unique order ids, post-trade check | Planned (B8) |
| F9 | **Several bad trades at once** (one source breaks for many matches) | Circuit breaker: disable a source after anomalies; daily loss limit | Partly (daily limit, pause on loss) |
| F10 | **Venue or wallet problem** (outage, hack, rule change) | Separate bot wallet with small balance; kill switch | Wallet rule written; Telegram kill switch planned (B9) |

---

## 3. Pillars for near-zero losses

1. **Certainty first.** Buy only after the result is confirmed final. Never
   predict, never buy during play. (Data: buying during play is where almost
   all historical losses came from.)
2. **Consensus.** Two or more *independent* result sources, ideally including
   the **official resolution source** that Polymarket names for that league.
   Any disagreement = stand down.
3. **Market veto (new idea).** If our "confirmed" winner is still trading
   **cheap after the end** (for example below 0.90 when sources say it won),
   the crowd may know something we don't (protest, correction, wrong match).
   Treat a bargain as a **warning**, not an opportunity. Skip.
4. **Known rules only.** Whitelist market types and sports whose settlement
   rules we have written down and tested. Everything else is skipped.
5. **UMA gate (choice per band).**
   - *Before the proposal:* more profit, small result risk.
   - *After a matching proposal is posted:* less profit (price usually 0.995+),
     but the result risk drops further. This matches the late-band (V2) approach.
6. **Small, spread-out bets.** One trade per match, small fixed share of the
   account per trade, caps per league and per day, so no single failure is
   big and failures are unlikely to stack.
7. **Every loss teaches a rule.** Each loss gets a short post-mortem, a new
   rule and an automatic test (as we did for the extra-time and PSG/Paris FC
   traps).

---

## 4. Making losses rarer: specific checks to add

- **Check 2, Polymarket score check (BUILT 2026-10-03):** never buy a side
  that Polymarket's own score shows losing. About 13,000 finished matches
  checked, 3 wrong scores (teams swapped), 0 wrong payouts. It would have
  blocked our only loss. Details: [[27-Score-Check]].

- **Official-source check:** scrape or read the league's official result page
  that Polymarket lists (rate-limited, polite), as the second or third source.
- **Rules-text reader:** read each market's description and refuse anything
  that doesn't match a known template.
- **Duplicate-fixture check:** refuse if the same two teams play twice within
  the time window (common in esports brackets).
- **Settlement cross-check after payout:** compare Polymarket's final result with
  ours for every market (bought or not). Any mismatch = investigate before the
  next trade.
- **Source health score:** track each source's agreement rate; demote or
  disable a source that disagrees too often.

---

## 5. Making the rare loss cheaper

### Tested: price stop-loss (sell if price falls below a level) -> **does NOT work**

Tested on our history (mid prices, buying when price first rose into 0.96-0.995,
selling at the first price seen below the stop, minus 2 cents):

| Stop | Esports profit/share | Football profit/share | Winners sold by mistake (football) | Price we got when selling losers (football) |
|---|---|---|---|---|
| none | +0.33c | -0.33c | 0 | - |
| 0.90 | -0.50c | -1.10c | 393 | about 0.50 |
| 0.80 | -0.28c | -0.86c | 142 | about 0.33 |
| 0.70 | -0.18c | -0.62c | 74 | about 0.26 |

Why: losses arrive as **jumps** (a goal), so the price skips past the stop and we
sell far lower; meanwhile many eventual winners dip temporarily and get sold.
(A naive test that assumed selling exactly at the stop looked great, which is
why the jump-aware test matters.) **Conclusion: no price-based stop-loss.**

### Promising: event-based exit (to test)

Sell immediately, while buyers still exist, **only when a specific warning
appears** after we bought:
- a UMA proposal for the other side, or a dispute,
- a results source changes its result,
- Polymarket posts a clarification or flags the market.

Because these warnings usually come **before** payout, the share can often still
be sold for much more than $0. Needs real data: shadow mode can log these events.

### Other ways to cap the damage

- **Size:** keep each trade a small share of the account (e.g. 2-5%), so one
  loss is a dent, not a crater.
- **Avoid 50/50-prone markets:** a 50/50 payout at price 0.98 loses about half
  the stake; skip sports/markets where cancellations, walkovers or ties are common.
- **Daily loss limit and pause after any loss** (built), with a review before
  restarting.
- **Circuit breakers:** stop everything if several anomalies happen together.

---

## 6. Go-live scorecard (what shadow mode must show first)

| Band | Typical profit per win | Settled confirmed trades needed with **zero** wrong-result losses |
|---|---|---|
| Low band (0.96-0.99) | 1-4 cents | about **300** (proves loss rate under about 1%) |
| Late band (0.995-0.999) | 0.1-0.5 cents | about **1,500** (proves under about 0.2%) |

Plus: no execution errors, real fills match the pretend fills, and every refusal
reason looks sensible.

---

## 7. Ideas backlog (newest at the bottom)

1. **Market veto** (section 3.3). Easy, high value.
2. **Resting buy orders after confirmation:** after the result is confirmed, place
   a limit buy at 0.97-0.99 and let impatient sellers fill it (maker: no fee,
   possible rebate). Catches the brief "seller dumps" in the late band.
3. **Faster price feed** via Polymarket's websocket instead of 15-second polling,
   for the short football window.
4. **UMA watcher:** log proposals and disputes for every market we watch
   (needed for the event-based exit and the UMA gate).
5. **Capacity estimate** from recorded order-book sizes: how much money each
   band can really absorb.
6. **Loss post-mortem template** in Obsidian, filled for every loss.
7. **Per-sport finality notes** (tennis retirement, cricket rain rules, US sports
   overtime) before adding any new sport.
