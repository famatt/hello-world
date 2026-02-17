"""0 DTE Options pricing model using Black-Scholes approximation.

Models the behavior of SPY options expiring same-day, including
rapid theta decay, gamma exposure, and approximate P&L calculation
for backtesting purposes.
"""

import datetime as dt
import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np
from scipy.stats import norm


class OptionType(Enum):
    CALL = "CALL"
    PUT = "PUT"


@dataclass
class OptionContract:
    """Represents a 0 DTE option contract."""
    option_type: OptionType
    strike: float
    expiry: dt.datetime        # Market close time on expiry day
    entry_time: dt.datetime
    entry_underlying: float
    entry_premium: float
    iv: float                  # Implied volatility at entry
    contracts: int = 1

    @property
    def is_itm(self) -> bool:
        if self.option_type == OptionType.CALL:
            return self.entry_underlying > self.strike
        return self.entry_underlying < self.strike


def black_scholes_price(
    S: float,         # Underlying price
    K: float,         # Strike price
    T: float,         # Time to expiry in years
    r: float,         # Risk-free rate
    sigma: float,     # Implied volatility
    option_type: OptionType = OptionType.CALL,
) -> float:
    """Calculate Black-Scholes option price.

    For 0 DTE, T is typically between 0.0001 and 0.025 (few minutes to 6.5 hours).
    """
    if T <= 0:
        # At expiration - intrinsic value only
        if option_type == OptionType.CALL:
            return max(S - K, 0)
        return max(K - S, 0)

    sqrt_T = math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T

    if option_type == OptionType.CALL:
        price = S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    else:
        price = K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

    return max(price, 0.01)  # Minimum $0.01


def calculate_greeks(
    S: float, K: float, T: float, r: float, sigma: float,
    option_type: OptionType = OptionType.CALL,
) -> dict[str, float]:
    """Calculate option Greeks."""
    if T <= 0:
        intrinsic = max(S - K, 0) if option_type == OptionType.CALL else max(K - S, 0)
        itm = intrinsic > 0
        return {
            "delta": (1.0 if itm else 0.0) * (1 if option_type == OptionType.CALL else -1),
            "gamma": 0.0, "theta": 0.0, "vega": 0.0,
        }

    sqrt_T = math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T

    n_d1 = norm.pdf(d1)
    N_d1 = norm.cdf(d1)

    gamma = n_d1 / (S * sigma * sqrt_T)
    vega = S * n_d1 * sqrt_T / 100  # Per 1% IV change

    if option_type == OptionType.CALL:
        delta = N_d1
        theta = (-(S * n_d1 * sigma) / (2 * sqrt_T) - r * K * math.exp(-r * T) * norm.cdf(d2)) / 365
    else:
        delta = N_d1 - 1
        theta = (-(S * n_d1 * sigma) / (2 * sqrt_T) + r * K * math.exp(-r * T) * norm.cdf(-d2)) / 365

    return {"delta": delta, "gamma": gamma, "theta": theta, "vega": vega}


def time_to_expiry_years(current_time: dt.datetime, market_close: dt.datetime) -> float:
    """Calculate time to expiry in years for 0 DTE.

    Market close is 4:00 PM ET. Trading year = 252 days, 6.5 hours/day.
    """
    seconds_remaining = max((market_close - current_time).total_seconds(), 0)
    trading_seconds_per_year = 252 * 6.5 * 3600
    return seconds_remaining / trading_seconds_per_year


def select_strike(
    underlying_price: float,
    option_type: OptionType,
    moneyness: str = "ATM",
) -> float:
    """Select strike price based on moneyness.

    SPY options have $1 strikes.
    """
    rounded = round(underlying_price)

    if moneyness == "ATM":
        return rounded
    elif moneyness == "OTM1":
        return rounded + 1 if option_type == OptionType.CALL else rounded - 1
    elif moneyness == "OTM2":
        return rounded + 2 if option_type == OptionType.CALL else rounded - 2
    elif moneyness == "ITM1":
        return rounded - 1 if option_type == OptionType.CALL else rounded + 1
    return rounded


def estimate_0dte_premium(
    underlying_price: float,
    strike: float,
    minutes_to_close: float,
    iv: float,
    r: float = 0.05,
    option_type: OptionType = OptionType.CALL,
) -> float:
    """Estimate 0 DTE option premium given minutes to market close."""
    hours_remaining = minutes_to_close / 60
    T = hours_remaining / (252 * 6.5)  # Convert to trading years
    return black_scholes_price(underlying_price, strike, T, r, iv, option_type)


def estimate_iv_from_time(minutes_to_close: float, base_iv: float = 0.15) -> float:
    """Estimate implied volatility adjustment for 0 DTE.

    IV tends to be elevated early in the day for 0 DTE and drops
    as time passes (absent any vol events). This provides a simple
    time-based IV curve.
    """
    # 0 DTE IV tends to be 1.5-3x the term IV early, normalizing toward close
    hours = minutes_to_close / 60
    if hours > 5:
        multiplier = 2.5
    elif hours > 3:
        multiplier = 2.0
    elif hours > 1:
        multiplier = 1.5
    else:
        multiplier = 1.2
    return base_iv * multiplier


@dataclass
class OptionTrade:
    """Tracks a complete 0 DTE option trade for backtesting."""
    entry_time: dt.datetime
    exit_time: Optional[dt.datetime]
    option_type: OptionType
    strike: float
    entry_underlying: float
    exit_underlying: Optional[float]
    entry_premium: float
    exit_premium: Optional[float]
    contracts: int
    pattern: str
    direction: str
    iv: float

    @property
    def pnl_per_contract(self) -> float:
        if self.exit_premium is None:
            return 0.0
        return (self.exit_premium - self.entry_premium) * 100  # Options are per 100 shares

    @property
    def total_pnl(self) -> float:
        return self.pnl_per_contract * self.contracts

    @property
    def pnl_pct(self) -> float:
        if self.entry_premium <= 0:
            return 0.0
        return ((self.exit_premium or 0) - self.entry_premium) / self.entry_premium * 100

    @property
    def duration_minutes(self) -> float:
        if self.exit_time is None:
            return 0.0
        return (self.exit_time - self.entry_time).total_seconds() / 60

    def __str__(self) -> str:
        status = "OPEN" if self.exit_time is None else "CLOSED"
        pnl = f"${self.total_pnl:+.2f}" if self.exit_time else "---"
        return (
            f"[{self.entry_time:%Y-%m-%d %H:%M}] {self.option_type.value} "
            f"${self.strike:.0f} | {self.pattern} | "
            f"Entry: ${self.entry_premium:.2f} | {status} {pnl}"
        )
