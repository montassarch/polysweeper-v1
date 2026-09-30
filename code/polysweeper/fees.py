"""Polymarket taker fee (formula from secondary sources; verify before real money)."""


def fee_per_share(price: float, rate: float) -> float:
    return rate * price * (1.0 - price)


def taker_fee(shares: float, price: float, rate: float) -> float:
    return shares * fee_per_share(price, rate)


def net_edge(price: float, rate: float) -> float:
    """Profit per $1 spent if the share pays $1, after the taker fee."""
    profit = 1.0 - price - fee_per_share(price, rate)
    return profit / price
