"""The bot's brain: look at one candidate and answer BUY or SKIP, with reasons."""
from __future__ import annotations

from .config import Limits
from .fees import net_edge, taker_fee
from .killswitch import KillSwitch
from .models import Candidate, Decision
from .risk import RiskState, size_shares
from .verifier import verify


def _skip(*reasons) -> Decision:
    return Decision("SKIP", list(reasons))


def decide(c: Candidate, limits: Limits, state: RiskState, kill: KillSwitch) -> Decision:
    # 1. emergency and pause states
    if kill.is_active():
        return _skip(f"kill switch active: {kill.reason()}")
    if state.paused:
        return _skip(f"bot paused: {state.pause_reason}")
    if state.daily_pnl <= -limits.daily_loss_limit:
        return _skip("daily loss limit reached")

    # 2. scope
    if c.sport not in limits.enabled_sports:
        return _skip(f"sport '{c.sport}' not enabled")
    if c.market_type not in limits.allowed_market_types:
        return _skip(f"market type '{c.market_type}' not allowed")
    if c.mapping_confidence < limits.min_mapping_confidence:
        return _skip("market/match mapping not certain enough")

    # 3. is the result trustworthy?
    v = verify(c.sources, c.time, limits.min_sources, limits.confirm_minutes,
               limits.max_data_age_minutes)
    if not v.ok:
        return _skip(*v.reasons)
    if v.winner != c.outcome_team.strip().lower():
        return _skip("this token is not the verified winner")

    # 4. price and profit
    if not (limits.price_min <= c.ask_price <= limits.price_max):
        return _skip(f"price {c.ask_price:.3f} outside {limits.price_min}-{limits.price_max}")
    if net_edge(c.ask_price, limits.fee_rate) < limits.min_net_edge:
        return _skip("profit after fee too small")

    # 5. how much, under the money limits
    if state.trades_in_market(c.market_id) >= limits.max_trades_per_market:
        return _skip("max trades in this market reached")
    shares = size_shares(limits, state, c.sport, c.ask_price, c.available_size)
    if shares < limits.min_shares:
        return _skip("size below minimum (limits or thin order book)")

    fee = taker_fee(shares, c.ask_price, limits.fee_rate)
    return Decision("BUY", ["all checks passed"], shares, c.ask_price, fee,
                    shares * c.ask_price + fee)
