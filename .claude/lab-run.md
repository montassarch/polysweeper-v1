# PolySweeper Lab — run procedure (read by the lab session every run)

The lab session ("PolySweeper Lab (daily research team)") gets two messages a day from routines:
the **full lab run** (05:17 Tunisia time) and the **health check** (17:43). Push finished work
directly to `main` (owner's standing rule, see CLAUDE.md).

## Full lab run

1. **Setup:** `git pull --rebase origin main`. Read `CLAUDE.md`, `PolySweeper-V1/30-Research-Hub.md`,
   the 2 newest notes in `PolySweeper-V1/Research/`, the last 30 lines of `PolySweeper-V1/00-Session-Log.md`.
   Agents are in `.claude/agents/` (ps-fixer, ps-analyst, ps-researcher, ps-red-team, ps-tester): spawn
   them with the Agent tool by that subagent_type; if unavailable, use a general-purpose agent with the
   agent file's full text at the top of its prompt. The owner asked for this team.
2. **Team** (see "Keep usage low"): (a) ps-analyst (+ ps-fixer only if needed); (b) ps-researcher with today's UTC date, a short
   idea-board summary, the **"Owner's focus" list in the Research Hub (goes ahead of the lab's own picks)**,
   and the analyst's key numbers; researcher and tester load the `polymarket-data` skill
   (`.claude/skills/polymarket-data/SKILL.md`) before touching Polymarket's APIs: 2-4 questions, at least one brand-new
   out-of-the-box angle and one deepening the most promising idea, no repeats without new evidence;
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

## Keep usage low (owner, 2026-10-04: "use less, but stay productive")

The lab runs on the owner's Claude plan; a full run used ~$8-10 of usage and once hit the 5-hour limit.
- **Morning:** ps-analyst always. ps-fixer only if the analyst or a quick `git log`/`errors.jsonl` look
  shows a problem (tests failing, new error type, PC data older than 4 h, restart loop) or a bug to fix.
- **Researcher:** 2-3 questions, reuse earlier results in `lab/`, no re-downloading what is already there.
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
