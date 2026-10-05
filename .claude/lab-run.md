# PolySweeper Lab — run procedure (read by the lab session every run)

The lab session ("PolySweeper Lab (daily research team)") gets two messages a day from routines:
the **full lab run** (05:17 Tunisia time) and the **health check** (17:43). Push finished work
directly to `main` (owner's standing rule, see CLAUDE.md).

## Full lab run

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
5. **Finish:** PushNotification (status "proactive") with a 4-6 line plain summary (what was checked,
   best new idea and evidence, problems found/fixed, what's next); end the turn with the same text.

## Health check

1. `git pull --rebase origin main`. Spawn ps-analyst (ask it to run the tests too); ps-fixer only for a real problem.
2. Append a section "Evening health check" to today's `PolySweeper-V1/Research/R-YYYY-MM-DD.md`
   (create the note with only that section if the morning run did not happen): PC data freshness,
   new trades/losses, live feed status, errors, anything fixed.
3. Commit and push as above (fixes only under ps-fixer's rules).
4. PushNotification **only if the owner should know**: PC data older than 4 hours, a new loss, new
   error types, a fix pushed, or the live feed failing. Otherwise end quietly with a one-line summary.

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
- Never mention a "friend" or another bot's author. Don't raise legal topics.
- Plain language for the owner (does not code, based in Tunisia).
- Cloud network: full access since 2026-10-03 (web pages, Polymarket REST APIs and websocket feed). If a
  site is blocked again, say so in the notification.
- If a run hits an error (tool, network, git), try to work around it; if blocked, say exactly what
  is blocked and what the owner can do, in the notification.
