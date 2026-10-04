# PolySweeper code (v1, offline core)

Standard library only (Python 3.11+). No installs needed.

    cd code
    python3 -m unittest discover -s tests      # run the checks
    python3 make_sample_data.py                # FAKE data for testing the machinery
    python3 -m polysweeper.backtest data/sample.jsonl config.json

Settings live in `config.json` (risk limits, price window, sports enabled).
Plain-language explanation: see `../PolySweeper-V1/13-Code-Overview.md`.

Shadow mode (pretend trades on live matches, no orders) runs 24/7 on the owner's PC under the
autopilot: `python -m polysweeper.shadow --forever` (add `--no-live` to turn off the live feed).
Its data is in `data/shadow/` (trades, events, errors, and `daily/` with score changes and live
end-window detail). Notes: `../PolySweeper-V1/28-Autopilot.md` and `29-Live-Feed-and-Score-Log.md`.
