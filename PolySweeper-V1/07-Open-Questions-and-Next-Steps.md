---
title: Open Questions and Next Steps
tags: [polysweeper, todo]
created: 2026-09-30
---

# Open questions and next steps

Back to [[V1-Home]]

## Open questions

- [ ] What exactly does "sweeper" mean to you? (near-certain outcomes, dust
      sweeping, order-book sweeping, other?) See [[01-What-is-a-Sweeper]].
- [x] Which jurisdiction are you in; is trading allowed? [[06-Legal-and-Compliance]]
- [ ] Exact taker-fee formula near 0.95–0.99 prices. [[05-Fees-and-Costs]]
- [x] Real historical data: how often did "0.97+" markets resolve against the
      holder? This decides whether the strategy has positive expectancy.
- [ ] How long do normal and disputed resolutions actually take?

## Suggested path (no real money until step 5)

1. Finish research: verify everything against primary docs
   (needs network access to docs.polymarket.com).
2. Pull **historical resolved markets** and their last prices; backtest the
   0.95–0.99 entry rule, including losses and fees.
3. Build a **read-only scanner** (Gamma API) that lists candidates and logs
   them.
4. Add **dry-run trading** (log hypothetical orders, track hypothetical PnL).
5. Only then: tiny real positions, dedicated wallet, hard loss limits.

## Housekeeping

- [x] Make `polysweeper-v1` **private** (Settings → Danger Zone).
- [x] Install the Claude GitHub App on the repo so the session can push.
- [x] ~~Create `Polysweep-V2` manually if still wanted (session cannot).~~ (not needed)
- [x] Open this folder as an Obsidian vault (or use the Obsidian Git plugin).
- [x] Never commit keys: add `.env` to `.gitignore` before any code exists.

## Owner's answers (2026-09-30)

- Building own version from scratch; no outside code used.
- Does not code; needs plain-language explanations.
- Backtest with fake $50; real money later.
- Country: Tunisia.
- Sports: esports and football first, then all sports.
- Risk: wants to avoid losses; risk management is a priority.
- Uses Telegram; will pay for a data API after the backtest.
- Goal: learn and profit; start small, improve gradually.
- Open questions are answered by our own research and testing (2026-10-03);
  the late-band strategy is researched separately in the V2 research project.
- Legal and funding questions: handled privately by the owner.

See [[11-V1-Plan-Simple]].

## Test plan agreed (2026-10-01)

1. **Phase 1, ours first:** shadow mode v2 runs on the owner's PC with our rules
   (confirmed result and price only, band 0.96-0.995). No code changes to the
   rules during this phase, so the results stay comparable.
   - Check-ins every 2-3 days (owner runs Commit-and-sync, assistant reads).
   - Phase ends after about **2 weeks**, or earlier once there are **100+ settled
     confirmed-result pretend trades**.
2. **Phase 2, the late-band strategy:** add the late band 0.995-0.999
   (confirmed results only) and run the same way. See the V2 research project (folder `PolySweeper-V2-Research`).
3. **Compare:** pretend trades per day, real fill prices, thin-book skips, wins,
   losses, 50/50s, fake profit per trade and per day, time until paid.

## Capacity estimate: all sports (measured 2026-10-02)

- Polymarket settled about **8,400 match-winner markets in 7 days**, of which about
  **4,000 single-match** ones: roughly **290 matches and 570 match-winner markets per
  day** (other sports ~320/day, football ~165/day, esports ~90/day). One day hit a
  paging limit, so this is a slight undercount.
- Our current coverage (9 football leagues + 4 esports) is only about 5% of that.
- Rough sweep estimate if everything were covered, low band (0.96-0.995), confirmed
  rule: 570 x ~30% (winner sits in band after the end) x ~70% (results source
  available) x ~70% (real sellers, not thin/junk) = **about 50-150 sweeps a day**.
  Late band (0.995-0.999) unknown until shadow data.
- Money limits: at $50 (3 trades open, payouts 1-2.5 h) the bot can only use about
  20-30 sweeps a day; 100+ a day needs roughly 10x the capital with percentage limits.
