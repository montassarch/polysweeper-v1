---
title: Fees and Costs
tags: [polysweeper, fees]
created: 2026-09-30
---

# Fees and costs

Back to [[V1-Home]] · Affects [[02-Strategy-and-Math]]

Per search summaries (verify on Polymarket docs; fees changed during 2026):

- Historically Polymarket charged no trading fees. A **taker-fee** model was
  rolled out in stages in 2026. **Makers pay zero** and receive rebates funded
  by taker fees.
- **Fee Structure V2 (effective 2026-03-30)** taker rates by category:
  crypto 0.07; sports 0.03; finance/politics/mentions/tech 0.04;
  economics/culture/weather/other 0.05; geopolitics and world events: free.
- Reported **maximum fee per 100 shares**: $1.00 (politics, finance, tech,
  mentions), $1.25 (sports, economics, culture, weather, other), $1.75
  (crypto).
- **Polymarket US** (regulated exchange): taker 0.05, maker rebate -0.0125,
  cap $1.25 per 100 contracts at 50¢.
- Gas is sponsored by the relayer; you pay in pUSD only.

## Why it matters for a sweeper

Edge per trade is ~1–5%. The exact fee formula is price-dependent (the
"maximum" is at mid prices, near 50¢); near 0.98 the fee is expected to be
much lower, but **this must be computed from the official formula**, not
assumed. Open item in [[07-Open-Questions-and-Next-Steps]].

Practical takeaways:

- Prefer **maker (limit) orders**: zero fee, possible rebate.
- **Fee-free categories** (geopolitics/world events) are attractive for this
  strategy, but check resolution-risk there.
- Crypto up/down markets carry the highest fee rate and the most tail risk.

## Update: sports fees (conflicting source)

One source reports the sports taker rate rose from 0.03 to **0.05 in July 2026**
(max ~$1.25 per 100 shares) and the sports maker rebate fell from 25% to
**15%**. Older sources say 0.03. Verify on the official docs. See
[[09-Sports-Markets]].
