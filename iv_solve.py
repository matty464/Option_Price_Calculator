"""Solve for implied volatility given a market option price."""

from __future__ import annotations

from black_scholes import OptionType, bs_price


def implied_volatility(
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    option_type: OptionType,
    *,
    max_iter: int = 80,
    tol: float = 1e-7,
    sigma_high: float = 5.0,
) -> float | None:
    """
    Bisection on sigma; BS price is monotone in vol for European calls/puts on non-dividend stock.
    Returns None if no bracket found or invalid inputs.
    """
    if market_price <= 0 or S <= 0 or K <= 0 or T <= 0:
        return None

    intrinsic = max(0.0, S - K) if option_type == "call" else max(0.0, K - S)
    if market_price < intrinsic - 1e-6:
        return None

    low, high = 1e-6, sigma_high
    p_low = bs_price(S, K, T, r, low, option_type)
    p_high = bs_price(S, K, T, r, high, option_type)

    if market_price > p_high:
        return None
    if market_price < p_low:
        return None

    for _ in range(max_iter):
        mid = 0.5 * (low + high)
        p_mid = bs_price(S, K, T, r, mid, option_type)
        if abs(p_mid - market_price) < tol:
            return mid
        if p_mid < market_price:
            low = mid
        else:
            high = mid

    return 0.5 * (low + high)
