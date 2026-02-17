"""Pattern detection engine for SPY 0 DTE options trading.

Detects intraday patterns commonly exploited for zero-days-to-expiration
options on SPY, including opening range breaks, VWAP signals, momentum
shifts, mean reversion setups, and time-of-day seasonality.
"""

import datetime as dt
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd

from spy_agent import indicators
from spy_agent.config import AgentConfig


class Direction(Enum):
    LONG = "LONG"   # Buy calls
    SHORT = "SHORT"  # Buy puts


@dataclass
class Signal:
    """A detected trading signal."""
    timestamp: dt.datetime
    pattern: str
    direction: Direction
    confidence: float          # 0.0 - 1.0
    entry_price: float         # SPY price at signal
    stop_price: float          # Suggested stop level
    target_price: float        # Suggested target level
    description: str           # Human-readable explanation
    metadata: dict = None      # Additional pattern-specific data

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    @property
    def risk_reward(self) -> float:
        risk = abs(self.entry_price - self.stop_price)
        reward = abs(self.target_price - self.entry_price)
        return reward / risk if risk > 0 else 0.0

    def __str__(self) -> str:
        arrow = "CALLS" if self.direction == Direction.LONG else "PUTS"
        return (
            f"[{self.timestamp:%H:%M}] {self.pattern} -> {arrow} | "
            f"Entry: ${self.entry_price:.2f} | Stop: ${self.stop_price:.2f} | "
            f"Target: ${self.target_price:.2f} | R:R {self.risk_reward:.1f} | "
            f"Confidence: {self.confidence:.0%}"
        )


class PatternDetector:
    """Detects trading patterns on SPY intraday data for 0 DTE options."""

    def __init__(self, config: AgentConfig = None):
        self.config = config or AgentConfig()

    def scan(self, df: pd.DataFrame, vwap: pd.Series = None) -> list[Signal]:
        """Run all enabled pattern detectors on the dataframe.

        Args:
            df: Intraday OHLCV DataFrame with columns [open, high, low, close, volume]
                and optionally [prev_open, prev_high, prev_low, prev_close].
            vwap: Pre-calculated VWAP series (optional, calculated if missing).

        Returns:
            List of Signal objects sorted by timestamp.
        """
        signals = []

        # Pre-compute indicators used by multiple patterns
        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        rsi_vals = indicators.rsi(close, self.config.rsi_period)
        macd_line, macd_signal, macd_hist = indicators.macd(
            close, self.config.macd_fast, self.config.macd_slow, self.config.macd_signal
        )
        adx_val, plus_di, minus_di = indicators.adx(high, low, close, self.config.adx_period)
        bb_upper, bb_mid, bb_lower, bb_bw = indicators.bollinger_bands(
            close, self.config.bb_period, self.config.bb_std
        )
        ema_fast = indicators.ema(close, self.config.ema_fast)
        ema_slow = indicators.ema(close, self.config.ema_slow)
        vol_sma = indicators.volume_sma(volume, 20)
        z_score = indicators.zscore(close, 20)
        atr_val = indicators.atr(high, low, close, 14)

        # Store computed indicators for access by individual detectors
        ctx = {
            "df": df, "vwap": vwap, "close": close, "high": high, "low": low,
            "volume": volume, "rsi": rsi_vals, "macd_line": macd_line,
            "macd_signal": macd_signal, "macd_hist": macd_hist, "adx": adx_val,
            "plus_di": plus_di, "minus_di": minus_di, "bb_upper": bb_upper,
            "bb_mid": bb_mid, "bb_lower": bb_lower, "bb_bw": bb_bw,
            "ema_fast": ema_fast, "ema_slow": ema_slow, "vol_sma": vol_sma,
            "zscore": z_score, "atr": atr_val,
        }

        enabled = set(self.config.enabled_patterns)
        detectors = [
            ("opening_range_breakout", self._detect_orb_long),
            ("opening_range_breakdown", self._detect_orb_short),
            ("vwap_rejection_long", self._detect_vwap_rejection_long),
            ("vwap_rejection_short", self._detect_vwap_rejection_short),
            ("vwap_crossover_long", self._detect_vwap_cross_long),
            ("vwap_crossover_short", self._detect_vwap_cross_short),
            ("macd_bullish_cross", self._detect_macd_bull),
            ("macd_bearish_cross", self._detect_macd_bear),
            ("rsi_oversold_bounce", self._detect_rsi_oversold),
            ("rsi_overbought_fade", self._detect_rsi_overbought),
            ("ema_bullish_cross", self._detect_ema_bull_cross),
            ("ema_bearish_cross", self._detect_ema_bear_cross),
            ("bollinger_squeeze_breakout", self._detect_bb_squeeze),
            ("volume_spike_continuation", self._detect_volume_spike),
            ("mean_reversion_long", self._detect_mean_rev_long),
            ("mean_reversion_short", self._detect_mean_rev_short),
            ("gap_fill_long", self._detect_gap_fill_long),
            ("gap_fill_short", self._detect_gap_fill_short),
            ("previous_day_high_break", self._detect_prev_high_break),
            ("previous_day_low_break", self._detect_prev_low_break),
            ("midday_reversal", self._detect_midday_reversal),
            ("power_hour_momentum", self._detect_power_hour),
            ("double_bottom", self._detect_double_bottom),
            ("double_top", self._detect_double_top),
            ("support_bounce", self._detect_support_bounce),
            ("resistance_rejection", self._detect_resistance_rejection),
        ]

        for name, detector in detectors:
            if name in enabled:
                try:
                    pattern_signals = detector(ctx)
                    signals.extend(pattern_signals)
                except Exception:
                    pass  # Skip failed detectors gracefully

        signals.sort(key=lambda s: s.timestamp)
        return signals

    # ─── Opening Range Breakout/Breakdown ──────────────────────────

    def _get_opening_range(self, df: pd.DataFrame) -> dict[str, tuple[float, float]]:
        """Calculate opening range (first N minutes) per trading day."""
        orb_minutes = self.config.orb_minutes
        ranges = {}
        df = df.copy()
        df["date"] = df.index.date
        for date, group in df.groupby("date"):
            first_bar_time = group.index[0]
            cutoff = first_bar_time + dt.timedelta(minutes=orb_minutes)
            or_bars = group[group.index <= cutoff]
            if len(or_bars) > 0:
                ranges[date] = (or_bars["high"].max(), or_bars["low"].min())
        return ranges

    def _detect_orb_long(self, ctx: dict) -> list[Signal]:
        """Opening Range Breakout (upside) - buy calls."""
        df = ctx["df"]
        atr_val = ctx["atr"]
        signals = []
        or_ranges = self._get_opening_range(df)
        df_copy = df.copy()
        df_copy["date"] = df_copy.index.date

        for date, (or_high, or_low) in or_ranges.items():
            day_bars = df_copy[df_copy["date"] == date]
            cutoff_time = day_bars.index[0] + dt.timedelta(minutes=self.config.orb_minutes)
            post_or = day_bars[day_bars.index > cutoff_time]

            for i in range(1, len(post_or)):
                row = post_or.iloc[i]
                prev = post_or.iloc[i - 1]
                threshold = or_high + self.config.orb_breakout_buffer

                if prev["close"] <= threshold and row["close"] > threshold:
                    atr_at = atr_val.get(post_or.index[i], 1.0)
                    if pd.isna(atr_at):
                        atr_at = 1.0
                    signals.append(Signal(
                        timestamp=post_or.index[i],
                        pattern="opening_range_breakout",
                        direction=Direction.LONG,
                        confidence=self._orb_confidence(row, or_high, or_low, ctx, post_or.index[i]),
                        entry_price=row["close"],
                        stop_price=or_high - 0.5 * (or_high - or_low),
                        target_price=row["close"] + 1.5 * (or_high - or_low),
                        description=f"ORB Long: price broke above opening range high ${or_high:.2f}",
                        metadata={"or_high": or_high, "or_low": or_low},
                    ))
                    break  # One signal per day

        return signals

    def _detect_orb_short(self, ctx: dict) -> list[Signal]:
        """Opening Range Breakdown (downside) - buy puts."""
        df = ctx["df"]
        signals = []
        or_ranges = self._get_opening_range(df)
        df_copy = df.copy()
        df_copy["date"] = df_copy.index.date

        for date, (or_high, or_low) in or_ranges.items():
            day_bars = df_copy[df_copy["date"] == date]
            cutoff_time = day_bars.index[0] + dt.timedelta(minutes=self.config.orb_minutes)
            post_or = day_bars[day_bars.index > cutoff_time]

            for i in range(1, len(post_or)):
                row = post_or.iloc[i]
                prev = post_or.iloc[i - 1]
                threshold = or_low - self.config.orb_breakout_buffer

                if prev["close"] >= threshold and row["close"] < threshold:
                    signals.append(Signal(
                        timestamp=post_or.index[i],
                        pattern="opening_range_breakdown",
                        direction=Direction.SHORT,
                        confidence=self._orb_confidence(row, or_high, or_low, ctx, post_or.index[i]),
                        entry_price=row["close"],
                        stop_price=or_low + 0.5 * (or_high - or_low),
                        target_price=row["close"] - 1.5 * (or_high - or_low),
                        description=f"ORB Short: price broke below opening range low ${or_low:.2f}",
                        metadata={"or_high": or_high, "or_low": or_low},
                    ))
                    break

        return signals

    def _orb_confidence(self, row, or_high, or_low, ctx, idx) -> float:
        """Calculate confidence for ORB signal using confirming indicators."""
        conf = 0.5
        vol = ctx["volume"].get(idx, 0)
        vol_avg = ctx["vol_sma"].get(idx, 1)
        if not pd.isna(vol) and not pd.isna(vol_avg) and vol_avg > 0:
            if vol > 1.5 * vol_avg:
                conf += 0.15
        adx_at = ctx["adx"].get(idx, 0)
        if not pd.isna(adx_at) and adx_at > self.config.adx_trend_threshold:
            conf += 0.15
        or_range = or_high - or_low
        if or_range > 0:
            atr_at = ctx["atr"].get(idx, or_range)
            if not pd.isna(atr_at) and or_range < atr_at:
                conf += 0.1  # Tight opening range = stronger breakout
        return min(conf, 1.0)

    # ─── VWAP Patterns ─────────────────────────────────────────────

    def _detect_vwap_rejection_long(self, ctx: dict) -> list[Signal]:
        """Price dips to VWAP and bounces - buy calls."""
        signals = []
        if ctx["vwap"] is None:
            return signals

        df = ctx["df"]
        vwap = ctx["vwap"]
        atr_val = ctx["atr"]
        thresh = self.config.vwap_rejection_threshold

        for i in range(2, len(df)):
            idx = df.index[i]
            price = df["close"].iloc[i]
            v = vwap.get(idx, np.nan)
            if pd.isna(v):
                continue

            # Price touched VWAP (within threshold) and bounced up
            prev_low = df["low"].iloc[i - 1]
            if abs(prev_low - v) < thresh and price > v + thresh:
                a = atr_val.get(idx, 1.0)
                if pd.isna(a):
                    a = 1.0
                signals.append(Signal(
                    timestamp=idx,
                    pattern="vwap_rejection_long",
                    direction=Direction.LONG,
                    confidence=0.65,
                    entry_price=price,
                    stop_price=v - a * 0.5,
                    target_price=price + a,
                    description=f"VWAP Rejection Long: bounced off VWAP ${v:.2f}",
                ))

        return signals

    def _detect_vwap_rejection_short(self, ctx: dict) -> list[Signal]:
        """Price rallies to VWAP and rejects - buy puts."""
        signals = []
        if ctx["vwap"] is None:
            return signals

        df = ctx["df"]
        vwap = ctx["vwap"]
        atr_val = ctx["atr"]
        thresh = self.config.vwap_rejection_threshold

        for i in range(2, len(df)):
            idx = df.index[i]
            price = df["close"].iloc[i]
            v = vwap.get(idx, np.nan)
            if pd.isna(v):
                continue

            prev_high = df["high"].iloc[i - 1]
            if abs(prev_high - v) < thresh and price < v - thresh:
                a = atr_val.get(idx, 1.0)
                if pd.isna(a):
                    a = 1.0
                signals.append(Signal(
                    timestamp=idx,
                    pattern="vwap_rejection_short",
                    direction=Direction.SHORT,
                    confidence=0.65,
                    entry_price=price,
                    stop_price=v + a * 0.5,
                    target_price=price - a,
                    description=f"VWAP Rejection Short: rejected at VWAP ${v:.2f}",
                ))

        return signals

    def _detect_vwap_cross_long(self, ctx: dict) -> list[Signal]:
        """Price crosses above VWAP - bullish."""
        signals = []
        if ctx["vwap"] is None:
            return signals
        df, vwap, atr_val = ctx["df"], ctx["vwap"], ctx["atr"]

        for i in range(1, len(df)):
            idx = df.index[i]
            v = vwap.get(idx, np.nan)
            v_prev = vwap.get(df.index[i - 1], np.nan)
            if pd.isna(v) or pd.isna(v_prev):
                continue
            if df["close"].iloc[i - 1] < v_prev and df["close"].iloc[i] > v:
                a = atr_val.get(idx, 1.0)
                if pd.isna(a):
                    a = 1.0
                signals.append(Signal(
                    timestamp=idx, pattern="vwap_crossover_long",
                    direction=Direction.LONG, confidence=0.55,
                    entry_price=df["close"].iloc[i],
                    stop_price=v - a * 0.3, target_price=df["close"].iloc[i] + a * 0.8,
                    description=f"VWAP Cross Long: price crossed above VWAP ${v:.2f}",
                ))
        return signals

    def _detect_vwap_cross_short(self, ctx: dict) -> list[Signal]:
        """Price crosses below VWAP - bearish."""
        signals = []
        if ctx["vwap"] is None:
            return signals
        df, vwap, atr_val = ctx["df"], ctx["vwap"], ctx["atr"]

        for i in range(1, len(df)):
            idx = df.index[i]
            v = vwap.get(idx, np.nan)
            v_prev = vwap.get(df.index[i - 1], np.nan)
            if pd.isna(v) or pd.isna(v_prev):
                continue
            if df["close"].iloc[i - 1] > v_prev and df["close"].iloc[i] < v:
                a = atr_val.get(idx, 1.0)
                if pd.isna(a):
                    a = 1.0
                signals.append(Signal(
                    timestamp=idx, pattern="vwap_crossover_short",
                    direction=Direction.SHORT, confidence=0.55,
                    entry_price=df["close"].iloc[i],
                    stop_price=v + a * 0.3, target_price=df["close"].iloc[i] - a * 0.8,
                    description=f"VWAP Cross Short: price crossed below VWAP ${v:.2f}",
                ))
        return signals

    # ─── Momentum Patterns ─────────────────────────────────────────

    def _detect_macd_bull(self, ctx: dict) -> list[Signal]:
        """MACD bullish crossover."""
        signals = []
        ml, ms = ctx["macd_line"], ctx["macd_signal"]
        df, atr_val = ctx["df"], ctx["atr"]

        for i in range(1, len(df)):
            idx = df.index[i]
            if pd.isna(ml.iloc[i]) or pd.isna(ms.iloc[i]):
                continue
            if ml.iloc[i - 1] < ms.iloc[i - 1] and ml.iloc[i] > ms.iloc[i]:
                a = atr_val.get(idx, 1.0)
                if pd.isna(a):
                    a = 1.0
                conf = 0.55
                if ctx["adx"].get(idx, 0) > self.config.adx_trend_threshold:
                    conf += 0.1
                signals.append(Signal(
                    timestamp=idx, pattern="macd_bullish_cross",
                    direction=Direction.LONG, confidence=conf,
                    entry_price=df["close"].iloc[i],
                    stop_price=df["close"].iloc[i] - a,
                    target_price=df["close"].iloc[i] + a * 1.5,
                    description="MACD Bullish Cross: MACD crossed above signal line",
                ))
        return signals

    def _detect_macd_bear(self, ctx: dict) -> list[Signal]:
        """MACD bearish crossover."""
        signals = []
        ml, ms = ctx["macd_line"], ctx["macd_signal"]
        df, atr_val = ctx["df"], ctx["atr"]

        for i in range(1, len(df)):
            idx = df.index[i]
            if pd.isna(ml.iloc[i]) or pd.isna(ms.iloc[i]):
                continue
            if ml.iloc[i - 1] > ms.iloc[i - 1] and ml.iloc[i] < ms.iloc[i]:
                a = atr_val.get(idx, 1.0)
                if pd.isna(a):
                    a = 1.0
                conf = 0.55
                if ctx["adx"].get(idx, 0) > self.config.adx_trend_threshold:
                    conf += 0.1
                signals.append(Signal(
                    timestamp=idx, pattern="macd_bearish_cross",
                    direction=Direction.SHORT, confidence=conf,
                    entry_price=df["close"].iloc[i],
                    stop_price=df["close"].iloc[i] + a,
                    target_price=df["close"].iloc[i] - a * 1.5,
                    description="MACD Bearish Cross: MACD crossed below signal line",
                ))
        return signals

    def _detect_rsi_oversold(self, ctx: dict) -> list[Signal]:
        """RSI drops below oversold, then crosses back above - buy calls."""
        signals = []
        rsi_vals = ctx["rsi"]
        df, atr_val = ctx["df"], ctx["atr"]
        threshold = self.config.rsi_oversold

        for i in range(1, len(df)):
            idx = df.index[i]
            if pd.isna(rsi_vals.iloc[i]) or pd.isna(rsi_vals.iloc[i - 1]):
                continue
            if rsi_vals.iloc[i - 1] < threshold and rsi_vals.iloc[i] > threshold:
                a = atr_val.get(idx, 1.0)
                if pd.isna(a):
                    a = 1.0
                signals.append(Signal(
                    timestamp=idx, pattern="rsi_oversold_bounce",
                    direction=Direction.LONG, confidence=0.6,
                    entry_price=df["close"].iloc[i],
                    stop_price=df["low"].iloc[i] - a * 0.3,
                    target_price=df["close"].iloc[i] + a,
                    description=f"RSI Oversold Bounce: RSI crossed above {threshold} from below",
                ))
        return signals

    def _detect_rsi_overbought(self, ctx: dict) -> list[Signal]:
        """RSI rises above overbought, then crosses back below - buy puts."""
        signals = []
        rsi_vals = ctx["rsi"]
        df, atr_val = ctx["df"], ctx["atr"]
        threshold = self.config.rsi_overbought

        for i in range(1, len(df)):
            idx = df.index[i]
            if pd.isna(rsi_vals.iloc[i]) or pd.isna(rsi_vals.iloc[i - 1]):
                continue
            if rsi_vals.iloc[i - 1] > threshold and rsi_vals.iloc[i] < threshold:
                a = atr_val.get(idx, 1.0)
                if pd.isna(a):
                    a = 1.0
                signals.append(Signal(
                    timestamp=idx, pattern="rsi_overbought_fade",
                    direction=Direction.SHORT, confidence=0.6,
                    entry_price=df["close"].iloc[i],
                    stop_price=df["high"].iloc[i] + a * 0.3,
                    target_price=df["close"].iloc[i] - a,
                    description=f"RSI Overbought Fade: RSI crossed below {threshold} from above",
                ))
        return signals

    def _detect_ema_bull_cross(self, ctx: dict) -> list[Signal]:
        """EMA 9/21 bullish crossover."""
        signals = []
        ef, es = ctx["ema_fast"], ctx["ema_slow"]
        df, atr_val = ctx["df"], ctx["atr"]

        for i in range(1, len(df)):
            idx = df.index[i]
            if pd.isna(ef.iloc[i]) or pd.isna(es.iloc[i]):
                continue
            if ef.iloc[i - 1] < es.iloc[i - 1] and ef.iloc[i] > es.iloc[i]:
                a = atr_val.get(idx, 1.0)
                if pd.isna(a):
                    a = 1.0
                signals.append(Signal(
                    timestamp=idx, pattern="ema_bullish_cross",
                    direction=Direction.LONG, confidence=0.55,
                    entry_price=df["close"].iloc[i],
                    stop_price=es.iloc[i] - a * 0.3,
                    target_price=df["close"].iloc[i] + a,
                    description=f"EMA Bull Cross: EMA{self.config.ema_fast} crossed above EMA{self.config.ema_slow}",
                ))
        return signals

    def _detect_ema_bear_cross(self, ctx: dict) -> list[Signal]:
        """EMA 9/21 bearish crossover."""
        signals = []
        ef, es = ctx["ema_fast"], ctx["ema_slow"]
        df, atr_val = ctx["df"], ctx["atr"]

        for i in range(1, len(df)):
            idx = df.index[i]
            if pd.isna(ef.iloc[i]) or pd.isna(es.iloc[i]):
                continue
            if ef.iloc[i - 1] > es.iloc[i - 1] and ef.iloc[i] < es.iloc[i]:
                a = atr_val.get(idx, 1.0)
                if pd.isna(a):
                    a = 1.0
                signals.append(Signal(
                    timestamp=idx, pattern="ema_bearish_cross",
                    direction=Direction.SHORT, confidence=0.55,
                    entry_price=df["close"].iloc[i],
                    stop_price=es.iloc[i] + a * 0.3,
                    target_price=df["close"].iloc[i] - a,
                    description=f"EMA Bear Cross: EMA{self.config.ema_fast} crossed below EMA{self.config.ema_slow}",
                ))
        return signals

    # ─── Bollinger Band Squeeze ────────────────────────────────────

    def _detect_bb_squeeze(self, ctx: dict) -> list[Signal]:
        """Bollinger Band squeeze followed by breakout."""
        signals = []
        df = ctx["df"]
        bb_bw, bb_upper, bb_lower = ctx["bb_bw"], ctx["bb_upper"], ctx["bb_lower"]
        atr_val = ctx["atr"]
        squeeze_thresh = self.config.bb_squeeze_threshold

        in_squeeze = False
        for i in range(1, len(df)):
            idx = df.index[i]
            bw = bb_bw.iloc[i]
            if pd.isna(bw):
                continue

            if bw < squeeze_thresh:
                in_squeeze = True
                continue

            if in_squeeze and bw >= squeeze_thresh:
                in_squeeze = False
                price = df["close"].iloc[i]
                a = atr_val.get(idx, 1.0)
                if pd.isna(a):
                    a = 1.0
                upper = bb_upper.iloc[i]
                lower = bb_lower.iloc[i]

                if not pd.isna(upper) and price > upper:
                    signals.append(Signal(
                        timestamp=idx, pattern="bollinger_squeeze_breakout",
                        direction=Direction.LONG, confidence=0.65,
                        entry_price=price, stop_price=price - a,
                        target_price=price + a * 1.5,
                        description="BB Squeeze Breakout Long: volatility expansion to upside",
                    ))
                elif not pd.isna(lower) and price < lower:
                    signals.append(Signal(
                        timestamp=idx, pattern="bollinger_squeeze_breakout",
                        direction=Direction.SHORT, confidence=0.65,
                        entry_price=price, stop_price=price + a,
                        target_price=price - a * 1.5,
                        description="BB Squeeze Breakout Short: volatility expansion to downside",
                    ))
        return signals

    # ─── Volume Spike ──────────────────────────────────────────────

    def _detect_volume_spike(self, ctx: dict) -> list[Signal]:
        """Unusual volume spike with price continuation."""
        signals = []
        df, vol, vol_avg, atr_val = ctx["df"], ctx["volume"], ctx["vol_sma"], ctx["atr"]
        mult = self.config.volume_spike_multiplier

        for i in range(2, len(df)):
            idx = df.index[i]
            v = vol.iloc[i - 1]
            va = vol_avg.iloc[i - 1]
            if pd.isna(v) or pd.isna(va) or va == 0:
                continue
            if v > mult * va:
                # Check continuation direction
                move = df["close"].iloc[i - 1] - df["open"].iloc[i - 1]
                confirm = df["close"].iloc[i] - df["open"].iloc[i]
                a = atr_val.get(idx, 1.0)
                if pd.isna(a):
                    a = 1.0

                if move > 0 and confirm > 0:
                    signals.append(Signal(
                        timestamp=idx, pattern="volume_spike_continuation",
                        direction=Direction.LONG, confidence=0.6,
                        entry_price=df["close"].iloc[i],
                        stop_price=df["low"].iloc[i - 1],
                        target_price=df["close"].iloc[i] + a,
                        description=f"Volume Spike Long: {v/va:.1f}x avg volume with bullish continuation",
                    ))
                elif move < 0 and confirm < 0:
                    signals.append(Signal(
                        timestamp=idx, pattern="volume_spike_continuation",
                        direction=Direction.SHORT, confidence=0.6,
                        entry_price=df["close"].iloc[i],
                        stop_price=df["high"].iloc[i - 1],
                        target_price=df["close"].iloc[i] - a,
                        description=f"Volume Spike Short: {v/va:.1f}x avg volume with bearish continuation",
                    ))
        return signals

    # ─── Mean Reversion ────────────────────────────────────────────

    def _detect_mean_rev_long(self, ctx: dict) -> list[Signal]:
        """Price z-score extremely negative -> mean reversion long."""
        signals = []
        df, zs, atr_val = ctx["df"], ctx["zscore"], ctx["atr"]
        thresh = self.config.mean_rev_zscore_threshold

        for i in range(1, len(df)):
            idx = df.index[i]
            if pd.isna(zs.iloc[i]) or pd.isna(zs.iloc[i - 1]):
                continue
            if zs.iloc[i - 1] < -thresh and zs.iloc[i] > -thresh:
                a = atr_val.get(idx, 1.0)
                if pd.isna(a):
                    a = 1.0
                signals.append(Signal(
                    timestamp=idx, pattern="mean_reversion_long",
                    direction=Direction.LONG, confidence=0.6,
                    entry_price=df["close"].iloc[i],
                    stop_price=df["close"].iloc[i] - a,
                    target_price=ctx["bb_mid"].iloc[i] if not pd.isna(ctx["bb_mid"].iloc[i]) else df["close"].iloc[i] + a,
                    description=f"Mean Reversion Long: z-score recovered from {zs.iloc[i-1]:.1f}",
                ))
        return signals

    def _detect_mean_rev_short(self, ctx: dict) -> list[Signal]:
        """Price z-score extremely positive -> mean reversion short."""
        signals = []
        df, zs, atr_val = ctx["df"], ctx["zscore"], ctx["atr"]
        thresh = self.config.mean_rev_zscore_threshold

        for i in range(1, len(df)):
            idx = df.index[i]
            if pd.isna(zs.iloc[i]) or pd.isna(zs.iloc[i - 1]):
                continue
            if zs.iloc[i - 1] > thresh and zs.iloc[i] < thresh:
                a = atr_val.get(idx, 1.0)
                if pd.isna(a):
                    a = 1.0
                signals.append(Signal(
                    timestamp=idx, pattern="mean_reversion_short",
                    direction=Direction.SHORT, confidence=0.6,
                    entry_price=df["close"].iloc[i],
                    stop_price=df["close"].iloc[i] + a,
                    target_price=ctx["bb_mid"].iloc[i] if not pd.isna(ctx["bb_mid"].iloc[i]) else df["close"].iloc[i] - a,
                    description=f"Mean Reversion Short: z-score dropped from {zs.iloc[i-1]:.1f}",
                ))
        return signals

    # ─── Gap Patterns ──────────────────────────────────────────────

    def _detect_gap_fill_long(self, ctx: dict) -> list[Signal]:
        """Gap down that starts filling (long)."""
        signals = []
        df = ctx["df"]
        atr_val = ctx["atr"]
        if "prev_close" not in df.columns:
            return signals

        df_copy = df.copy()
        df_copy["date"] = df_copy.index.date
        for date, group in df_copy.groupby("date"):
            if len(group) < 3:
                continue
            first_bar = group.iloc[0]
            prev_close = first_bar.get("prev_close", np.nan)
            if pd.isna(prev_close):
                continue
            gap = first_bar["open"] - prev_close
            if gap < -0.5:  # Gap down > $0.50
                for i in range(2, min(len(group), 12)):  # First hour
                    if group["close"].iloc[i] > group["close"].iloc[i - 1]:
                        idx = group.index[i]
                        a = atr_val.get(idx, 1.0)
                        if pd.isna(a):
                            a = 1.0
                        signals.append(Signal(
                            timestamp=idx, pattern="gap_fill_long",
                            direction=Direction.LONG, confidence=0.6,
                            entry_price=group["close"].iloc[i],
                            stop_price=group["low"].iloc[:i + 1].min(),
                            target_price=prev_close,
                            description=f"Gap Fill Long: filling ${abs(gap):.2f} gap down",
                            metadata={"gap_size": gap, "prev_close": prev_close},
                        ))
                        break
        return signals

    def _detect_gap_fill_short(self, ctx: dict) -> list[Signal]:
        """Gap up that starts filling (short)."""
        signals = []
        df = ctx["df"]
        atr_val = ctx["atr"]
        if "prev_close" not in df.columns:
            return signals

        df_copy = df.copy()
        df_copy["date"] = df_copy.index.date
        for date, group in df_copy.groupby("date"):
            if len(group) < 3:
                continue
            first_bar = group.iloc[0]
            prev_close = first_bar.get("prev_close", np.nan)
            if pd.isna(prev_close):
                continue
            gap = first_bar["open"] - prev_close
            if gap > 0.5:
                for i in range(2, min(len(group), 12)):
                    if group["close"].iloc[i] < group["close"].iloc[i - 1]:
                        idx = group.index[i]
                        a = atr_val.get(idx, 1.0)
                        if pd.isna(a):
                            a = 1.0
                        signals.append(Signal(
                            timestamp=idx, pattern="gap_fill_short",
                            direction=Direction.SHORT, confidence=0.6,
                            entry_price=group["close"].iloc[i],
                            stop_price=group["high"].iloc[:i + 1].max(),
                            target_price=prev_close,
                            description=f"Gap Fill Short: filling ${gap:.2f} gap up",
                            metadata={"gap_size": gap, "prev_close": prev_close},
                        ))
                        break
        return signals

    # ─── Previous Day Level Breaks ─────────────────────────────────

    def _detect_prev_high_break(self, ctx: dict) -> list[Signal]:
        """Price breaks above previous day's high."""
        signals = []
        df = ctx["df"]
        atr_val = ctx["atr"]
        if "prev_high" not in df.columns:
            return signals

        for i in range(1, len(df)):
            idx = df.index[i]
            ph = df["prev_high"].iloc[i]
            if pd.isna(ph):
                continue
            if df["close"].iloc[i - 1] <= ph and df["close"].iloc[i] > ph:
                a = atr_val.get(idx, 1.0)
                if pd.isna(a):
                    a = 1.0
                signals.append(Signal(
                    timestamp=idx, pattern="previous_day_high_break",
                    direction=Direction.LONG, confidence=0.65,
                    entry_price=df["close"].iloc[i],
                    stop_price=ph - a * 0.3,
                    target_price=df["close"].iloc[i] + a,
                    description=f"Prev Day High Break: broke above ${ph:.2f}",
                ))
        return signals

    def _detect_prev_low_break(self, ctx: dict) -> list[Signal]:
        """Price breaks below previous day's low."""
        signals = []
        df = ctx["df"]
        atr_val = ctx["atr"]
        if "prev_low" not in df.columns:
            return signals

        for i in range(1, len(df)):
            idx = df.index[i]
            pl = df["prev_low"].iloc[i]
            if pd.isna(pl):
                continue
            if df["close"].iloc[i - 1] >= pl and df["close"].iloc[i] < pl:
                a = atr_val.get(idx, 1.0)
                if pd.isna(a):
                    a = 1.0
                signals.append(Signal(
                    timestamp=idx, pattern="previous_day_low_break",
                    direction=Direction.SHORT, confidence=0.65,
                    entry_price=df["close"].iloc[i],
                    stop_price=pl + a * 0.3,
                    target_price=df["close"].iloc[i] - a,
                    description=f"Prev Day Low Break: broke below ${pl:.2f}",
                ))
        return signals

    # ─── Time-of-Day Patterns ──────────────────────────────────────

    def _detect_midday_reversal(self, ctx: dict) -> list[Signal]:
        """Midday reversal pattern (11:30 - 12:30 ET)."""
        signals = []
        df = ctx["df"]
        atr_val = ctx["atr"]
        rsi_vals = ctx["rsi"]

        df_copy = df.copy()
        df_copy["time"] = df_copy.index.time
        df_copy["date"] = df_copy.index.date

        for date, group in df_copy.groupby("date"):
            midday = group[
                (group["time"] >= dt.time(11, 30)) & (group["time"] <= dt.time(12, 30))
            ]
            if len(midday) < 3:
                continue

            # Check morning trend
            morning = group[group["time"] < dt.time(11, 30)]
            if len(morning) < 5:
                continue

            morning_move = morning["close"].iloc[-1] - morning["open"].iloc[0]

            for i in range(2, len(midday)):
                idx = midday.index[i]
                rsi_val = rsi_vals.get(idx, 50)
                if pd.isna(rsi_val):
                    rsi_val = 50
                a = atr_val.get(idx, 1.0)
                if pd.isna(a):
                    a = 1.0

                # Morning was bullish, midday reversal down
                if morning_move > a * 0.5 and rsi_val > 65:
                    if midday["close"].iloc[i] < midday["close"].iloc[i - 1] < midday["close"].iloc[i - 2]:
                        signals.append(Signal(
                            timestamp=idx, pattern="midday_reversal",
                            direction=Direction.SHORT, confidence=0.6,
                            entry_price=midday["close"].iloc[i],
                            stop_price=midday["high"].iloc[:i + 1].max(),
                            target_price=midday["close"].iloc[i] - a * 0.8,
                            description="Midday Reversal Short: bearish reversal after bullish morning",
                        ))
                        break

                # Morning was bearish, midday reversal up
                if morning_move < -a * 0.5 and rsi_val < 35:
                    if midday["close"].iloc[i] > midday["close"].iloc[i - 1] > midday["close"].iloc[i - 2]:
                        signals.append(Signal(
                            timestamp=idx, pattern="midday_reversal",
                            direction=Direction.LONG, confidence=0.6,
                            entry_price=midday["close"].iloc[i],
                            stop_price=midday["low"].iloc[:i + 1].min(),
                            target_price=midday["close"].iloc[i] + a * 0.8,
                            description="Midday Reversal Long: bullish reversal after bearish morning",
                        ))
                        break
        return signals

    def _detect_power_hour(self, ctx: dict) -> list[Signal]:
        """Power hour momentum (3:00 - 4:00 PM ET)."""
        signals = []
        df = ctx["df"]
        atr_val = ctx["atr"]
        adx_vals = ctx["adx"]

        df_copy = df.copy()
        df_copy["time"] = df_copy.index.time
        df_copy["date"] = df_copy.index.date

        for date, group in df_copy.groupby("date"):
            power = group[
                (group["time"] >= dt.time(15, 0)) & (group["time"] <= dt.time(15, 30))
            ]
            if len(power) < 3:
                continue

            # Determine day's trend going into power hour
            pre_power = group[group["time"] < dt.time(15, 0)]
            if len(pre_power) < 10:
                continue

            day_move = pre_power["close"].iloc[-1] - pre_power["open"].iloc[0]
            idx = power.index[2]
            a = atr_val.get(idx, 1.0)
            if pd.isna(a):
                a = 1.0
            adx_at = adx_vals.get(idx, 0)
            if pd.isna(adx_at):
                adx_at = 0

            # Strong trend into power hour with ADX confirmation
            if abs(day_move) > a * 0.5 and adx_at > 20:
                first_moves = power["close"].iloc[2] - power["close"].iloc[0]
                if day_move > 0 and first_moves > 0:
                    signals.append(Signal(
                        timestamp=idx, pattern="power_hour_momentum",
                        direction=Direction.LONG, confidence=0.6,
                        entry_price=power["close"].iloc[2],
                        stop_price=power["low"].iloc[:3].min(),
                        target_price=power["close"].iloc[2] + a * 0.5,
                        description="Power Hour Momentum Long: bullish trend continuing into close",
                    ))
                elif day_move < 0 and first_moves < 0:
                    signals.append(Signal(
                        timestamp=idx, pattern="power_hour_momentum",
                        direction=Direction.SHORT, confidence=0.6,
                        entry_price=power["close"].iloc[2],
                        stop_price=power["high"].iloc[:3].max(),
                        target_price=power["close"].iloc[2] - a * 0.5,
                        description="Power Hour Momentum Short: bearish trend continuing into close",
                    ))
        return signals

    # ─── Chart Patterns ────────────────────────────────────────────

    def _detect_double_bottom(self, ctx: dict) -> list[Signal]:
        """Double bottom pattern."""
        signals = []
        df = ctx["df"]
        atr_val = ctx["atr"]

        df_copy = df.copy()
        df_copy["date"] = df_copy.index.date
        for date, group in df_copy.groupby("date"):
            if len(group) < 15:
                continue
            if indicators.detect_double_bottom(group["low"], lookback=len(group)):
                idx = group.index[-1]
                a = atr_val.get(idx, 1.0)
                if pd.isna(a):
                    a = 1.0
                signals.append(Signal(
                    timestamp=idx, pattern="double_bottom",
                    direction=Direction.LONG, confidence=0.65,
                    entry_price=group["close"].iloc[-1],
                    stop_price=group["low"].min() - a * 0.2,
                    target_price=group["close"].iloc[-1] + (group["close"].iloc[-1] - group["low"].min()),
                    description="Double Bottom: bullish reversal pattern detected",
                ))
        return signals

    def _detect_double_top(self, ctx: dict) -> list[Signal]:
        """Double top pattern."""
        signals = []
        df = ctx["df"]
        atr_val = ctx["atr"]

        df_copy = df.copy()
        df_copy["date"] = df_copy.index.date
        for date, group in df_copy.groupby("date"):
            if len(group) < 15:
                continue
            if indicators.detect_double_top(group["high"], lookback=len(group)):
                idx = group.index[-1]
                a = atr_val.get(idx, 1.0)
                if pd.isna(a):
                    a = 1.0
                signals.append(Signal(
                    timestamp=idx, pattern="double_top",
                    direction=Direction.SHORT, confidence=0.65,
                    entry_price=group["close"].iloc[-1],
                    stop_price=group["high"].max() + a * 0.2,
                    target_price=group["close"].iloc[-1] - (group["high"].max() - group["close"].iloc[-1]),
                    description="Double Top: bearish reversal pattern detected",
                ))
        return signals

    # ─── Support/Resistance ────────────────────────────────────────

    def _detect_support_bounce(self, ctx: dict) -> list[Signal]:
        """Price bounces off a support level."""
        signals = []
        df = ctx["df"]
        atr_val = ctx["atr"]

        supports, _ = indicators.find_support_resistance(
            df["high"], df["low"], df["close"],
            lookback=self.config.sr_lookback_days * 78,  # Approx bars
        )
        if not supports:
            return signals

        for i in range(2, len(df)):
            idx = df.index[i]
            for s_level in supports[:3]:
                proximity = abs(df["low"].iloc[i - 1] - s_level) / s_level * 100
                if proximity < self.config.sr_proximity_pct:
                    if df["close"].iloc[i] > df["close"].iloc[i - 1]:
                        a = atr_val.get(idx, 1.0)
                        if pd.isna(a):
                            a = 1.0
                        signals.append(Signal(
                            timestamp=idx, pattern="support_bounce",
                            direction=Direction.LONG, confidence=0.6,
                            entry_price=df["close"].iloc[i],
                            stop_price=s_level - a * 0.3,
                            target_price=df["close"].iloc[i] + a,
                            description=f"Support Bounce: bounced off support ${s_level:.2f}",
                            metadata={"support_level": s_level},
                        ))
                        break
        return signals

    def _detect_resistance_rejection(self, ctx: dict) -> list[Signal]:
        """Price rejects at a resistance level."""
        signals = []
        df = ctx["df"]
        atr_val = ctx["atr"]

        _, resistances = indicators.find_support_resistance(
            df["high"], df["low"], df["close"],
            lookback=self.config.sr_lookback_days * 78,
        )
        if not resistances:
            return signals

        for i in range(2, len(df)):
            idx = df.index[i]
            for r_level in resistances[:3]:
                proximity = abs(df["high"].iloc[i - 1] - r_level) / r_level * 100
                if proximity < self.config.sr_proximity_pct:
                    if df["close"].iloc[i] < df["close"].iloc[i - 1]:
                        a = atr_val.get(idx, 1.0)
                        if pd.isna(a):
                            a = 1.0
                        signals.append(Signal(
                            timestamp=idx, pattern="resistance_rejection",
                            direction=Direction.SHORT, confidence=0.6,
                            entry_price=df["close"].iloc[i],
                            stop_price=r_level + a * 0.3,
                            target_price=df["close"].iloc[i] - a,
                            description=f"Resistance Rejection: rejected at resistance ${r_level:.2f}",
                            metadata={"resistance_level": r_level},
                        ))
                        break
        return signals
