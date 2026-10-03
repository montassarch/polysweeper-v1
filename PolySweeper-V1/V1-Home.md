---
title: PolySweeper V1 — Home
tags: [polysweeper, v1, index]
created: 2026-09-30
---

# PolySweeper V1 — our bot (home)

Our own Polymarket sports "sweeper": buy the confirmed winner of a finished
match below $1, hold until it pays $1. Code lives in the repo's `code/` folder.

> Status (2026-10-03): **shadow mode running 24/7 on the owner's PC under the autopilot** (pretend
> trades only, no real money). Latest: [[26-First-Shadow-Results]]. Research, backtests, results checks, dashboard and
> logic spec done. Started 2026-09-30.

## Map of content

- [[24-Task-List]] — **master to-do list: start here**
- [[25-Zero-Loss-Strategy-Lab]] — **living section: logic and strategies for near-zero losses**
- [[00-Session-Log]] — what was asked and decided, in order
- [[01-What-is-a-Sweeper]] — plain-language explanation
- [[02-Strategy-and-Math]] — how profit is made, formulas, examples
- [[03-Risks]] — what can go wrong (read before anything else)
- [[04-Technical-Stack]] — APIs, SDKs, wallets, rate limits
- [[05-Fees-and-Costs]] — Polymarket fee structure
- [[06-Legal-and-Compliance]] — jurisdictions, terms of use
- [[07-Open-Questions-and-Next-Steps]] — what to do next
- [[08-Strategy-Catalog]] — every strategy type found, to study one by one
- [[09-Sports-Markets]] — sports focus: how they work and which strategies fit
- [[10-After-Match-Sweeper-Brainstorm]] — the after-the-match sweeper idea, architecture, kill switch
- [[11-V1-Plan-Simple]] — the v1 plan in plain language, risk rules, backtest plan
- [[12-Data-Sources]] — Polymarket data and sports results APIs
- [[13-Code-Overview]] — what the code does, in plain language (code is in `code/`)
- [[14-Real-Data-Findings]] — first look at real Polymarket data (min order size, resolution sources, price behaviour)
- [[15-First-Real-Backtest]] — first real results on esports: win rates, timing, honest caveats
- [[16-Football-Results-and-Shadow-Mode]] — football results and the shadow mode tool
- [[17-Run-Shadow-On-Your-PC]] — how to run shadow mode on your Windows PC
- [[18-Dashboard]] — the dashboard page: what it shows and how to open it
- [[19-Results-Check-Dota]] — Dota 2 results check with true end times
- [[20-Results-Check-Football]] — football results check against ESPN, two traps found
- [[21-Shadow-Mode-v2]] — shadow mode now tests the confirmed-result rule
- [[23-Bot-Logic-Spec-and-Audit]] — full bot logic and the audit of mistakes
- [[26-First-Shadow-Results]] — first pretend-trade results and the match-finding bug
- [[27-Score-Check]] — check 2: Polymarket's own score must agree (blocks the Sep 30 loss)
- [[28-Autopilot]] — hands-free shadow mode: starts at login, auto-updates, auto-syncs data
- [[Sources]] — every link used

## Reliability warning

Facts in this vault come from **web-search summaries of secondary sources**
(blogs, Medium, Substack, vendor pages). Polymarket's own docs could not be
fetched directly in the research environment (network blocked), so nothing
here is verified against primary docs yet. Treat numbers as leads to verify,
not as facts. Many "make $1,000 a day" articles are promotional.
