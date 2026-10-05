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

- [x] Desktop app PolySweeper.exe: live view of shadow mode, built and tested on Windows by GitHub, installed by the autopilot ([[31-Desktop-App]])
- [ ] Open the PolySweeper icon on the desktop; the first time click "More info" then "Run anyway" — **owner**
- [x] (done 2026-10-04 00:31: one-time git fix, PC now runs the new autopilot) **Restart the autopilot once** (restart the PC, or `stop_shadow.bat` then `autopilot.bat`): the PC still runs the first version ([[28-Autopilot]]) — **owner**
- [x] (2026-10-05: owner keeps it) Old PC copies of `.claude`, `lab` and `30-Research-Hub.md` stay in `pc-backup` on the PC (37 KB); PC edits saved on branch `pc-local-changes`. Do not delete.
- [ ] Pull in Obsidian, then double-click `setup_autopilot.bat` once ([[28-Autopilot]]) — **owner**
- [x] (checked 2026-10-04: sleep is Never on power and battery, PC plugged in) Keep shadow mode running, PC awake and plugged in — **owner**
- [x] First results written up: [[26-First-Shadow-Results]]
- [ ] Find a free results source for CS2 and LoL so they can use the confirmed rule — **assistant**
- [x] Data sync is automatic every 3 hours (autopilot)
- [ ] Read results after each sync and report — **assistant**
- [x] (2026-10-04) "Today" results report live (double-click `code/report_shadow.bat`)
- [x] Live feed + 2-second checks near the end + score log (shadow v2.6, [[29-Live-Feed-and-Score-Log]])
- [x] (2026-10-04) Live feed on the PC: connected, 0 errors, 36/36 checks agree with the 15-second reads
- [ ] First live end-window look (8 matches): 0 trades at 0.96-0.995 after the result, but all 8 had late-band trades (0.995-0.999, ~87,700 shares). Confirm over 1-2 days — **assistant**
- [x] (2026-10-05, [[R-2026-10-05]]) After 1-2 days: live end-window report: no gap after the result; market reacts ~1.5-2.5 min before Polymarket's score
- [ ] Save price and side of each after-result trade in end-window records (logging only) — **V1 session**
- [ ] Per sport: find a free result source and measure its lag vs Polymarket's score (score log); need ~2 min faster — **assistant (lab)**
- [ ] (started 2026-10-05 13:18 Tunisia, laptop) Polymarket Sports WebSocket lag test: `lab/sports_ws_record.py` records 6 h, `lab/sports_ws_lag.py` compares with end windows — **assistant**
- [ ] After a few days: test tennis "practically locked" rules on the score log — **assistant**
- [x] Shadow mode: enforce B7 (max 1 pretend buy per match and rule; second chances logged as `skip_second_buy`)
- [x] End-window study: record real watch time (`seconds_watched`), report leaves out pre-fix rows
- [x] Autopilot: restart shadow mode only when code changes, not for note edits ([[28-Autopilot]])
- [ ] Phase 1 ends after ~2 weeks or 100+ settled confirmed pretend trades — **both**

## PolySweeper Lab (automated research, from 2026-10-03)

- [x] Team of agents, idea board and daily routines set up ([[30-Research-Hub]])
- [x] Cloud network set to full trust (owner, 2026-10-03): agents can read web pages; live feed tested on the real server
- [x] (2026-10-04) Exa connected on claude.ai (works in new chats and the PC chat; free credit only, never add a card)
- [ ] Read the daily research note; tell the lab what to focus on — **owner** (whenever useful)
- [x] Fix confirmed 2026-10-04 00:35: `daily/` folder on main, a code update was picked up and synced within 30 s
- [x] (2026-10-04) #10 profitable wallets, first pass ([[R-2026-10-04-wallets]])
- [x] (2026-10-04 12:33 UTC) US sports (MLB, NFL, college football, NHL) added to shadow mode; PC restarted fine
- [ ] Rebuild the game situation at each buy of the best US-sports wallet: which situations never lose? — **assistant (lab)**
- [ ] Lab next: #18 paid UMA proposer: whitelist path, then a 3-day shadow proposer log (no wallet) — **assistant (lab)**
- [x] Overwatch post-result asks verified (2026-10-05): Bo3/BO5 score artefact; scorecheck fixed
- [x] Live locked-lines watcher on NFL (2026-10-04): nothing for sale on the winner; idea #17 rejected
- [x] (done 2026-10-04 by V1 session, no need for the lab) **Morning of 2026-10-05 (owner OK given):** fix `report_shadow.bat` crash on team names with hidden characters (UnicodeEncodeError, cp1252 console): in `shadow_report.py` `main()` add `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`, run tests, push (restarts shadow mode once) — **lab fixer (05:17 run)**

## Next: compare with the late band (Phase 2)

- [x] Record prices up to 0.999 and check results there too (logging only)
- [ ] Analyse the late band (0.995-0.999) on the same matches — **assistant**
- [ ] Compare both bands: trades/day, fills, thin/junk skips, losses, profit/trade, time to payout — **assistant**
- [ ] Decide which band(s) the real bot uses — **owner**

## Before any real money (from the audit)

- [ ] **Ready for real money checklist** written: [[32-Go-Live-Checklist]] (15 boxes, all must be ticked for one rule). Review and adjust the numbers — **owner**
- [x] (done 2026-10-04, see [[28-Autopilot]]) **Automatic go-back after a bad update:** after a code update the autopilot checks shadow mode is really running (live.json keeps updating for 3 minutes); if not, it returns to the last working commit, restarts and logs it. Test it once on purpose. Change `autopilot.py` very carefully — **V1 session**
- [ ] **Phone alerts:** a push notification when there is no new PC data for 4 hours, errors pile up, or any pretend loss happens (free method only; ask the owner before anything paid) — **V1 session**
- [x] (done 2026-10-04: `fill_check` lines in trades.jsonl) **Second-look check + public-trades check** on every pretend buy (fill rate for the checklist); ship together with the report fix so the PC restarts only once — **V1 session**
- [ ] Emergency stop from the phone (before real money) — **V1 session**

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
- [x] (2026-10-04) Automatic tests on GitHub for every code change (`.github/workflows/tests.yml`; warning only, the PC still pulls main)
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
