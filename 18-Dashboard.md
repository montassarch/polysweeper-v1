---
title: Dashboard
tags: [polysweeper, dashboard]
created: 2026-10-01
---

# Dashboard

Back to [[README]] · Shadow mode: [[17-Run-Shadow-On-Your-PC]] · Results so far: [[16-Football-Results-and-Shadow-Mode]]

A single web page that shows how shadow mode is doing, next to the historical
backtest. It is generated on **your own PC** from your own result files, needs
**no internet and no hosting**, and nothing leaves your computer.

## How to open it (Windows)

1. In Obsidian, **Pull** to get the latest files.
2. Open `polysweeper-v1\code` and **double-click `dashboard.bat`**.
3. Your browser opens `dashboard.html`. Double-click `dashboard.bat` again any
   time to refresh it with the newest shadow results.

If the window shows an error, send me a screenshot of it.

## What it shows

**Shadow mode (live, real prices, pretend orders)**
- Counts: pretend buys, settled, wins and losses, fake profit, and how many
  times the order book was too thin to buy 5 shares.
- Fake profit over time (running total) and the real fill prices.
- Whether buying after Polymarket marked the match ended did better than buying
  during play.
- How many matches were watched and how long they last.
- A table of the latest pretend trades with win, loss or 50/50.

**Historical backtest (esports and football)**
- Profit per share by price band, and loss rate by buying time.
- Numbers come from `code/data/backtest_summary.json`, refreshed with
  `python -m polysweeper.backtest_summary` after downloading data.

**Also:** the risk rules from `config.json`, and a plain list of caveats.
There is a Light/dark button, a **Table view** under each chart, and hover
tooltips.

## Honest limits

- It is only as good as the data: shadow mode needs weeks and 100+ settled
  pretend trades before any number means much.
- Backtest numbers use mid prices, so they are optimistic.
- The dashboard was tested with **invented** data; the numbers in any
  screenshot of that test are not real.

## Files

- `code/polysweeper/dashboard.py` builds the page; `code/dashboard.bat` runs it.
- `code/polysweeper/backtest_summary.py` builds the backtest summary file.
