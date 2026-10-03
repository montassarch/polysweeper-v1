---
title: Technical Stack
tags: [polysweeper, tech, api]
created: 2026-09-30
---

# Technical stack

Back to [[V1-Home]] · Related: [[03-Risks]]

All details from secondary sources; verify against
https://docs.polymarket.com before coding.

## APIs

| API | Purpose | Auth |
|---|---|---|
| Gamma API (`gamma-api.polymarket.com`) | Market/event discovery, metadata | none, public |
| CLOB API | Order book, prices, place/cancel orders | yes, for trading |
| Data API | Positions, trades, history | public reads |
| WebSocket `/wss/market` | Live book snapshots, price changes, last trade, tick-size changes | public |

Read endpoints are reportedly not geoblocked, so research and monitoring work
from anywhere (see [[06-Legal-and-Compliance]]).

## SDKs

- **Current**: `py-clob-client-v2` (`pip install py-clob-client-v2 web3
  requests websocket-client`).
- Legacy `py-clob-client` was retired with CLOB V2 (2026-04-28). Collateral
  moved to **pUSD**; order signing changed.
- Order types mentioned: GTC (limit), FOK (market, fill-or-kill); others
  (FAK, GTD) exist per general knowledge; verify.
- Other options: NautilusTrader Polymarket integration, TypeScript/OCaml
  clients, Polymarket `agents` repo (AI agent framework).

## Wallets and gas

- New API users use **deposit wallets** (ERC-1271 order validation). Safe and
  Proxy wallets remain supported for existing users.
- Token approvals must be made **from the deposit wallet**, through the
  relayer, not from the owner EOA.
- The **Relayer** sponsors gas on Polygon: you need pUSD, not MATIC.
- Winning tokens must be **redeemed**; there are auto-redeem scripts.

## Rate limits (per one 2026 source, verify)

- Gamma general: ~4,000 req / 10s; `/markets` ~300 / 10s; `/events` ~500 / 10s.
- CLOB: ~9,000 req / 10s overall; `POST /order` burst ~5,000 / 10s,
  sustained ~120,000 / 10 min; `/book`, `/price`, `/midpoint` ~1,500 / 10s.
- Enforced via Cloudflare throttling (requests may be queued, not rejected).

## Suggested v1 architecture

1. **Scanner**: poll Gamma for markets closing soon with price 0.95–0.995.
2. **Filter**: liquidity, depth, rules check, blacklist categories.
3. **Risk engine**: position caps, daily loss limit, kill switch.
4. **Executor**: place limit orders via CLOB V2 client.
5. **Redeemer**: claim winnings after resolution.
6. **Logger / journal**: every decision to a file (feeds this vault).
7. **Dry-run mode** first: log what it *would* do, no orders.

Language suggestion: Python (official client, easy to iterate).
