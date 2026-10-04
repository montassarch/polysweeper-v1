---
title: Desktop App (PolySweeper.exe)
tags: [polysweeper, v1, app, dashboard]
created: 2026-10-04
---

# Desktop app: PolySweeper.exe

Back to [[V1-Home]] · Autopilot: [[28-Autopilot]] · Live feed: [[29-Live-Feed-and-Score-Log]]

A real Windows app (not a web page) that shows shadow mode live. It is read-only: it never places an
order and never changes a file.

## How to open it

- After the autopilot has installed it, there is a **PolySweeper** icon on the desktop. Double-click it.
- It also lives at `app\bin\PolySweeper.exe` in the project folder.
- The first time, Windows may say "Windows protected your PC" (the app is not signed by a company).
  Click **More info**, then **Run anyway**. This happens only once.

## What it shows (refreshes every second)

| Part | What you see |
|---|---|
| Top bar | Bot running or stopped · live prices connected (books, % matching) · matches near the end (2-second checks) · last autopilot action · problems today (live price reconnects are counted separately; they are normal) |
| Numbers | Net result of all pretend trades · paid out today · wins / losses · win rate · open pretend trades · buys today · skipped today |
| **Live** tab | Every watched match: score, state, both sides' best ask / best bid (live), flags NEAR END / WATCHING RESULT / IN BUY BAND. Open pretend trades with the price now. Activity feed: every buy (and the sell orders it took), payout, skip and problem, newest first |
| **Trades** tab | Every pretend buy; click one to see why it was bought, the sell orders on the book, the orders taken (the "fills"), average price, fee, cost and result |
| **Performance** tab | Running total of all payouts (losses circled in red), results by rule and by league |
| **After the match** tab | Is anything left to buy after a result? (the end-window study, including the second-by-second live numbers) |
| **System** tab | Bot details, live price connection, problems, the autopilot log |

## How it works

1. Shadow mode writes `code/data/shadow/live.json` every ~2 seconds: every watched match with its score
   and live prices, the live feed status and the counters (not sent to GitHub).
2. The app reads that file and the trade, event and error files every second.
3. The exe is built on a Windows machine at GitHub (`.github/workflows/build-app.yml`), tested there
   (all tests on Windows, a 90-second shadow run, the app's own self-check and a screenshot), and
   published to the `app-build` branch.
4. The autopilot installs it from there into `app\bin\` (checks every hour) and makes the desktop
   shortcut once. If the app is open during an update, the update waits until it is closed.
5. The exe loads the app's screens from `app\polysweeper_app.py` in the project folder, so most app
   improvements arrive with the normal update; just close and reopen the app.

## How it was checked (2026-10-04)

- Run on a virtual screen in the cloud against real data (the PC's synced data plus a fresh shadow run
  with the live feed): 29 watched matches with live prices (98% matching), 136 pretend trades,
  13 open, 123 payouts on the chart, every tab screenshotted and looked at.
- Packaged with PyInstaller exactly like the Windows build (as a Linux program) and run: the packaged
  app found the project folder, loaded the screens and passed its self-check.
- Automatic tests: the data side of the app (new lines arriving, Windows line endings, files being
  replaced), shadow mode's live file, and the autopilot installing and updating the app.
- The Windows build and its self-test: see the latest run in GitHub Actions and `BUILD.txt` /
  `screen.png` on the `app-build` branch.
