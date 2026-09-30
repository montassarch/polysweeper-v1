"""Plain data containers used across the bot."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple

# How a match ended. Only "normal" is safe to trade: everything else can
# resolve 50/50 on Polymarket (forfeit, walkover, disqualification, cancelled).
NORMAL = "normal"


@dataclass(frozen=True)
class SourceResult:
    """What ONE results provider says about a match."""

    source: str                 # provider name, e.g. "provider_a"
    status: str                 # "finished", "live", "scheduled", "cancelled", "abandoned"
    result_type: str            # "normal", "forfeit", "walkover", "disqualification", "draw", "unknown"
    winner: Optional[str]
    finished_at: Optional[datetime]
    fetched_at: datetime        # when we asked the provider (to detect stale data)


@dataclass(frozen=True)
class Candidate:
    """One chance to buy: a Polymarket outcome token plus what we know."""

    market_id: str
    sport: str                  # "football", "esports", ...
    market_type: str            # "moneyline", "spread", "total", ...
    outcome_team: str           # the team this token pays out on
    ask_price: float            # best price we could buy at
    available_size: float       # shares offered at or below ask_price
    time: datetime              # moment of the decision
    sources: Tuple[SourceResult, ...]
    mapping_confidence: float = 1.0   # how sure we are market <-> match is right
    synthetic: bool = False           # True for fake test data


@dataclass
class Decision:
    action: str                 # "BUY" or "SKIP"
    reasons: list
    shares: float = 0.0
    price: float = 0.0
    fee: float = 0.0
    cost: float = 0.0           # shares * price + fee
