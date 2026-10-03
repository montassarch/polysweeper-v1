---
title: Master Task List
tags: [polysweeper, tasks, todo]
created: 2026-10-02
---

# Master task list

Back to [[V1-Home]] · Logic and audit: [[23-Bot-Logic-Spec-and-Audit]] · Test plan: [[07-Open-Questions-and-Next-Steps]]

One place for everything. Older notes keep their own checklists for context;
this list is the one to follow. Owner = who does it.

## Now: running test (Phase 1)

- [ ] Pull in Obsidian, then double-click `setup_autopilot.bat` once ([[28-Autopilot]]) — **owner**
- [ ] Keep shadow mode running, PC awake and plugged in (set sleep to Never; it slept 27 of 49 h) — **owner**
- [x] First results written up: [[26-First-Shadow-Results]]
- [ ] Find a free results source for CS2 and LoL so they can use the confirmed rule — **assistant**
- [x] Data sync is automatic every 3 hours (autopilot)
- [ ] Read results after each sync and report — **assistant**
- [x] Shadow mode: enforce B7 (max 1 pretend buy per match and rule; second chances logged as `skip_second_buy`)
- [x] End-window study: record real watch time (`seconds_watched`), report leaves out pre-fix rows
- [x] Autopilot: restart shadow mode only when code changes, not for note edits ([[28-Autopilot]])
- [ ] Phase 1 ends after ~2 weeks or 100+ settled confirmed pretend trades — **both**

## Next: compare with the late band (Phase 2)

- [x] Record prices up to 0.999 and check results there too (logging only)
- [ ] Analyse the late band (0.995-0.999) on the same matches — **assistant**
- [ ] Compare both bands: trades/day, fills, thin/junk skips, losses, profit/trade, time to payout — **assistant**
- [ ] Decide which band(s) the real bot uses — **owner**

## Before any real money (from the audit)

- [ ] B1 Set the waiting time after the match per band (low band: fast; late band: can wait) — **assistant**
- [ ] B2 Internal team IDs so different spellings count as the same team — **assistant**
- [ ] B3 Decision model = "market + token" (Yes/No and draw markets) — **assistant**
- [ ] B4 Second independent results source for football (OpenLigaDB for German leagues; paid option later) — **assistant**
- [ ] B5 Refuse markets that are disputed or have a UMA proposal against us — **assistant**
- [ ] B6 Sport-by-sport settlement rules table (football 90 min, US sports with overtime, tennis retirements) — **assistant**
- [ ] B7 Max 1 trade per match — **assistant** (done in shadow mode; the real bot needs it too)
- [ ] B8 Real order handling: fill-or-kill limit orders, never buy twice, check fills and balance — **assistant**
- [ ] B9 Telegram bot: alerts, `/status`, `/pause`, `/kill` — **assistant** (owner creates the bot token)
- [ ] Watchdog: auto-restart after crash, pause on anything strange — **assistant**
- [ ] Money limits as percentages instead of fixed dollars — **assistant**
- [ ] Full refusal log (every skipped chance with its reason) — **assistant**
- [ ] Measure ESPN/OpenDota delay vs Polymarket "ended" flag (from shadow data) — **assistant**
- [ ] Re-test with pessimistic fills (real asks and depth from shadow data) — **assistant**

## Zero-loss ideas to build or test (see [[25-Zero-Loss-Strategy-Lab]])

- [x] Test a price stop-loss on history -> does NOT work (losses jump past the stop)
- [ ] Market veto: skip a "confirmed" winner that still trades below 0.90 after the end — **assistant**
- [ ] UMA watcher: log proposals and disputes for watched markets — **assistant**
- [ ] Event-based exit (sell only on a UMA proposal against us, a dispute or a source correction) — test with shadow data — **assistant**
- [ ] Resting buy orders after confirmation (catch seller dumps, no fee) — design and test — **assistant**
- [ ] Settlement cross-check after every payout (our result vs Polymarket's) — **assistant**
- [ ] Duplicate-fixture check and rules-text reader — **assistant**
- [ ] Websocket price feed for the short football window — **assistant**
- [ ] Go-live scorecard: ~300 (low band) / ~1,500 (late band) confirmed trades with zero wrong-result losses — **both**

## Legal and money setup

Handled privately by the owner; not tracked in this vault.

## Later: grow

- [ ] Results sources for CS2, LoL, Valorant — **assistant**
- [ ] More leagues and sports, one at a time, each with its own results source and rules — **both**
- [ ] AI helpers: daily reporter, bug-fix agent (branch + pull request, owner approves), code reviewer, weekly analyst — **assistant**
- [ ] Automatic tests on GitHub for every change — **assistant**
- [ ] Watch UMA for disputes on held positions — **assistant**

## Done (highlights)

- [x] Research vault in Obsidian, private repo, Obsidian Git sync
- [x] Strategy research, sports focus, after-match sweeper brainstorm, v1 plan
- [x] Decision core, risk rules, kill switch, backtester (45 automatic tests)
- [x] Real data collector; esports and football backtests
- [x] Dota 2 results check (OpenDota) and football results check (ESPN); extra-time and wrong-team traps fixed
- [x] Shadow mode v2.1 on owner's PC: confirmed-result and price-only rules, batched and crash-proof, junk-book filter
- [x] Shadow mode v2.2: finds matches by real start time, not listing date (A6 fix)
- [x] Check 2 (score check) built and tested on ~13,000 finished matches; third shadow rule "score" ([[27-Score-Check]])
- [x] Dashboard (snapshot and 15-second live mode)
- [x] Full bot logic spec and audit
- [x] Venue decision: Polymarket global
