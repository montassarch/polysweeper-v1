---
title: Open Questions and Next Steps
tags: [polysweeper, todo]
created: 2026-09-30
---

# Open questions and next steps

Back to [[README]]

## Open questions

- [ ] What exactly does "sweeper" mean to you? (near-certain outcomes, dust
      sweeping, order-book sweeping, other?) See [[01-What-is-a-Sweeper]].
- [ ] Which jurisdiction are you in; is trading allowed? [[06-Legal-and-Compliance]]
- [ ] Exact taker-fee formula near 0.95–0.99 prices. [[05-Fees-and-Costs]]
- [ ] Real historical data: how often did "0.97+" markets resolve against the
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

- [ ] Make `polysweeper-v1` **private** (Settings → Danger Zone).
- [ ] Install the Claude GitHub App on the repo so the session can push.
- [ ] Create `Polysweep-V2` manually if still wanted (session cannot).
- [ ] Open this folder as an Obsidian vault (or use the Obsidian Git plugin).
- [ ] Never commit keys: add `.env` to `.gitignore` before any code exists.
