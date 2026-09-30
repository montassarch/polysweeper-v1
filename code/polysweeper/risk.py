"""Paper portfolio + risk state. Every money rule lives here or in decide.py."""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional

from .config import Limits
from .fees import fee_per_share


@dataclass
class Position:
    market_id: str
    sport: str
    shares: float
    price: float
    fee: float
    opened_at: datetime

    @property
    def cost(self) -> float:
        return self.shares * self.price + self.fee


class RiskState:
    def __init__(self, limits: Limits):
        self.limits = limits
        self.cash = limits.bankroll
        self.open: List[Position] = []
        self.day: Optional[date] = None
        self.daily_pnl = 0.0
        self.realized_pnl = 0.0
        self.paused = False
        self.pause_reason = ""
        self.peak_equity = limits.bankroll
        self.max_drawdown = 0.0

    # --- views -------------------------------------------------------
    def open_total(self) -> float:
        return sum(p.cost for p in self.open)

    def open_for_sport(self, sport: str) -> float:
        return sum(p.cost for p in self.open if p.sport == sport)

    def trades_in_market(self, market_id: str) -> int:
        return sum(1 for p in self.open if p.market_id == market_id)

    def equity(self) -> float:
        """Cash plus open positions at cost (conservative: no unrealised gains)."""
        return self.cash + self.open_total()

    # --- day handling ------------------------------------------------
    def roll_day(self, day: date, auto_resume: bool = False) -> None:
        if day != self.day:
            self.day = day
            self.daily_pnl = 0.0
            if auto_resume and self.paused:
                self.paused = False
                self.pause_reason = ""

    # --- actions -----------------------------------------------------
    def open_position(self, market_id, sport, shares, price, fee, when) -> Position:
        pos = Position(market_id, sport, shares, price, fee, when)
        self.cash -= pos.cost
        self.open.append(pos)
        return pos

    def settle(self, pos: Position, outcome: str) -> float:
        """outcome: 'win' pays $1/share, 'loss' pays 0, 'split' pays $0.50/share."""
        payout = {"win": 1.0, "loss": 0.0, "split": 0.5}[outcome] * pos.shares
        pnl = payout - pos.cost
        self.cash += payout
        self.open.remove(pos)
        self.daily_pnl += pnl
        self.realized_pnl += pnl
        if pnl < 0 and self.limits.pause_on_loss:
            self.paused = True
            self.pause_reason = f"loss of {pnl:.2f} on {pos.market_id}; review before resuming"
        equity = self.equity()
        self.peak_equity = max(self.peak_equity, equity)
        self.max_drawdown = max(self.max_drawdown, self.peak_equity - equity)
        return pnl


def size_shares(limits: Limits, state: RiskState, sport: str, price: float, available_size: float) -> float:
    """How many shares we may buy under all money limits (rounded DOWN)."""
    budget = min(
        limits.max_stake_per_trade,
        limits.max_open_total - state.open_total(),
        limits.max_open_per_sport - state.open_for_sport(sport),
        state.cash,
    )
    if budget <= 0:
        return 0.0
    cost_per_share = price + fee_per_share(price, limits.fee_rate)
    by_budget = budget / cost_per_share
    by_depth = available_size * limits.depth_fraction
    shares = min(by_budget, by_depth)
    return math.floor(shares * 100) / 100
