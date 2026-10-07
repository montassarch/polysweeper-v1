# PolySweeper Lab — run procedure (read by the lab session every run)

Since 2026-10-05 (owner: "different time, different schedule, so usage is spread") the lab runs as
**six separate routines, one agent each**, every one a fresh cloud session. Each run reads only its own
step below plus today's note, where the earlier steps left their results. Times are Tunisia time.

## Split schedule (one agent per run)

**One shared goal until 2026-10-21 (owner 2026-10-07): "Which method gets filled with zero losses?"**
Scoreboard: `PolySweeper-V1/34-Fill-Scoreboard.md`. Every step works on a row of that table (or a new method
that could fill with 0 losses) before anything else. Measuring beats brainstorming: new ideas only if they
answer the question.

**Every step:** `git pull --rebase origin main`; read the "Rules for every run" section below and your
step only (don't read whole big files). Today's note = `PolySweeper-V1/Research/R-YYYY-MM-DD.md` (UTC date;
if missing, create it with YAML front matter: title, tags [polysweeper, research, daily], created, and a link
back to [[30-Research-Hub]]). Spawn the named agent with the Agent tool (subagent_type = its name; if
unavailable, a general-purpose agent with the agent file's full text at the top of its prompt). Give it a
short prompt that points to files, not pasted text. Write **your step's section** into today's note, then
commit, `git pull --rebase origin main`, push (retry after 2, 4, 8, 16 s). If an earlier step's section is
missing (that run failed), work with what exists and say so in one line. Never touch `code/` except
ps-fixer under its rules.

1. **01:00 Analyst:** ps-analyst (+ ps-fixer only for a real problem: tests failing, new error type, PC data
   older than 4 h, restart loop). Sections "System health" and "Shadow results". No notification unless
   something is broken.
   **Loss review (owner 2026-10-06), new settled losses since the last run:**
   - Loss on a **safe rule** (any rule except `price_only`: confirmed, score, mlb_lead7, later official_end):
     **red alarm.** Write a section "Loss card" (rule, market, side, price, score/period at buy, ended flag, how
     the match turned, time from buy to result) and send the owner a push notification ("loss on safe rule X").
   - Loss on `price_only`: one line per loss under "Shadow results" (sport, side, price, score at buy). No card.
2. **05:00 Ideas (Monday and Thursday only, owner 2026-10-06: ideas pile up faster than they can be tested):** ps-ideas (effort max). Section "New ideas": raw list (one line each, kept or kill reason),
   top 3-5 cards, and a line `Pick for research: <idea>`. Until 2026-10-21 only ideas that could get real fills with 0 losses (scoreboard question). Add the top cards to the idea board in
   `30-Research-Hub.md` with status "new".
3. **09:00 Research:** ps-researcher (effort max) with today's UTC date, the "Road to 1 Nov" priorities below,
   the scoreboard (`34-Fill-Scoreboard.md`: work on the most promising NOT YET row first), the hub's "Owner's focus" list, the analyst's key numbers and the ideas pick from today's note (on days with no ideas run: the most
   promising untested idea on the hub's idea board, status "new" or "promising"); load the
   `polymarket-data` skill. Sections "Road to 1 Nov" (2-4 lines, put at the top of the note), "News and
   trends", "Research". Update the idea board (status, one line why, date). Side task: the hub's "MCP servers" item (small, after the main work).
   **Loss review comes first (owner 2026-10-06):** if today's note has a "Loss card" (safe-rule loss), that is
   the top priority before anything else: find the cause, propose a fix (a check that would have blocked it),
   test the fix on ALL recorded pretend trades (losses blocked vs wins lost), section "Loss review". **Sundays:**
   weekly review of the week's `price_only` losses together: look for patterns (sport, score state, price,
   time left) and propose a safety check only if it blocks losses without costing more in wins. Fixes are
   proposals only: nothing changes in the bot without the owner's yes. Rejected fixes go to `33-Rejected-Ideas.md`.
4. **13:00 Red team (odd days only, owner 2026-10-06 to save usage):** ps-red-team on the new or upgraded ideas in today's and yesterday's notes. If there are none, write
   "Red team: nothing new today" and stop (don't spawn the agent). Section "Red team".
5. **17:00 Tester:** ps-tester on the one best idea measurable today with public APIs (scripts in `lab/`), taken from a NOT YET row of the scoreboard.
   **Update `34-Fill-Scoreboard.md` every day** (fills, losses, money per day, verdict per row, one line in its "Changes").
   Sections "Tests and numbers" and "Decisions and next steps". Then finish the day's note: "Summary for the
   owner" (5 short plain lines) at the top, the hub's daily-notes list (newest first), one line in
   `00-Session-Log.md`, real new tasks in `24-Task-List.md`. PushNotification (status "proactive") with the day's
   report. **Owner (2026-10-05): keep it simple, only the report, no advice and no tasks.** 3-5 short plain
   lines of facts, **starting with the scoreboard in short form** (one line per method: name, fills, losses, YES/NO/NOT YET), then: bot results (wins, losses, pretend profit), best new idea in one line, what research and
   the test found, anything broken. No "you should", no to-dos, no next steps.
6. **21:00 Health check (even days only, owner 2026-10-06 to save usage; the PC's phone alerts cover the other days):** follow "Health check" below.

## Full lab run (old all-in-one run; only when the owner asks for one)

1. **Setup:** `git pull --rebase origin main`. Read `CLAUDE.md`, `PolySweeper-V1/30-Research-Hub.md`,
   the 2 newest notes in `PolySweeper-V1/Research/`, the last 30 lines of `PolySweeper-V1/00-Session-Log.md`.
   Agents are in `.claude/agents/` (ps-fixer, ps-analyst, ps-ideas, ps-researcher, ps-red-team, ps-tester): spawn
   them with the Agent tool by that subagent_type; if unavailable, use a general-purpose agent with the
   agent file's full text at the top of its prompt. The owner asked for this team.
2. **Team** (see "Keep usage low"): (a) ps-analyst (+ ps-fixer only if needed); (a2) **ps-ideas** (effort max, owner 2026-10-05:
   "I need ideas"): 15+ raw ideas, top 3-5 cards, one pick for the researcher; put its top cards and the
   raw list (one line each) in the daily note under "New ideas"; (b) ps-researcher (effort max, owner 2026-10-05: deep dives on data, news and trends), given ps-ideas' pick to check in depth, with today's UTC date, a short
   idea-board summary, the **"Owner's focus" list in the Research Hub (goes ahead of the lab's own picks)**,
   and the analyst's key numbers; researcher and tester load the `polymarket-data` skill
   (`.claude/skills/polymarket-data/SKILL.md`) before touching Polymarket's APIs: 1-3 deep questions plus a news scan,
   no repeats without new evidence; the daily note gets a "News and trends" section;
   (c) ps-red-team on new/upgraded ideas; (d) ps-tester on the 1-2 best ideas measurable today with
   Polymarket's public APIs (scripts in `lab/`, never `code/`). Build on earlier days.
3. **Write up:** `PolySweeper-V1/Research/R-YYYY-MM-DD.md` (UTC date; YAML front matter: title, tags
   [polysweeper, research, daily], created; link back to [[30-Research-Hub]]). Sections: Summary for the
   owner (5 short plain lines), System health, Shadow results, Research (idea cards with sources),
   Red team, Tests and numbers, Decisions and next steps. Update the idea board (status, one line why,
   date) and its daily-notes list (newest first); one line in `00-Session-Log.md`; real new tasks in
   `24-Task-List.md`.
4. **Save:** commit, `git pull --rebase origin main`, push to `main`. Notes, `lab/`, `.claude/` do not
   restart the owner's PC; `code/` does: code changes only via ps-fixer's rules (tests + 2-minute
   scratch run + ps-reviewer verdict SHIP), at most one code push per run. Retry failed pushes after 2, 4, 8, 16 s.
5. **Finish:** PushNotification (status "proactive") with a simple 3-5 line report of facts only (no advice,
   no tasks); end the turn with the same text.

## Health check

1. `git pull --rebase origin main`. Spawn ps-analyst (ask it to run the tests too); ps-fixer only for a real problem.
2. Append a section "Evening health check" to today's `PolySweeper-V1/Research/R-YYYY-MM-DD.md`
   (create the note with only that section if the morning run did not happen): PC data freshness,
   new trades/losses, live feed status, errors, anything fixed.
3. Commit and push as above (fixes only under ps-fixer's rules).
4. PushNotification (simple report, facts only, no advice or tasks) **only if the owner should know**: PC data older than 4 hours, a new loss, new
   error types, a fix pushed, or the live feed failing. Otherwise end quietly with a one-line summary.
5. **Phone alert if the PC went quiet** (the PC cannot alert about itself when it is off): if the newest
   commit touching `code/data/shadow/` on main is more than 4 hours old, send one ntfy alert (topic =
   `ntfy_topic` in `code/config.json`), at both the morning run and the health check:
   `curl -s -H "Title: PolySweeper" -H "Priority: high" -d "No new data from the PC for N hours. Is it on?" https://ntfy.sh/<topic>`

## Road to 1 November (owner decision 2026-10-05: real money starts 1 Nov 2026 with $20)

Plan: `PolySweeper-V1/24-Task-List.md`, section "Road to real money". Until then the lab's priorities are,
ahead of everything else (including the hub's "Owner's focus" list):
1. **Best-wallet copy study, US sports after the end (#10/#14):** which sports, how many seconds after the
   end, what sizes, and how many fills a day we could really get at about 0.99.
2. **Flashscore lag test (#20):** how many seconds before Polymarket's score / the sports websocket does a
   free score site show the result?
3. **From mid-October:** red-team the one chosen rule and its whole buy path (data source → decision →
   order → settlement).
Every daily note starts with a section **"Road to 1 Nov"** (2-4 lines: where each priority stands), before the
summary for the owner.

## Keep usage low (owner, 2026-10-04: "use less, but stay productive")

The lab runs on the owner's Claude plan; a full run used ~$8-10 of usage and once hit the 5-hour limit.
- **Morning:** ps-analyst always. ps-fixer only if the analyst or a quick `git log`/`errors.jsonl` look
  shows a problem (tests failing, new error type, PC data older than 4 h, restart loop) or a bug to fix.
- **Ideas:** every full run (owner asked; effort max). Not in the evening health check.
- **Researcher:** 1-3 deep questions + news scan (effort max), reuse earlier results in `lab/`, no re-downloading what is already there.
- **Red team:** only new or upgraded ideas; skip when there are none. **Tester:** one idea per run.
- **Evening health check:** ps-analyst only (it runs the tests too); ps-fixer only for a real problem.
- Prompts to agents: short, point to files instead of pasting; ask for reports under ~40 lines.
- Lead: don't read big files yourself; write the daily note compactly.

## Rules for every run

- Never place orders, never touch wallets or keys. Research and pretend trades only.
- Never edit `code/data/shadow/*` by hand. Keep V1 and V2 notes unlinked.
- **Rejected ideas list** (owner 2026-10-06): whenever your step says no to an idea (ps-ideas raw-list kills,
  researcher, red team or tester rejects, or parks it), add one plain row to `PolySweeper-V1/33-Rejected-Ideas.md`
  (date, idea, who, why, note link). Don't delete rows; if an idea comes back, say so in its row.
- Never mention a "friend" or another bot's author. Don't raise legal topics.
- Plain language for the owner (does not code, based in Tunisia).
- Cloud network: full access since 2026-10-03 (web pages, Polymarket REST APIs and websocket feed). If a
  site is blocked again, say so in the notification.
- If a run hits an error (tool, network, git), try to work around it; if blocked, say exactly what
  is blocked and what the owner can do, in the notification.

- **Phone alerts:** any shadow or autopilot run outside the owner's PC (cloud, lab, scratch runs) must set `POLYSWEEPER_NO_ALERTS=1`, or it alerts the owner's phone.
