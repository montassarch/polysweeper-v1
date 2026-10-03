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

- [ ] **Restart the autopilot once** (restart the PC, or `stop_shadow.bat` then `autopilot.bat`): the PC still runs the first version ([[28-Autopilot]]) — **owner**
- [ ] Pull in Obsidian, then double-click `setup_autopilot.bat` once ([[28-Autopilot]]) — **owner**
- [ ] Keep shadow mode running, PC awake and plugged in (set sleep to Never; it slept 27 of 49 h) — **owner**
- [x] First results written up: [[26-First-Shadow-Results]]
- [ ] Find a free results source for CS2 and LoL so they can use the confirmed rule — **assistant**
- [x] Data sync is automatic every 3 hours (autopilot)
- [ ] Read results after each sync and report — **assistant**
- [x] Live feed + 2-second checks near the end + score log (shadow v2.6, [[29-Live-Feed-and-Score-Log]])
- [ ] Check the first `live_feed_status` line from the PC: does the live feed connect and agree with the 15-second reads? — **assistant**
- [ ] After 1-2 days: live end-window report (any gap after the result?) — **assistant**
- [ ] After a few days: test tennis "practically locked" rules on the score log — **assistant**
- [x] Shadow mode: enforce B7 (max 1 pretend buy per match and rule; second chances logged as `skip_second_buy`)
- [x] End-window study: record real watch time (`seconds_watched`), report leaves out pre-fix rows
- [x] Autopilot: restart shadow mode only when code changes, not for note edits ([[28-Autopilot]])
- [ ] Phase 1 ends after ~2 weeks or 100+ settled confirmed pretend trades — **both**

## PolySweeper Lab (automated research, from 2026-10-03)

- [x] Team of agents, idea board and daily routines set up ([[30-Research-Hub]])
- [x] Cloud network set to full trust (owner, 2026-10-03): agents can read web pages; live feed tested on the real server
- [ ] Optional: install the "Exa Deep Research" plugin for better web reading — **owner**
- [ ] Read the daily research note; tell the lab what to focus on — **owner** (whenever useful)
- [ ] Daily score log (`code/data/shadow/daily/`) not reaching GitHub and a restart after a notes-only push: check the 22:12 sync; if still missing, owner closes and reopens `autopilot.bat` (see [[R-2026-10-03]]) — **assistant**, then **owner**
- [ ] Lab next: research #8 maker rebates / liquidity rewards and #10 profitable 0.99+ wallets — **assistant (lab)**

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
- [x] Resting buy orders: dropped 2026-10-03 (after the result buyers already offer 0.99-0.999 in 27 of 27 matches; before it, fills come when we are wrong)
- [ ] Settlement cross-check after every payout (our result vs Polymarket's) — **assistant**
- [ ] Duplicate-fixture check and rules-text reader — **assistant**
- [x] Websocket price feed (built into shadow mode v2.6, measuring only)
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
