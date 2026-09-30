"""Replay past candidates through the bot's rules with fake money.

Usage:  python -m polysweeper.backtest data/sample.jsonl [config.json]
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .config import Limits
from .decide import decide
from .killswitch import KillSwitch
from .models import Candidate, SourceResult
from .risk import RiskState


def _dt(value):
    return None if value is None else datetime.fromisoformat(value)


def parse_record(raw: dict):
    sources = tuple(
        SourceResult(s["source"], s["status"], s["result_type"], s.get("winner"),
                     _dt(s.get("finished_at")), _dt(s["fetched_at"]))
        for s in raw["sources"]
    )
    cand = Candidate(
        raw["market_id"], raw["sport"], raw["market_type"], raw["outcome_team"],
        raw["ask_price"], raw["available_size"], _dt(raw["time"]), sources,
        raw.get("mapping_confidence", 1.0), raw.get("synthetic", False),
    )
    return cand, raw["settlement"], _dt(raw["settled_at"])


def load_records(path):
    out = []
    for line in Path(path).read_text().splitlines():
        if line.strip():
            out.append(parse_record(json.loads(line)))
    out.sort(key=lambda r: r[0].time)
    return out


@dataclass
class Report:
    start_bankroll: float
    final_equity: float = 0.0
    trades: int = 0
    wins: int = 0
    losses: int = 0
    splits: int = 0
    realized_pnl: float = 0.0
    max_drawdown: float = 0.0
    worst_loss: float = 0.0
    skipped: Counter = field(default_factory=Counter)
    pnl_by_sport: dict = field(default_factory=lambda: defaultdict(float))
    synthetic: bool = False

    def text(self) -> str:
        lines = []
        if self.synthetic:
            lines += ["*** SYNTHETIC DATA: tests the machinery only. It says NOTHING about real profit. ***", ""]
        lines += [
            f"Start bankroll : ${self.start_bankroll:.2f}",
            f"Final equity   : ${self.final_equity:.2f}  (P&L ${self.realized_pnl:+.2f})",
            f"Trades         : {self.trades}  (wins {self.wins}, losses {self.losses}, 50/50 {self.splits})",
            f"Worst loss     : ${self.worst_loss:.2f}",
            f"Max drawdown   : ${self.max_drawdown:.2f}",
            "P&L by sport   : " + ", ".join(f"{k} ${v:+.2f}" for k, v in sorted(self.pnl_by_sport.items())),
            "Skipped (top reasons):",
        ]
        for reason, n in self.skipped.most_common(8):
            lines.append(f"  {n:4d}  {reason}")
        lines += ["", "Reminder: chart prices overstate what you could really buy. Confirm with shadow mode."]
        return "\n".join(lines)


def run(records, limits: Limits) -> Report:
    state = RiskState(limits)
    kill = KillSwitch()
    report = Report(limits.bankroll)
    pending = []  # (settled_at, position, outcome)

    def settle_due(until=None):
        due = sorted((p for p in pending if until is None or p[0] <= until), key=lambda p: p[0])
        for settled_at, pos, outcome in due:
            pending.remove((settled_at, pos, outcome))
            state.roll_day(settled_at.date(), auto_resume=True)
            pnl = state.settle(pos, outcome)
            report.realized_pnl += pnl
            report.pnl_by_sport[pos.sport] += pnl
            if outcome == "win":
                report.wins += 1
            elif outcome == "loss":
                report.losses += 1
            else:
                report.splits += 1
            report.worst_loss = min(report.worst_loss, pnl)

    for cand, settlement, settled_at in records:
        report.synthetic = report.synthetic or cand.synthetic
        settle_due(cand.time)
        state.roll_day(cand.time.date(), auto_resume=True)
        d = decide(cand, limits, state, kill)
        if d.action == "BUY":
            pos = state.open_position(cand.market_id, cand.sport, d.shares, d.price, d.fee, cand.time)
            pending.append((settled_at, pos, settlement))
            report.trades += 1
        else:
            report.skipped[d.reasons[0]] += 1
    settle_due()
    report.final_equity = state.equity()
    report.max_drawdown = state.max_drawdown
    return report


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    limits = Limits.from_json(argv[2]) if len(argv) > 2 else Limits()
    print(run(load_records(argv[1]), limits).text())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
