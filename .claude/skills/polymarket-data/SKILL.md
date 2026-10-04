---
name: polymarket-data
description: Cheat sheet for reading Polymarket's public data in this project (Gamma events/markets, CLOB order books and price history, Data API public trades, the market websocket) plus the traps that already cost us time. Use before writing any script or research that queries Polymarket, in lab/ or code/.
---

# Polymarket public data: what works and what bites

Read-only. Never place orders, never touch wallets or keys. Standard-library Python only
(`urllib.request`, `json`); copy helpers from `code/polysweeper/collector.py` instead of rewriting them.

## Endpoints we use (all public, no key)

| Need | Endpoint | Notes |
|---|---|---|
| Events and their markets | `GET https://gamma-api.polymarket.com/events` | Filter with `closed=`, `tag_slug=`, `series_id=`; page with `limit`/`offset`. Fields: `negRisk`, `umaResolutionStatus`, market `outcomes`, `clobTokenIds` (JSON strings inside JSON: `json.loads` them) |
| One market | `GET https://gamma-api.polymarket.com/markets` | Same fields per market |
| Order books (many at once) | `POST https://clob.polymarket.com/books` with `[{"token_id": ...}, ...]` | Always batch; one book per token (YES and NO share one book: YES ask = 1 - NO bid) |
| Price history | `GET https://clob.polymarket.com/prices-history` | About 1-minute points, **mid prices, no depth**: never treat as fills |
| Every public trade, with wallet | `GET https://data-api.polymarket.com/trades` | Filter by `market` (condition id) or `user` (wallet); best source for "who bought at 0.99+, when, how much" |
| Live books and trades | `wss://ws-subscriptions-clob.polymarket.com/ws/market` | Stdlib client already built: `code/polysweeper/livefeed.py` |

## Traps (each one already bit us)

- **Custom User-Agent required** on CLOB (default Python UA gets refused). Use the `UA` dict from `collector.py`.
- Gamma `start_date` is the **listing** date. Match start is `startTime` / `gameStartTime`.
- Gamma prices and "last trade" can be stale. Only the CLOB book says what you could really buy.
- Minimum order **5 shares**. Taker fee = shares x rate x p x (1-p), rate per market (0.03-0.05).
- Football settles on **90 minutes** (extra time and penalties excluded). Voids and cancellations pay **50/50**.
- Polymarket's score field has teams swapped about 1 in 4,000: use it as a **veto**, never alone (`code/polysweeper/scorecheck.py` parses it).
- negRisk "augmented" events have hidden placeholder outcomes and an "Other" slot: the named options are not a complete set.
- Old listings can still say "active": trade only markets with a live book.
- Results are final only after UMA's challenge window; `umaResolutionStatus` shows proposed / disputed / resolved.

## House rules for scripts

- Research scripts go in `lab/` (not `code/`: a push to `code/` restarts the owner's PC). Small results in
  `lab/results/`, raw downloads in `lab/data/raw/` (git-ignored).
- Be polite: sleep between pages, batch book requests, cache raw downloads.
- Report counts and short tables in the vault note, never raw API dumps.
- Before a new idea, check `PolySweeper-V1/30-Research-Hub.md`: rejected ideas stay rejected unless there is new evidence.
