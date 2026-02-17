"""Backtesting engine for 0 DTE SPY options strategies.

Simulates trading 0 DTE options based on detected patterns,
modeling entry/exit with Black-Scholes pricing, stop losses,
profit targets, and theta decay.
"""

import datetime as dt
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from spy_agent.config import AgentConfig
from spy_agent.data_fetcher import DataFetcher
from spy_agent.options_model import (
    OptionTrade,
    OptionType,
    black_scholes_price,
    estimate_iv_from_time,
    select_strike,
    time_to_expiry_years,
)
from spy_agent.patterns import Direction, PatternDetector, Signal


@dataclass
class BacktestResult:
    """Results from a backtest run."""
    trades: list[OptionTrade]
    initial_capital: float
    final_capital: float
    config: AgentConfig

    @property
    def total_trades(self) -> int:
        return len(self.trades)

    @property
    def winners(self) -> list[OptionTrade]:
        return [t for t in self.trades if t.total_pnl > 0]

    @property
    def losers(self) -> list[OptionTrade]:
        return [t for t in self.trades if t.total_pnl <= 0]

    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return len(self.winners) / self.total_trades * 100

    @property
    def total_pnl(self) -> float:
        return sum(t.total_pnl for t in self.trades)

    @property
    def avg_pnl(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return self.total_pnl / self.total_trades

    @property
    def avg_winner(self) -> float:
        if not self.winners:
            return 0.0
        return sum(t.total_pnl for t in self.winners) / len(self.winners)

    @property
    def avg_loser(self) -> float:
        if not self.losers:
            return 0.0
        return sum(t.total_pnl for t in self.losers) / len(self.losers)

    @property
    def profit_factor(self) -> float:
        gross_profit = sum(t.total_pnl for t in self.winners)
        gross_loss = abs(sum(t.total_pnl for t in self.losers))
        if gross_loss == 0:
            return float("inf") if gross_profit > 0 else 0.0
        return gross_profit / gross_loss

    @property
    def max_drawdown(self) -> float:
        if not self.trades:
            return 0.0
        equity = [self.initial_capital]
        for t in self.trades:
            equity.append(equity[-1] + t.total_pnl)
        eq = np.array(equity)
        peak = np.maximum.accumulate(eq)
        dd = (eq - peak) / peak * 100
        return dd.min()

    @property
    def sharpe_ratio(self) -> float:
        if len(self.trades) < 2:
            return 0.0
        returns = [t.pnl_pct for t in self.trades]
        avg_ret = np.mean(returns)
        std_ret = np.std(returns)
        if std_ret == 0:
            return 0.0
        # Annualize: ~252 trading days
        return avg_ret / std_ret * np.sqrt(252)

    @property
    def avg_duration_minutes(self) -> float:
        if not self.trades:
            return 0.0
        return np.mean([t.duration_minutes for t in self.trades])

    def pattern_breakdown(self) -> dict[str, dict]:
        """Break down performance by pattern."""
        patterns = {}
        for t in self.trades:
            if t.pattern not in patterns:
                patterns[t.pattern] = {"trades": [], "pnl": 0.0, "wins": 0, "count": 0}
            patterns[t.pattern]["trades"].append(t)
            patterns[t.pattern]["pnl"] += t.total_pnl
            patterns[t.pattern]["count"] += 1
            if t.total_pnl > 0:
                patterns[t.pattern]["wins"] += 1

        for p in patterns.values():
            p["win_rate"] = p["wins"] / p["count"] * 100 if p["count"] > 0 else 0
            p["avg_pnl"] = p["pnl"] / p["count"] if p["count"] > 0 else 0

        return dict(sorted(patterns.items(), key=lambda x: x[1]["pnl"], reverse=True))

    def day_of_week_breakdown(self) -> dict[str, dict]:
        """Break down performance by day of week."""
        days = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday", 4: "Friday"}
        breakdown = {}
        for t in self.trades:
            dow = t.entry_time.weekday()
            day_name = days.get(dow, str(dow))
            if day_name not in breakdown:
                breakdown[day_name] = {"pnl": 0.0, "wins": 0, "count": 0}
            breakdown[day_name]["pnl"] += t.total_pnl
            breakdown[day_name]["count"] += 1
            if t.total_pnl > 0:
                breakdown[day_name]["wins"] += 1

        for d in breakdown.values():
            d["win_rate"] = d["wins"] / d["count"] * 100 if d["count"] > 0 else 0
        return breakdown

    def hour_breakdown(self) -> dict[int, dict]:
        """Break down performance by hour of day."""
        breakdown = {}
        for t in self.trades:
            hour = t.entry_time.hour
            if hour not in breakdown:
                breakdown[hour] = {"pnl": 0.0, "wins": 0, "count": 0}
            breakdown[hour]["pnl"] += t.total_pnl
            breakdown[hour]["count"] += 1
            if t.total_pnl > 0:
                breakdown[hour]["wins"] += 1

        for h in breakdown.values():
            h["win_rate"] = h["wins"] / h["count"] * 100 if h["count"] > 0 else 0
        return dict(sorted(breakdown.items()))


class Backtester:
    """Backtests 0 DTE options strategies on SPY historical data."""

    def __init__(self, config: AgentConfig = None):
        self.config = config or AgentConfig()
        self.fetcher = DataFetcher(self.config.ticker)
        self.detector = PatternDetector(self.config)

    def run(
        self,
        use_daily_simulation: bool = True,
        intraday_days: int = 60,
        progress_callback=None,
    ) -> BacktestResult:
        """Run backtest on historical data.

        Args:
            use_daily_simulation: If True, simulates intraday bars from 5yr daily
                data for extended backtesting. If False, uses actual intraday data
                (limited to ~60 days for 5m bars).
            intraday_days: Number of days of actual intraday data to use.
            progress_callback: Optional callable(current, total) for progress updates.
        """
        if use_daily_simulation:
            daily_df = self.fetcher.fetch_daily(years=self.config.history_years)
            intraday_df = self.fetcher.simulate_intraday_from_daily(daily_df)
        else:
            intraday_df = self.fetcher.fetch_max_intraday_history(self.config.intraday_interval)

        # Add previous day levels
        intraday_df = self.fetcher.get_previous_day_levels(intraday_df)

        # Calculate VWAP
        vwap = self.fetcher.get_vwap(intraday_df)

        # Detect all patterns
        if progress_callback:
            progress_callback(0, 3)

        signals = self.detector.scan(intraday_df, vwap)

        if progress_callback:
            progress_callback(1, 3)

        # Filter by confidence
        signals = [s for s in signals if s.confidence >= self.config.min_pattern_confidence]

        # Simulate trades
        trades = self._simulate_trades(signals, intraday_df)

        if progress_callback:
            progress_callback(2, 3)

        # Calculate final capital
        final_capital = self.config.initial_capital + sum(t.total_pnl for t in trades)

        if progress_callback:
            progress_callback(3, 3)

        return BacktestResult(
            trades=trades,
            initial_capital=self.config.initial_capital,
            final_capital=final_capital,
            config=self.config,
        )

    def _simulate_trades(
        self, signals: list[Signal], df: pd.DataFrame
    ) -> list[OptionTrade]:
        """Simulate option trades from detected signals."""
        trades = []
        capital = self.config.initial_capital
        active_trade_date = None  # Only one trade per day at a time

        for signal in signals:
            trade_date = signal.timestamp.date() if hasattr(signal.timestamp, 'date') else signal.timestamp

            # Skip if we already have a trade today
            if active_trade_date == trade_date:
                continue

            # Determine option type
            if signal.direction == Direction.LONG:
                opt_type = OptionType.CALL
            else:
                opt_type = OptionType.PUT

            # Select ATM strike
            strike = select_strike(signal.entry_price, opt_type, "ATM")

            # Calculate time to close
            if hasattr(signal.timestamp, 'hour'):
                market_close = dt.datetime.combine(
                    signal.timestamp.date() if hasattr(signal.timestamp, 'date') else signal.timestamp,
                    dt.time(16, 0),
                )
                minutes_to_close = max((market_close - signal.timestamp).total_seconds() / 60, 1)
            else:
                minutes_to_close = 180  # Default 3 hours

            # Estimate IV and premium
            iv = estimate_iv_from_time(minutes_to_close, self.config.default_iv)
            T = minutes_to_close / 60 / (252 * 6.5)
            entry_premium = black_scholes_price(
                signal.entry_price, strike, T, self.config.risk_free_rate, iv, opt_type
            )

            if entry_premium < 0.05:
                continue  # Skip too cheap options

            # Position sizing
            position_value = capital * self.config.position_size_pct / 100
            contracts = max(int(position_value / (entry_premium * 100)), 1)
            cost = contracts * entry_premium * 100

            if cost > capital:
                contracts = max(int(capital / (entry_premium * 100)), 1)
                if contracts == 0:
                    continue

            # Simulate exit using forward bars
            exit_result = self._find_exit(
                signal, df, opt_type, strike, iv, entry_premium, minutes_to_close
            )

            trade = OptionTrade(
                entry_time=signal.timestamp,
                exit_time=exit_result["exit_time"],
                option_type=opt_type,
                strike=strike,
                entry_underlying=signal.entry_price,
                exit_underlying=exit_result["exit_price"],
                entry_premium=entry_premium,
                exit_premium=exit_result["exit_premium"],
                contracts=contracts,
                pattern=signal.pattern,
                direction=signal.direction.value,
                iv=iv,
            )

            trades.append(trade)
            capital += trade.total_pnl
            # Apply slippage and commissions
            capital -= contracts * self.config.commission_per_contract * 2  # Round trip
            capital -= abs(trade.total_pnl) * self.config.slippage_pct / 100

            active_trade_date = trade_date

            if capital <= 0:
                break

        return trades

    def _find_exit(
        self,
        signal: Signal,
        df: pd.DataFrame,
        opt_type: OptionType,
        strike: float,
        iv: float,
        entry_premium: float,
        initial_minutes_to_close: float,
    ) -> dict:
        """Find exit point for a trade based on stop loss, target, or expiration."""
        stop_pct = self.config.max_loss_per_trade_pct / 100
        target_pct = self.config.profit_target_pct / 100

        stop_premium = entry_premium * (1 - stop_pct)
        target_premium = entry_premium * (1 + target_pct)

        # Get forward bars from signal
        mask = df.index > signal.timestamp
        forward = df[mask]

        # Only look at same day
        signal_date = signal.timestamp.date() if hasattr(signal.timestamp, 'date') else None
        if signal_date:
            forward = forward[forward.index.date == signal_date] if hasattr(forward.index, 'date') else forward

        market_close = dt.datetime.combine(
            signal_date or dt.date.today(), dt.time(16, 0)
        )

        for i in range(len(forward)):
            bar_time = forward.index[i]
            bar_price = forward["close"].iloc[i]

            minutes_left = max((market_close - bar_time).total_seconds() / 60, 0.1)
            T = minutes_left / 60 / (252 * 6.5)

            # Recalculate premium with new underlying price and time decay
            current_premium = black_scholes_price(bar_price, strike, T, self.config.risk_free_rate, iv, opt_type)

            # Check stop loss
            if current_premium <= stop_premium:
                return {
                    "exit_time": bar_time,
                    "exit_price": bar_price,
                    "exit_premium": stop_premium,
                    "exit_reason": "stop_loss",
                }

            # Check profit target
            if current_premium >= target_premium:
                return {
                    "exit_time": bar_time,
                    "exit_price": bar_price,
                    "exit_premium": target_premium,
                    "exit_reason": "profit_target",
                }

        # Expired - calculate final premium
        final_bar = forward.iloc[-1] if len(forward) > 0 else None
        if final_bar is not None:
            final_price = final_bar["close"]
            # At expiration, option is worth intrinsic value
            if opt_type == OptionType.CALL:
                final_premium = max(final_price - strike, 0)
            else:
                final_premium = max(strike - final_price, 0)
            return {
                "exit_time": forward.index[-1],
                "exit_price": final_price,
                "exit_premium": final_premium,
                "exit_reason": "expiration",
            }

        # No forward data - assume loss
        return {
            "exit_time": signal.timestamp,
            "exit_price": signal.entry_price,
            "exit_premium": 0.0,
            "exit_reason": "no_data",
        }

    def run_pattern_comparison(self) -> dict[str, BacktestResult]:
        """Run backtests for each pattern individually to compare performance."""
        all_patterns = list(self.config.enabled_patterns)
        results = {}

        for pattern in all_patterns:
            single_config = AgentConfig(
                **{
                    k: v
                    for k, v in self.config.__dict__.items()
                    if k != "enabled_patterns"
                },
                enabled_patterns=[pattern],
            )
            bt = Backtester(single_config)
            try:
                result = bt.run(use_daily_simulation=True)
                if result.total_trades > 0:
                    results[pattern] = result
            except Exception:
                pass

        return dict(sorted(results.items(), key=lambda x: x[1].total_pnl, reverse=True))
