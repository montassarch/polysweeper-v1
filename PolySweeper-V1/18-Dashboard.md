---
title: Dashboard
tags: [polysweeper, dashboard]
created: 2026-10-01
---

# Dashboard

Back to [[V1-Home]] · Shadow mode: [[17-Run-Shadow-On-Your-PC]] · Results so far: [[16-Football-Results-and-Shadow-Mode]]

A single web page that shows how shadow mode is doing, next to the historical
backtest. It is generated on **your own PC** from your own result files, needs
**no internet and no hosting**, and nothing leaves your computer.

## How to open it (Windows)

1. In Obsidian, **Pull** to get the latest files.
2. Open `polysweeper-v1\code` and **double-click `dashboard.bat`**.
3. Your browser opens `dashboard.html`. Double-click `dashboard.bat` again any
   time to refresh it with the newest shadow results.

If the window shows an error, send me a screenshot of it.

## Live mode (near-live, every 15 seconds)

Double-click **`dashboard_live.bat`** instead. It opens the page, then rebuilds
it every **15 seconds** and the page reloads itself. Leave its black window open
next to the shadow-mode window; close it to stop.

- 15 seconds is the practical floor: shadow mode itself reads new data every 15
  seconds, so a faster dashboard would have nothing newer to show.
- It is still a **local page on your PC**, not a website. You can't open it from
  your phone.
- Matches settle every few minutes, so most refreshes will look unchanged.

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

## Live feed (added 2026-10-03)

Just under the summary tiles. Newest first, it shows for every pretend buy:

- **Why:** match ended or still in play, the score, the score-check verdict
  (and the result source for the confirmed rule).
- **Sellers:** the 5 cheapest sell orders on the book at that moment.
- **Took:** exactly which sell orders the 5 shares came from, for example
  "3 @ 0.970 + 2 @ 0.975 → avg 0.9720, fee $0.01, cost $4.87".
- **Outcome:** what it wins if right and loses if wrong.

It also lists every skip (junk book, too few shares, blocked by the score
check) and every payout (won/lost and the amount). Open it with
`dashboard_live.bat`; it refreshes every 15 seconds.

The shadow window prints the same details for each buy.
