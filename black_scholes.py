"""Black–Scholes pricing and Greeks (per share; scale by 100 for standard equity options)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Tuple

OptionType = Literal["call", "put"]


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def bs_d1_d2(S: float, K: float, T: float, r: float, sigma: float) -> Tuple[float, float]:
    sigma = max(sigma, 1e-12)
    T = max(T, 1e-12)
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return d1, d2


def bs_price(S: float, K: float, T: float, r: float, sigma: float, option_type: OptionType) -> float:
    d1, d2 = bs_d1_d2(S, K, T, r, sigma)
    if option_type == "call":
        return S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
    return K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)


@dataclass
class Greeks:
    price: float
    delta: float
    gamma: float
    vega: float  # per 1.00 change in IV (as decimal), /100 for "per vol point" in some UIs
    theta: float  # per calendar day
    rho: float  # per 1% rate change (matches common convention /100)


def bs_price_greeks(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: OptionType,
) -> Greeks:
    d1, d2 = bs_d1_d2(S, K, T, r, sigma)
    pdf_d1 = norm_pdf(d1)

    if option_type == "call":
        price = S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
        delta = norm_cdf(d1)
        theta = (-(S * pdf_d1 * sigma) / (2 * math.sqrt(T)) - r * K * math.exp(-r * T) * norm_cdf(d2)) / 365.0
        rho = (K * T * math.exp(-r * T) * norm_cdf(d2)) / 100.0
    else:
        price = K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)
        delta = norm_cdf(d1) - 1.0
        theta = (-(S * pdf_d1 * sigma) / (2 * math.sqrt(T)) + r * K * math.exp(-r * T) * norm_cdf(-d2)) / 365.0
        rho = (-K * T * math.exp(-r * T) * norm_cdf(-d2)) / 100.0

    gamma = pdf_d1 / (S * sigma * math.sqrt(T))
    vega = S * pdf_d1 * math.sqrt(T) / 100.0

    return Greeks(price=price, delta=delta, gamma=gamma, vega=vega, theta=theta, rho=rho)
