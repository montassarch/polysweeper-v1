# lab/ — PolySweeper Lab research scripts

Small, standard-library Python scripts written by the lab's tester agent to measure strategy ideas
on real Polymarket data (see `PolySweeper-V1/30-Research-Hub.md`).

- Kept **outside `code/` on purpose**: changes here do not restart shadow mode on the owner's PC.
- Scripts may import helpers from `code/polysweeper` (add `code` to `sys.path`).
- `lab/results/`: small dated summaries (committed). `lab/data/raw/`: raw downloads (git-ignored).
- Read-only research: nothing here places orders or touches a wallet.
