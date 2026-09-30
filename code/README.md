# PolySweeper code (v1, offline core)

Standard library only (Python 3.11+). No installs needed.

    cd code
    python3 -m unittest discover -s tests      # run the checks
    python3 make_sample_data.py                # FAKE data for testing the machinery
    python3 -m polysweeper.backtest data/sample.jsonl config.json

Settings live in `config.json` (risk limits, price window, sports enabled).
Plain-language explanation: see `../13-Code-Overview.md`.
