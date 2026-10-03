---
title: Autopilot (hands-free shadow mode)
tags: [polysweeper, v1, shadow, autopilot]
created: 2026-10-03
---

# Autopilot: shadow mode with no clicks

Back to [[V1-Home]] · Running shadow mode by hand: [[17-Run-Shadow-On-Your-PC]]

## What it does

| When | What happens |
|---|---|
| You log in to Windows | The autopilot starts by itself (a minimised window called "PolySweeper autopilot") |
| At start | Pulls the latest version from GitHub, then starts shadow mode |
| Every minute | Checks GitHub. If the update changes code, it stops shadow mode cleanly, pushes the data, pulls, restarts it |
| Every minute, notes-only update | Pulls the notes and leaves shadow mode running (no restart, no data push) |
| Every 3 hours | Commits and pushes the shadow data (trades, events, errors) so the results can be read |
| Shadow mode crashes | Restarts it after 30 seconds |
| The autopilot itself is updated | Restarts itself |

It only ever commits the shadow data: the three files (trades, events, errors) and the `daily`
folder (score log and live detail, one file per day, see [[29-Live-Feed-and-Score-Log]]).
Your notes are not touched.
It places **no orders**: shadow mode only reads public prices.

## One-time setup (owner)

1. In Obsidian: **Pull**.
2. In the `code` folder, double-click **`setup_autopilot.bat`**.

Setup does three things: adds the autopilot to Windows startup (your user
only, no admin needed), sets sleep and hibernate to **Never while plugged in**,
and starts the autopilot now (it stops any old shadow window first).

## Day to day

- Keep the PC **on and plugged in**. That is all.
- Watch: double-click `dashboard_live.bat` whenever you like.
- **Don't** also start `run_shadow.bat` while the autopilot runs (that would run
  shadow mode twice).
- Pause: `stop_shadow.bat` stops shadow mode and the autopilot until the next login
  (or double-click `autopilot.bat` to start again).
- Turn it off for good: `remove_autopilot.bat`.
- Log: `code/data/shadow/autopilot.log` (what it did and when; any pull/push problem).

## If something goes wrong

- **A pull fails** (e.g. a file conflict): it keeps running the current version and
  writes the reason in the log.
- **A push fails** (e.g. no internet): it tries again 3 hours later.
- **Git not found:** install "Git for Windows" (git-scm.com). Obsidian Git uses it too.

## Why notes-only updates no longer restart shadow mode (2026-10-03)

Every restart cuts short the 15-minute end-window watches that are running (6 of the first 9
were cut short). Now only a change inside the `code` folder restarts shadow mode. A notes-only
update is brought in with a "fast-forward": git rewrites only the changed notes and never touches
the data files shadow mode is writing. If anything is in the way (a note edited on the PC, data
not yet pushed), git changes nothing and the autopilot uses the normal stop-pull-restart path.
Tested with a fake GitHub and PC copy (automatic tests). Data still syncs every 3 hours and on
every code update.

## How it was tested (2026-10-03)

In a sandbox with a fake GitHub and a fake PC copy: an update pushed while it ran
was pulled and shadow mode restarted within seconds; data was pushed; a simulated
crash restarted shadow mode; the stop file stopped everything; an update to the
autopilot itself made it restart.

## Live test on the owner's PC (2026-10-03)

A small update was pushed at about 13:33 UTC to check that the owner's autopilot
pulls it, restarts shadow mode and pushes the shadow data back.

## 2026-10-03 evening: the PC still runs the first autopilot version (owner action needed once)

Found by the lab's health check and confirmed:
- The PC checks GitHub only every **10 minutes** (updates at 18:07, 18:47 and 19:02 were taken at
  18:13, 18:52 and 19:12). The newer autopilot checks every minute.
- A notes-only update at 19:02 still restarted shadow mode. The newer autopilot does not do that.
- The new `daily` folder (score log) never reached GitHub. The newer autopilot syncs it.

**Why:** the first version (13:26) had a bug. It brings in the update while sending the data, and
then looks for its own update in a second, empty pull, so it never sees that it was updated
itself. That bug was fixed at 13:50, but a running program cannot pick up its own fix. Shadow mode
itself is up to date (v2.6, live feed connected on the PC, 97-98% agreement), because the
autopilot restarts it with the new files each time.

**Fix (once):** restart the autopilot. Either restart the PC (the autopilot starts by itself at
login), or in the `code` folder double-click `stop_shadow.bat`, wait until the "PolySweeper
autopilot" window closes (up to about 2 minutes), then double-click `autopilot.bat`. After that,
updates to the autopilot itself are applied automatically. The score rows written so far are
kept on the PC and will be sent with the next sync.
