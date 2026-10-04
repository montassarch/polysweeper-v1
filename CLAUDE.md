# CLAUDE.md — read this first

Private repo `montassarch/polysweeper-v1`: an **Obsidian vault + Python code** for a
Polymarket (global, not US) **sports "sweeper" bot**: buy the winner of a finished match
below $1 and hold to the $1 payout. **No real money yet: shadow mode only (pretend trades).**

## The owner

- Does not code. Explain in plain language, short steps, no jargon. Based in Tunisia.
- Goal: near-zero losses ("99% winning and minimise the 1%"). One loss at ~0.97 wipes out
  ~25 wins, so safety beats volume.
- Legal/compliance is handled privately by the owner: don't raise it.
- Never mention or ask about a "friend" / the author of the other bot.

## Layout

- `PolySweeper-V1/` — our bot. Start at `V1-Home.md`; **master to-do: `24-Task-List.md`**;
  safety ideas: `25-Zero-Loss-Strategy-Lab.md`; log of decisions: `00-Session-Log.md`.
- `PolySweeper-V2-Research/` — separate project: rebuild the late-band (0.995-0.999) approach
  from a white paper through our own research. Start at `V2-Home.md`.
- **Keep V1 and V2 unlinked** (no wikilinks between the two folders).
- `code/` — Python, standard library only. Tests: `cd code && python3 -m unittest discover -s tests`.
- Notes use Obsidian wikilinks (`[[Note-Name]]`) and YAML front matter. Update the task list,
  session log and home note when something changes.

## Code map (`code/polysweeper/`)

- `shadow.py` — shadow mode (watches live matches, reads real order books, pretend-buys 5
  shares). Three rules side by side: `confirmed` (ESPN football / OpenDota Dota 2 result),
  `score` (Polymarket's own score says this side won + ended flag), `price_only` (comparison).
  Junk-book filter, kill switch (`data/shadow/STOP`). Leagues: `code/shadow_leagues.txt`.
- `endwindow.py` — end-window study: winner's book for 15 min after a match is decided.
- `livefeed.py` — live order books via Polymarket's websocket (stdlib client, background thread,
  measuring only). Shadow v2.6 also re-checks matches near the end every 2 s and writes every
  score change to `code/data/shadow/daily/<date>.jsonl` (note 29). `--no-live` turns the feed off.
- `scorecheck.py` — parses Polymarket score (`000-000|2-1|Bo3`, tennis `6-3, 5-7, 6-2`).
- `autopilot.py` — runs on the owner's Windows PC (see below).
- `dashboard.py` — HTML dashboard with a live feed; `confirm.py`, `results_*.py` — results sources.
- **Desktop app** (`app/`, outside `code/`): `PolySweeper.exe` = `app/launcher.py` built by GitHub Actions
  (`.github/workflows/build-app.yml`, Windows, PyInstaller) and published to branch `app-build`; the autopilot
  installs it into `app/bin/` (git-ignored) and makes a desktop shortcut. The exe loads the screens from
  `app/polysweeper_app.py` (tkinter, read-only) at start; shadow mode feeds it via `code/data/shadow/live.json`
  (rewritten every ~2 s, not synced). Note 31. App tests: `code/tests/test_app.py`.
- Research scripts in `code/`: `trades_study.py` (public trades), `score_check_test.py`,
  `end_window_report.py`. Config: `code/config.json` (strict keys: unknown keys raise).

## The owner's PC (autopilot)

- Shadow mode runs 24/7 on the owner's Windows PC under `autopilot.py` (started at login).
- It **checks `main` on GitHub every minute**. A change inside `code/` stops shadow mode, pulls and
  restarts it, so **any code pushed to `main` goes live on the PC**. Keep `main` working; run tests
  first. Notes-only pushes are fast-forwarded without a restart (restarts cut end-window watches short).
- It commits/pushes only `code/data/shadow/{trades,events,errors}.jsonl` and `code/data/shadow/daily/`
  (every 3 h and on each code update). **Never edit those files by hand.** Always `git pull --rebase` before pushing.
- The owner cannot debug; changes to `autopilot.py` must be safe (it restarts itself on update).
- `.bat` files must keep CRLF (handled by `.gitattributes`).

## Polymarket facts that bit us

- Gamma `start_date` is the LISTING date; use `startTime` for the match start.
- CLOB needs a custom User-Agent; batch books via `POST /books`.
- Min order 5 shares; taker fee = shares x rate x p x (1-p), rate per market (0.03-0.05).
- Football settles on 90 minutes (extra time/penalties excluded); voids pay 50/50.
- Data API (`data-api.polymarket.com/trades`) gives every public trade with wallet.
- Polymarket score field is wrong (teams swapped) about 1 in 4,000: use it as a veto, never alone.

## Where things stand (2026-10-03)

- Price-only pretend buys win often but all happen during play, and that is how losses happen:
  67 wins, 4 losses, -$8.42 by 16:31 on Oct 3 (comebacks in CS2 Bo3s and in tennis).
- Score-check/confirmed rules made 0 buys: **within 15 s of a result the winner's book is
  empty** (0.999 bots clear it). First look, 5 matches; the PC's end-window data will confirm.
- Public trades study: every loss at 0.99+ was a buy made before the match was really over;
  real late-band sweepers earn ~0.15% per trade at 0.999.
- Open question: what strategy gets fills safely (faster feed, resting orders before the end,
  or in-play only when the result is locked). See note 26 and the task list.

## Sessions (owner's setup, 2026-10-04)

- **PolySweeper V1** (cloud session in the Claude desktop app) = the **main/core session** for the bot.
- **CLI on the owner's laptop** (`polysweeper-work`, reachable by Remote Control from the phone) = where the
  owner prompts and talks; it also controls the laptop (live data, shadow mode, autopilot). It forwards
  bot work and decisions to PolySweeper V1 by message (cloud sessions cannot message back: read their
  results from `main`).
- **PolySweeper Lab** = automated daily research (below). Every session shares one memory: this repo
  (CLAUDE.md, task list, session log). Always `git pull --rebase` first and write results there.

## PolySweeper Lab (automated research team)

- Daily routines (claude.ai/code Routines): **full lab run 05:17 Tunisia time** and **health check
  17:43**. Both send a message to the permanent session "PolySweeper Lab (daily research team)",
  which follows `.claude/lab-run.md` (the run procedure; edit it to change what the lab does).
- Project skills: `.claude/skills/` — `polymarket-data` (APIs and traps), `shadow-data` (reading results), `safe-deploy` (pushing to main).
- Plugins (project scope): `context7` (code library docs) and `frontend-design` (page design), both Anthropic official, moved here from user scope 2026-10-04.
- Plugin `watch@claude-video` (project scope, reviewed 2026-10-04): watch a video link (yt-dlp + ffmpeg frames + captions). **Free mode only**: engine local, speech fallback none, detail efficient (`~/.config/watch/.env`, no keys). Never add a Gemini/Groq/OpenAI key without the owner's OK.
- Agents (each has a fixed `effort` in its front matter to save usage: analyst low, fixer/tester medium,
  researcher/red-team high): `.claude/agents/ps-researcher.md` (most important), `ps-red-team`, `ps-tester`, `ps-analyst`,
  `ps-fixer`. Shared memory: idea board `PolySweeper-V1/30-Research-Hub.md`, daily notes
  `PolySweeper-V1/Research/R-<date>.md`.
- Research scripts go in `lab/` (outside `code/`, so the owner's PC is not restarted); small results in
  `lab/results/`, raw downloads in `lab/data/raw/` (git-ignored).
- Cloud network: full access (the owner set "full trust" on 2026-10-03): web pages, Polymarket's REST APIs
  and its websocket feed all work in the cloud.

## Working rules

- **Plugins and skills: project scope only, installed automatically when the owner asks.** Standing
  permission (2026-10-03): when the owner asks for plugin or skill suggestions, choose suitable ones, tell
  the owner in one line what you are adding, and add them without asking again.
  - Plugins: project scope only, recorded in this repo's `.claude/settings.json` (`enabledPlugins`, plus
    `extraKnownMarketplaces` if needed), or `claude plugin install <name> --scope project` from the repo root.
    Skills: files in `.claude/skills/<name>/` in this repo. Never install user-wide or on the claude.ai account.
  - Only from trusted sources (Anthropic, verified partners, well-known public repos). Read every file
    before adding it; nothing that touches money, orders, wallets or keys. Commit and push like any change.
  - Do not add plugins or skills on your own initiative (the lab may suggest them in its notes).

- Never place real orders or handle wallet keys without the owner's explicit go-ahead.
- **Nothing that costs money without asking first** (owner, 2026-10-04): paid APIs or credits (e.g. Exa beyond its free tier), subscriptions, servers, paid data or plugins. Check the price, tell the owner plainly what is free and what could be charged, and wait for a yes. Never add a card or buy credits.
- Push finished work to `main` with a clear commit message; keep commits small.
- Keep tool output short (no raw API dumps); write findings into the vault, not just chat.
