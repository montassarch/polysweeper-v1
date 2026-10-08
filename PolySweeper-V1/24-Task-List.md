---
title: Master Task List
tags: [polysweeper, tasks, todo]
created: 2026-10-02
---

# Master task list

Back to [[V1-Home]] · Logic and audit: [[23-Bot-Logic-Spec-and-Audit]] · **Until 21 Oct: [[34-Fill-Scoreboard]]**

One place for everything. Older notes keep their own checklists for context;
this list is the one to follow. Owner = who does it.

## Road to real money: 1 November 2026, $20 (owner decision 2026-10-05)

Owner: "by 1 November I start with $20. Until the end of October the project must be well studied,
well built, the logic there, bugs fixed, and above all no losses on trades bought after the end."
The gate is still [[32-Go-Live-Checklist]] (now set to $20). If no rule passes by 31 Oct, tell the
owner plainly and propose a new date; never lower the bar to make a rule pass.

**Week 1 (6-12 Oct): find the rule that gets real fills safely**
- [x] (2026-10-05: score rule now covers MLB/NFL/CFB/NHL after the end; NBA when its season starts) Add US sports to shadow mode (MLB postseason, NFL, NHL, college football; NBA from ~21 Oct) with an
  "after the end" rule at ~0.99 (Research Hub #14). Strongest lead. — **V1 session**
- [x] (2026-10-05: rule `mlb_lead7` in shadow mode) MLB "lead 7+ after 8 innings" shadow rule (Research Hub focus #1). — **V1 session**
- [ ] ~21 Oct: check NBA score order on settled games, then add NBA to `shadow_leagues.txt`. — **V1 session**
- [ ] Small: HTML dashboard tabs don't list `mlb_lead7` yet (reviewer note). — **V1 session**
- [x] (parked 2026-10-06: best wallet is a maker + fast in-play sniper, nothing copyable) Best-wallet copy study (#10, #14). — **lab**
- [x] (rejected 2026-10-06: Flashscore ~42 s ahead but the band is gone 77 s earlier) Flashscore lag test (#20). — **lab**
- [ ] Finish the Sports WebSocket lag result. — **assistant**
- [x] (2026-10-05, ntfy topic in code/config.json) Phone alerts (free ntfy app). **Owner said yes 2026-10-05**, installing ntfy (Philipp Heckel, free, iPhone). Topic: `polysweeper-4463a025f72df6b3` (keep private; server ntfy.sh). Owner subscribes in the app; V1 builds the sender (stdlib HTTP POST to https://ntfy.sh/<topic>, alerts: no PC data 4 h, errors piling up, any pretend loss, crash/restart loop) and sends one test message. — **owner (subscribe) + V1 (build)**

**21 Oct: choose the ONE rule from [[34-Fill-Scoreboard]]** (owner 2026-10-07; was 17 Oct). Note: this leaves ~10 days of shadow mode before 1 Nov instead of 14, and the [[32-Go-Live-Checklist]] still needs 200+ pretend trades with 0 losses on that rule; if it can't be met by 31 Oct, propose a new date. — **both**

**Weeks 2-3 (13-26 Oct): make it solid**
- [ ] Full bug hunt on the chosen rule: red team + reviewer audit of the whole buy path. — **lab + V1**
- [ ] Test the automatic go-back once on purpose; emergency stop from the phone. — **V1**
- [ ] 7 days in a row with no crash and no data gap over 1 hour. — **PC (watch)**
- [ ] Build the real-order part switched OFF (dry run: builds the order, never sends it). No wallet
  keys until the owner says so. — **V1**
- [ ] Check the cost of depositing and withdrawing $20. — **assistant**

**27-31 Oct: final check**
- [ ] Go through [[32-Go-Live-Checklist]] box by box with the owner. — **both**
- [ ] Owner creates the wallet and deposits $20; owner says **"go"**. — **owner**

**After 1 Nov (owner plan 2026-10-05):** once the $20 test is proven, the owner adds $100-200 a month for a year.
- [ ] Before each top-up: monthly report (wins, losses, profit, fill sizes) and check that bigger orders still fill at our price. — **assistant**
- [ ] Write the size rules: max per trade as a % of the total, max open trades, and the ceiling where shares for sale run out. — **V1 + lab**

## Now: running test (Phase 1)

**Speed plan (laptop session 2026-10-06; owner: "your project, make it work", full permission; bar updated 2026-10-08: see [[34-Fill-Scoreboard]]):**
- [x] (2026-10-07: 0 of 36 filled at the safe moment; leaning NO, kept running in the background) **0.999 queue test** (owner yes 2026-10-07 02:45): `lab/queue999.py` running on the laptop (restarted 2026-10-07 04:00, to ~2026-10-08 03:00 Tunisia), read-only; raw output local in `lab/data/raw/queue999/`, **summary pushed every 3 h to `lab/results/queue999-summary.json`** (cloud lab can read it). Question: if we rest a 5-share buy at 0.999 once a match is over, does it fill, and how fast? Next laptop session writes the answer in that day's research note. Early: 0 of 7 filled (too few to judge). First look: queues are big (Dodgers game ~1M shares at 0.999, LoL 45k).
- [ ] **MAIN JOB (owner 2026-10-07): late US-games resting bids** (scoreboard row 4). `lab/queue_late.py` running on the laptop from 2026-10-07 16:44 to ~21 Oct (read-only; summary pushed every 3 h to `lab/results/queue-late-summary.json`; if the laptop restarts, start it again: `py lab/queue_late.py 300`). Cloud lab: same question on public history. — **laptop + lab**
- [x] (done 2026-10-07: ESPN ~140 s ahead, 11/11 agree, 0 shares left; safety source only) **Tennis end race** running on the laptop until ~2026-10-07 13:30 Tunisia (`lab/tennis_end_race.py`, output `lab/data/raw/tennis_end_race/` is LOCAL ONLY, git-ignored): next laptop session reads it and reports: ESPN "final" vs Polymarket "ended" (seconds), winner agreement, shares left at 0.96-0.995 at the ESPN moment. Write the result into today's research note so the lab sees it.
- [ ] **NARROWED PLAN (owner yes 2026-10-08), replaces the CEO plan below until 21 Oct:** only (1) row 4 late US-games
  resting bids with a rule usable live (hindsight "last 10 min" guard is not enough: live clock rule still had 6 loser
  fills), (2) row 9 stock/ETF ladder last-hour sweep, (3) backup research: market making (both sides, spread +
  rewards). 21 Oct: neither near 300 safe fills with 0 losses -> switch to the backup, owner decides. Details:
  [[30-Research-Hub]] "Owner's focus". — **lab + assistant**
- [ ] (superseded 2026-10-08 by the narrowed plan) **CEO plan (owner 2026-10-07: "you are the CEO, plan everything")**, in order — **assistant + lab**:
  1. Row 4 keeps running to 21 Oct (main job). 2. Row 8 late football 2+ goals: tester measures on past matches
  (next free tester run). 3. Row 7 elections: Brazil runoff 25 Oct, recorder ready by 23 Oct; US 3 Nov.
  4. Usage budget: lab runs save hourly; heavy laptop work outside 08:00-12:00 Tunisia so the 09:00 researcher isn't starved.
  5. Weekly verdict to the owner every Sunday (what works, what died, next bets).
- [ ] If ESPN is clearly faster and shares are left: propose a shadow rule "confirmed tennis" (ESPN final + Polymarket score agrees), owner decides.
- [ ] CS2 (and every other traded sport) second result source: owner's focus #1 in [[30-Research-Hub]].
- [ ] Two sources must agree for any real-money buy (Polymarket score + outside source).
- [ ] Waiting (resting) orders: scoreboard rows 3 and 4; less-watched leagues where books stay non-empty longer.
- [ ] If every free feed is too slow: tell the owner plainly (pay for a pro feed vs very few trades).

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
- [x] (confirmed 2026-10-07 on 358 matches: after-result money is at 0.999, [[R-2026-10-07]]) First live end-window look (8 matches): 0 trades at 0.96-0.995 after the result, but all 8 had late-band trades (0.995-0.999, ~87,700 shares). Confirm over 1-2 days — **assistant**
- [x] (2026-10-05, [[R-2026-10-05]]) After 1-2 days: live end-window report: no gap after the result; market reacts ~1.5-2.5 min before Polymarket's score
- [x] (done 2026-10-05) Save price and side of each after-result trade in end-window records (logging only) — **V1 session**
- [ ] Per sport: find a free result source and measure its lag vs Polymarket's score (score log); need ~2 min faster — **assistant (lab)**
- [ ] (started 2026-10-05 13:18 Tunisia, laptop) Polymarket Sports WebSocket lag test: `lab/sports_ws_record.py` records 6 h, `lab/sports_ws_lag.py` compares with end windows — **assistant**
- [ ] After a few days: test tennis "practically locked" rules on the score log — **assistant**
- [ ] (owner 2026-10-06) **Fix the in-play losses:** 8 price_only losses by Oct 6 (CS2 3, tennis 4, NFL 1), all comebacks or a wrong "ended" flag. Shadow keeps running unchanged meanwhile. Find a "locked" check (per sport) that blocks all 8 and keeps as many wins as possible; test on recorded data, then propose to V1 — **assistant (laptop)**
  - [x] (done 2026-10-06) (owner yes 2026-10-06) Score check "against" blocks price_only buys (would have saved loss #1); sent to V1 by message — **V1 session**
  - [ ] (started 2026-10-06 12:05 Tunisia, laptop, 18 h, read-only) `lab/official_end_recorder.py`: shares left at <=0.995 when MLB/NHL say "Final"? Pass: 30%+ of games, latency under 10 s. Output `lab/data/raw/official_end/` — **assistant**
- [x] (done 2026-10-06) (owner yes 2026-10-06) Phone alerts: no alert for harmless live-feed drops ("feed closed", reconnects in seconds); alert only if the feed is down 5+ min. Sent to V1 by message — **V1 session**
- [x] Shadow mode: enforce B7 (max 1 pretend buy per match and rule; second chances logged as `skip_second_buy`)
- [x] End-window study: record real watch time (`seconds_watched`), report leaves out pre-fix rows
- [x] Autopilot: restart shadow mode only when code changes, not for note edits ([[28-Autopilot]])
- [ ] Phase 1 ends after ~2 weeks or 100+ settled confirmed pretend trades — **both**

## PolySweeper Lab (automated research, from 2026-10-03)

- [x] Team of agents, idea board and daily routines set up ([[30-Research-Hub]])
- [x] Cloud network set to full trust (owner, 2026-10-03): agents can read web pages; live feed tested on the real server
- [x] (2026-10-04) Exa connected on claude.ai (works in new chats and the PC chat; free credit only, never add a card)
- [x] (duplicate: running since 2026-10-06 12:05, see Phase 1) Run `lab/official_end_recorder.py` on the laptop (MLB+NHL, ~6 h, read-only; pass bar 5+ shares at <=0.995 at "Final" in 30%+ of games) — **owner/laptop session** (2026-10-06)
- [ ] Read the daily research note; tell the lab what to focus on — **owner** (whenever useful)
- [x] (2026-10-05, owner) New idea agent `ps-ideas` (effort max, skill `idea-methods`): 15+ ideas a day, top 3-5, one pick for research
- [x] (2026-10-05, owner) Research agent refocused: deep dives on data, news and trends, effort max
- [x] (2026-10-05, owner) One agent per routine, spread over the day (Tunisia): 01:00 analyst, 05:00 ideas, 09:00 research, 13:00 red team, 17:00 tester + phone summary, 21:00 health check; old 05:17 / 17:43 routines off
- [ ] Check the first full day of the split schedule (6 Oct): did every step run and hand over through the note? — **assistant**
- [ ] After ~1 week: is usage OK with two agents on max? If the limit is hit, lower ideas or research to "high" — **assistant + owner**
- [ ] Decide: add the free Sports WebSocket as a second, faster score source (after the final lag result) — **owner, then V1**
- [x] Fix confirmed 2026-10-04 00:35: `daily/` folder on main, a code update was picked up and synced within 30 s
- [x] (2026-10-04) #10 profitable wallets, first pass ([[R-2026-10-04-wallets]])
- [x] (2026-10-04 12:33 UTC) US sports (MLB, NFL, college football, NHL) added to shadow mode; PC restarted fine
- [ ] Rebuild the game situation at each buy of the best US-sports wallet: which situations never lose? — **assistant (lab)**
- [x] (done 2026-10-05: `mlb_lead7`) Decide: add shadow-only MLB rule "lead 7+ after 8 innings" (Stats API live feed, lead ≥7 + runners on base, no buy if price <0.98, game-ID match) — **owner, then V1**
- [ ] (parked until after 21 Oct) Lab: #18 paid UMA proposer: whitelist path, then a 3-day shadow proposer log (no wallet) — **assistant (lab)**
- [x] Overwatch post-result asks verified (2026-10-05): Bo3/BO5 score artefact; scorecheck fixed
- [x] Live locked-lines watcher on NFL (2026-10-04): nothing for sale on the winner; idea #17 rejected
- [x] (done 2026-10-04 by V1 session, no need for the lab) **Morning of 2026-10-05 (owner OK given):** fix `report_shadow.bat` crash on team names with hidden characters (UnicodeEncodeError, cp1252 console): in `shadow_report.py` `main()` add `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`, run tests, push (restarts shadow mode once) — **lab fixer (05:17 run)**

## Next: compare with the late band (Phase 2)

- [x] Record prices up to 0.999 and check results there too (logging only)
- [ ] Analyse the late band (0.995-0.999) on the same matches — now the 0.999 queue test (scoreboard row 3) — **assistant**
- [ ] Compare both bands: trades/day, fills, thin/junk skips, losses, profit/trade, time to payout — **assistant**
- [ ] Decide which band(s) the real bot uses — **owner**

## Before any real money (from the audit)

- [ ] **Ready for real money checklist** written: [[32-Go-Live-Checklist]] (15 boxes, all must be ticked for one rule). Review and adjust the numbers — **owner**
- [x] (done 2026-10-04, see [[28-Autopilot]]) **Automatic go-back after a bad update:** after a code update the autopilot checks shadow mode is really running (live.json keeps updating for 3 minutes); if not, it returns to the last working commit, restarts and logs it. Test it once on purpose. Change `autopilot.py` very carefully — **V1 session**
- [x] (2026-10-05, ntfy, test received by the owner) **Phone alerts:** a push notification when there is no new PC data for 4 hours, errors pile up, or any pretend loss happens (free method only; ask the owner before anything paid) — **V1 session**
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
- [ ] Resting buy orders: dropped 2026-10-03, **reopened 2026-10-07** (after-result money goes to resting 0.999 bids; late US games at 0.98+): scoreboard rows 3 and 4 — **lab**
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
