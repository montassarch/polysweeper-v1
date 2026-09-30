---
title: Run Shadow Mode on Your PC (Windows)
tags: [polysweeper, shadow, setup, windows]
created: 2026-09-30
---

# Run shadow mode on your own computer (Windows)

Back to [[README]] · What it is: [[16-Football-Results-and-Shadow-Mode]]

Shadow mode **places no orders**, needs **no wallet, no keys, no login**. It only
reads public Polymarket data and writes log files. It must run for days or
weeks to collect enough real cases.

## One-time setup

1. **Install Python** from https://www.python.org/downloads/ (version 3.11 or
   newer). On the first installer screen **tick "Add python.exe to PATH"**,
   then click Install.
2. **Get the latest files:** in Obsidian click **Pull** in the Git panel
   (or run Git: Pull from `Ctrl+P`). You should now see a `code` folder inside
   the vault folder.
3. **Open the folder in File Explorer:** `polysweeper-v1\code`. You should see
   `run_shadow.bat`, `stop_shadow.bat`, `report_shadow.bat`.
4. **Keep the PC awake:**
   - Windows Settings -> System -> Power & battery -> Screen and sleep ->
     "When plugged in, put my device to sleep after" -> **Never**.
   - Laptop: keep it plugged in, and set "closing the lid" to **Do nothing**
     (Control Panel -> Power Options -> Choose what closing the lid does).

## Start it

1. Double-click **`run_shadow.bat`**.
2. If Windows shows a blue "protected your PC" box, click **More info ->
   Run anyway**. (The file is 10 lines of text; right-click -> Edit shows it.)
3. A black window opens and says `shadow mode started`. **Leave it open.**
   It may print nothing for long stretches. It prints a line such as
   `SHADOW BUY ...` only when a match reaches the buy zone.

## Stop it

Double-click **`stop_shadow.bat`** (it stops within about 15 seconds), or just
close the black window. You can start it again later; it **resumes**.

## See results

Double-click **`report_shadow.bat`**. It prints counts of pretend-buys, wins,
losses, and thin-book skips, split by whether Polymarket had marked the match
as ended.

## Send me the results

The small result files are `code\data\shadow\trades.jsonl` and
`events.jsonl`. They are **not** excluded from git, so Obsidian Git will upload
them with its normal sync (use **Git: Commit-and-sync**, or set the auto backup
interval to 10 minutes in Settings -> Git). Then tell me, and I read them from
GitHub. (The large `snapshots.jsonl` stays on your PC.)

## If something goes wrong

- **"python is not recognized":** reinstall Python and tick "Add to PATH".
- **Errors about connection or 403:** tell me the exact text.
- **Window closed by itself after a reboot/sleep:** just run it again.
- Don't put any keys, passwords or wallet info into this folder.

## How long?

Aim for **1-2 weeks**. More is better. Check in every few days.
