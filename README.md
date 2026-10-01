---
title: PolySweeper Vault — Index
tags: [polysweeper, polymarket, index]
created: 2026-09-30
---

# PolySweeper (v1) — Research Vault

Research notes on building a **Polymarket "sweeper" bot**. This folder is an
Obsidian vault: open the repo folder in Obsidian (or sync it with the
Obsidian Git plugin) and the `[[wikilinks]]` below will work.

> Status: **research phase, nothing built yet.** Started 2026-09-30.
> Author knows nothing about the topic yet, so notes start from zero.

## Map of content

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
- [[10-Friend-Bot-Brainstorm]] — the after-the-match sweeper idea, architecture, kill switch
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
- [[Sources]] — every link used

## Reliability warning

Facts in this vault come from **web-search summaries of secondary sources**
(blogs, Medium, Substack, vendor pages). Polymarket's own docs could not be
fetched directly in the research environment (network blocked), so nothing
here is verified against primary docs yet. Treat numbers as leads to verify,
not as facts. Many "make $1,000 a day" articles are promotional.
