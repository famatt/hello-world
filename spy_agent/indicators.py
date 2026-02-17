"""Technical indicator calculations for SPY pattern detection."""

import numpy as np
import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average."""
    return series.ewm(span=period, adjust=False).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(window=period).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index."""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """MACD: returns (macd_line, signal_line, histogram)."""
    fast_ema = ema(close, fast)
    slow_ema = ema(close, slow)
    macd_line = fast_ema - slow_ema
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def adx(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Average Directional Index: returns (adx, plus_di, minus_di)."""
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    plus_dm = high.diff()
    minus_dm = -low.diff()

    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    atr = tr.ewm(alpha=1.0 / period, min_periods=period).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1.0 / period, min_periods=period).mean() / atr
    minus_di = 100 * minus_dm.ewm(alpha=1.0 / period, min_periods=period).mean() / atr

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx_val = dx.ewm(alpha=1.0 / period, min_periods=period).mean()

    return adx_val, plus_di, minus_di


def bollinger_bands(
    close: pd.Series, period: int = 20, std_mult: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """Bollinger Bands: returns (upper, middle, lower, bandwidth_pct)."""
    middle = sma(close, period)
    std = close.rolling(window=period).std()
    upper = middle + std_mult * std
    lower = middle - std_mult * std
    bandwidth = ((upper - lower) / middle) * 100
    return upper, middle, lower, bandwidth


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Average True Range."""
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / period, min_periods=period).mean()


def zscore(series: pd.Series, period: int = 20) -> pd.Series:
    """Rolling Z-Score."""
    mean = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    return (series - mean) / std.replace(0, np.nan)


def volume_sma(volume: pd.Series, period: int = 20) -> pd.Series:
    """Volume Simple Moving Average."""
    return sma(volume, period)


def pivot_points(
    high: float, low: float, close: float
) -> dict[str, float]:
    """Classic pivot points from previous day's HLC."""
    pivot = (high + low + close) / 3
    r1 = 2 * pivot - low
    s1 = 2 * pivot - high
    r2 = pivot + (high - low)
    s2 = pivot - (high - low)
    r3 = high + 2 * (pivot - low)
    s3 = low - 2 * (high - pivot)
    return {"pivot": pivot, "r1": r1, "r2": r2, "r3": r3, "s1": s1, "s2": s2, "s3": s3}


def find_support_resistance(
    high: pd.Series, low: pd.Series, close: pd.Series, lookback: int = 20, num_levels: int = 5
) -> tuple[list[float], list[float]]:
    """Find support and resistance levels using price clustering.

    Returns (support_levels, resistance_levels) sorted by strength.
    """
    recent_high = high.tail(lookback)
    recent_low = low.tail(lookback)
    recent_close = close.tail(lookback)
    current_price = close.iloc[-1]

    # Combine all significant price points
    all_prices = pd.concat([recent_high, recent_low]).values
    price_range = all_prices.max() - all_prices.min()
    if price_range == 0:
        return [], []

    # Cluster prices using simple binning
    bin_size = price_range * 0.005  # 0.5% bins
    if bin_size == 0:
        return [], []

    bins = np.arange(all_prices.min(), all_prices.max() + bin_size, bin_size)
    counts, edges = np.histogram(all_prices, bins=bins)

    # Find peaks in the histogram (high-frequency price levels)
    level_candidates = []
    for i in range(1, len(counts) - 1):
        if counts[i] >= counts[i - 1] and counts[i] >= counts[i + 1] and counts[i] >= 2:
            level = (edges[i] + edges[i + 1]) / 2
            level_candidates.append((level, counts[i]))

    # Sort by frequency
    level_candidates.sort(key=lambda x: x[1], reverse=True)

    supports = []
    resistances = []
    for level, strength in level_candidates[:num_levels * 2]:
        if level < current_price:
            supports.append(level)
        else:
            resistances.append(level)

    return supports[:num_levels], resistances[:num_levels]


def detect_double_top(high: pd.Series, lookback: int = 30, tolerance_pct: float = 0.3) -> bool:
    """Detect double top pattern in recent price action."""
    recent = high.tail(lookback)
    if len(recent) < 10:
        return False

    # Find two highest peaks
    peaks = []
    for i in range(2, len(recent) - 2):
        if recent.iloc[i] > recent.iloc[i - 1] and recent.iloc[i] > recent.iloc[i + 1]:
            if recent.iloc[i] > recent.iloc[i - 2] and recent.iloc[i] > recent.iloc[i + 2]:
                peaks.append((i, recent.iloc[i]))

    if len(peaks) < 2:
        return False

    # Check if two highest peaks are at similar levels
    peaks.sort(key=lambda x: x[1], reverse=True)
    p1, p2 = peaks[0], peaks[1]
    tolerance = p1[1] * tolerance_pct / 100
    # Peaks should be at similar height but separated in time
    return abs(p1[1] - p2[1]) < tolerance and abs(p1[0] - p2[0]) > 5


def detect_double_bottom(low: pd.Series, lookback: int = 30, tolerance_pct: float = 0.3) -> bool:
    """Detect double bottom pattern in recent price action."""
    recent = low.tail(lookback)
    if len(recent) < 10:
        return False

    troughs = []
    for i in range(2, len(recent) - 2):
        if recent.iloc[i] < recent.iloc[i - 1] and recent.iloc[i] < recent.iloc[i + 1]:
            if recent.iloc[i] < recent.iloc[i - 2] and recent.iloc[i] < recent.iloc[i + 2]:
                troughs.append((i, recent.iloc[i]))

    if len(troughs) < 2:
        return False

    troughs.sort(key=lambda x: x[1])
    t1, t2 = troughs[0], troughs[1]
    tolerance = t1[1] * tolerance_pct / 100
    return abs(t1[1] - t2[1]) < tolerance and abs(t1[0] - t2[0]) > 5
