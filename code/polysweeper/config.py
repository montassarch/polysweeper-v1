"""Risk and strategy settings, loaded from a JSON file (no code needed to tune)."""
from __future__ import annotations

import json
from dataclasses import dataclass, fields
from pathlib import Path


@dataclass
class Limits:
    # money
    bankroll: float = 50.0
    max_stake_per_trade: float = 2.0
    max_open_total: float = 15.0
    max_open_per_sport: float = 6.0
    max_trades_per_market: int = 2
    daily_loss_limit: float = 3.0
    pause_on_loss: bool = True
    # price window and size
    price_min: float = 0.96
    price_max: float = 0.995
    depth_fraction: float = 0.25      # never take more than this share of visible size
    min_shares: float = 1.0           # VERIFY the real Polymarket minimum order size
    min_net_edge: float = 0.005       # skip if profit after fee is below 0.5%
    fee_rate: float = 0.05            # sports taker rate per secondary source; VERIFY
    # verification
    min_sources: int = 2
    confirm_minutes: int = 10
    max_data_age_minutes: int = 15
    min_mapping_confidence: float = 0.95
    # scope
    enabled_sports: tuple = ("football", "esports")
    allowed_market_types: tuple = ("moneyline",)

    @classmethod
    def from_json(cls, path) -> "Limits":
        raw = json.loads(Path(path).read_text())
        known = {f.name for f in fields(cls)}
        unknown = set(raw) - known
        if unknown:
            raise ValueError(f"unknown setting(s) in {path}: {sorted(unknown)}")
        for key in ("enabled_sports", "allowed_market_types"):
            if key in raw:
                raw[key] = tuple(raw[key])
        return cls(**raw)
