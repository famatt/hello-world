"""Configuration for SPY pattern detection agent."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AgentConfig:
    """Master configuration for the SPY pattern detection agent."""

    # Data settings
    ticker: str = "SPY"
    history_years: int = 5
    intraday_interval: str = "5m"  # 1m, 2m, 5m, 15m, 30m
    daily_interval: str = "1d"

    # Opening Range settings
    orb_minutes: int = 15  # First N minutes define opening range
    orb_breakout_buffer: float = 0.10  # Buffer above/below range in $

    # VWAP settings
    vwap_rejection_threshold: float = 0.15  # $ distance for VWAP rejection

    # Momentum settings
    rsi_period: int = 14
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    adx_period: int = 14
    adx_trend_threshold: float = 25.0
    ema_fast: int = 9
    ema_slow: int = 21

    # Bollinger Band settings
    bb_period: int = 20
    bb_std: float = 2.0
    bb_squeeze_threshold: float = 0.5  # % bandwidth threshold for squeeze

    # Volume settings
    volume_spike_multiplier: float = 2.0  # x times average volume

    # Mean reversion settings
    mean_rev_zscore_threshold: float = 2.0

    # Support/Resistance settings
    sr_lookback_days: int = 20
    sr_touch_count: int = 3
    sr_proximity_pct: float = 0.1  # % proximity to level

    # Time-of-day windows (ET)
    opening_range_end: str = "09:45"
    midday_reversal_start: str = "11:30"
    midday_reversal_end: str = "12:30"
    power_hour_start: str = "15:00"
    market_close: str = "16:00"

    # 0 DTE Options modeling
    risk_free_rate: float = 0.05
    default_iv: float = 0.15  # Annualized IV fallback

    # Backtesting
    initial_capital: float = 10000.0
    position_size_pct: float = 5.0  # % of capital per trade
    max_loss_per_trade_pct: float = 50.0  # Stop loss as % of premium
    profit_target_pct: float = 100.0  # Take profit as % of premium
    slippage_pct: float = 1.0  # Slippage as % of premium
    commission_per_contract: float = 0.65

    # Alert settings
    alert_cooldown_seconds: int = 300  # Min time between same-pattern alerts
    min_pattern_confidence: float = 0.6  # Minimum confidence to alert (0-1)

    # Patterns to enable
    enabled_patterns: list = field(default_factory=lambda: [
        "opening_range_breakout",
        "opening_range_breakdown",
        "vwap_rejection_long",
        "vwap_rejection_short",
        "vwap_crossover_long",
        "vwap_crossover_short",
        "macd_bullish_cross",
        "macd_bearish_cross",
        "rsi_oversold_bounce",
        "rsi_overbought_fade",
        "ema_bullish_cross",
        "ema_bearish_cross",
        "bollinger_squeeze_breakout",
        "volume_spike_continuation",
        "mean_reversion_long",
        "mean_reversion_short",
        "gap_fill_long",
        "gap_fill_short",
        "previous_day_high_break",
        "previous_day_low_break",
        "midday_reversal",
        "power_hour_momentum",
        "double_bottom",
        "double_top",
        "support_bounce",
        "resistance_rejection",
    ])
