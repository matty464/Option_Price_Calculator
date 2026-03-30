"""Live quotes: VIX, equity spot, and a near-ATM option snapshot via yfinance."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

import pandas as pd
import yfinance as yf

OptionKind = Literal["call", "put"]


@dataclass
class OptionSnapshot:
    ticker: str
    underlying_spot: float
    expiry: str  # YYYY-MM-DD
    strike: float
    option_type: OptionKind
    mid_price: float
    bid: float | None
    ask: float | None
    last_price: float | None
    iv_yahoo: float | None  # decimal, if chain provides it
    days_to_expiry: float


def _mid_from_row(bid: float | None, ask: float | None, last: float | None) -> float | None:
    if bid is not None and ask is not None and bid > 0 and ask > 0 and ask >= bid:
        return 0.5 * (bid + ask)
    if last is not None and last > 0:
        return float(last)
    if bid is not None and bid > 0:
        return float(bid)
    if ask is not None and ask > 0:
        return float(ask)
    return None


def get_vix() -> float | None:
    t = yf.Ticker("^VIX")
    fast = t.fast_info.get("last_price") or t.fast_info.get("regular_market_price")
    if fast is not None:
        return float(fast)
    hist = t.history(period="1d", auto_adjust=True)
    if hist.empty:
        return None
    return float(hist["Close"].iloc[-1])


def get_spot(equity_ticker: str) -> float | None:
    sym = equity_ticker.strip().upper()
    if not sym:
        return None
    t = yf.Ticker(sym)
    fast = t.fast_info.get("last_price") or t.fast_info.get("regular_market_price")
    if fast is not None:
        return float(fast)
    hist = t.history(period="1d", auto_adjust=True)
    if hist.empty:
        return None
    return float(hist["Close"].iloc[-1])


def _parse_expiry_years(expiry_str: str) -> float:
    """Calendar DTE / 365 from UTC midnight expiry to now."""
    exp = datetime.strptime(expiry_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    seconds = max((exp - now).total_seconds(), 0.0)
    return seconds / (24.0 * 3600.0)


def list_option_expiries(equity_ticker: str) -> list[str]:
    """Listed expiry strings (YYYY-MM-DD) for options on this symbol, or []."""
    sym = equity_ticker.strip().upper()
    if not sym:
        return []
    t = yf.Ticker(sym)
    return list(t.options or [])


def fetch_option_at_strike(
    equity_ticker: str,
    expiry: str,
    strike: float,
    option_type: OptionKind,
) -> OptionSnapshot | None:
    """
    Pull bid/ask/mid for the given symbol, expiry, strike, and call/put.
    Expiry must match a Yahoo-listed date (e.g. from list_option_expiries).
    Chooses nearest listed strike if no exact match within 0.02.
    """
    sym = equity_ticker.strip().upper()
    exp = expiry.strip()
    if not sym or not exp:
        return None

    spot = get_spot(sym)
    if spot is None:
        return None

    t = yf.Ticker(sym)
    expiries = list(t.options or [])
    if exp not in expiries:
        return None

    dte = _parse_expiry_years(exp)
    chain = t.option_chain(exp)
    opts = chain.calls if option_type == "call" else chain.puts
    if opts is None or opts.empty:
        return None

    k = float(strike)
    sel = opts[(opts["strike"].astype(float) - k).abs() <= 0.02]
    if not sel.empty:
        row = sel.iloc[0]
    else:
        strikes = opts["strike"].astype(float)
        idx = int((strikes - k).abs().idxmin())
        row = opts.loc[idx]

    bid = float(row["bid"]) if not pd.isna(row["bid"]) else None
    ask = float(row["ask"]) if not pd.isna(row["ask"]) else None
    last = float(row["lastPrice"]) if not pd.isna(row["lastPrice"]) else None
    mid = _mid_from_row(bid, ask, last)

    iv_y = row["impliedVolatility"] if "impliedVolatility" in row.index else None
    iv_dec = float(iv_y) if iv_y is not None and not pd.isna(iv_y) else None

    if mid is None or mid <= 0:
        return None

    return OptionSnapshot(
        ticker=sym,
        underlying_spot=spot,
        expiry=exp,
        strike=float(row["strike"]),
        option_type=option_type,
        mid_price=mid,
        bid=bid,
        ask=ask,
        last_price=last,
        iv_yahoo=iv_dec,
        days_to_expiry=dte,
    )


def pick_atm_option(
    equity_ticker: str,
    *,
    min_dte_days: float = 5.0,
    option_type: OptionKind = "call",
) -> OptionSnapshot | None:
    """
    Choose the listed expiry with DTE >= min_dte_days (earliest such expiry),
    then the strike closest to spot from the chain.
    """
    sym = equity_ticker.strip().upper()
    if not sym:
        return None

    spot = get_spot(sym)
    if spot is None:
        return None

    t = yf.Ticker(sym)
    expiries = list(t.options or [])
    if not expiries:
        return None

    chosen = None
    for exp in expiries:
        dte = _parse_expiry_years(exp)
        if dte >= min_dte_days:
            chosen = exp
            break
    if chosen is None:
        chosen = expiries[-1]

    dte = _parse_expiry_years(chosen)
    chain = t.option_chain(chosen)
    opts = chain.calls if option_type == "call" else chain.puts
    if opts is None or opts.empty:
        return None

    strikes = opts["strike"].astype(float)
    idx = int((strikes - spot).abs().idxmin())
    row = opts.loc[idx]

    bid = float(row["bid"]) if not pd.isna(row["bid"]) else None
    ask = float(row["ask"]) if not pd.isna(row["ask"]) else None
    last = float(row["lastPrice"]) if not pd.isna(row["lastPrice"]) else None
    mid = _mid_from_row(bid, ask, last)

    iv_y = row["impliedVolatility"] if "impliedVolatility" in row.index else None
    iv_dec = float(iv_y) if iv_y is not None and not pd.isna(iv_y) else None

    if mid is None or mid <= 0:
        return None

    return OptionSnapshot(
        ticker=sym,
        underlying_spot=spot,
        expiry=chosen,
        strike=float(row["strike"]),
        option_type=option_type,
        mid_price=mid,
        bid=bid,
        ask=ask,
        last_price=last,
        iv_yahoo=iv_dec,
        days_to_expiry=dte,
    )
