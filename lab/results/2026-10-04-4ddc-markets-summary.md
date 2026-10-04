# Wallet 0x4dDC... buys at 0.95+ by market type (lab/lockedline_wallet.py, lab/mlb_buy_situation.py; raw rows in lab/data/raw/)
Last 6,000 trades (2026-09-20..10-04). Wins/losses from Gamma settlement.
- Moneylines: ATP 132W/0L, CFB 124/1, MLB 100/0, WTA 88/0, NFL 67/0.
- Totals "Over": MLB 54/0, NFL 51/0, CFB 18/0, football 15/0 (Over lines can lock mid-game).
- Totals "Under": NFL 50/1 (-$62.6), MLB 40/0. Spreads: MLB away 33/1 (-$59.3), others 0 losses.
- NRFI ("run in 1st inning?"): No 17/0 (all bought right after a 0-0 first inning = locked), Yes 12/0.
- MLB moneyline buy situations (StatsAPI play-by-play; feed end-times lag a few s): 35 after the final out,
  ~45 in the 9th (leads 1-5), ~20 in innings 7-8 with leads of 4-8 runs.
- Its 0.99 Over buys were mostly NOT yet locked (e.g. Over 8.5 at 8 runs, 4th inning): model bets, not locks.
