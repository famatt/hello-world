"""Data fetching module for SPY historical and intraday data.

Uses yfinance when available, falls back to Yahoo Finance CSV API.
"""

import datetime as dt
import io
import urllib.request
from typing import Optional, Tuple

import numpy as np
import pandas as pd

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False


class DataFetcher:
    """Fetches and prepares SPY market data for pattern detection."""

    def __init__(self, ticker: str = "SPY"):
        self.ticker = ticker
        self._daily_cache: Optional[pd.DataFrame] = None
        self._intraday_cache: Optional[pd.DataFrame] = None
        self._cache_date: Optional[dt.date] = None

    def _normalize_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize yfinance DataFrame to standard columns."""
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.columns = ["open", "high", "low", "close", "volume"]
        df.index.name = "datetime"
        df.dropna(inplace=True)
        return df

    def _fetch_daily_fallback(self, years: int = 5) -> pd.DataFrame:
        """Fetch daily data via Yahoo Finance CSV endpoint (no yfinance)."""
        end = int(dt.datetime.now().timestamp())
        start = int((dt.datetime.now() - dt.timedelta(days=years * 365)).timestamp())
        url = (
            f"https://query1.finance.yahoo.com/v7/finance/download/{self.ticker}"
            f"?period1={start}&period2={end}&interval=1d&events=history"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=30)
        csv_data = resp.read().decode("utf-8")
        df = pd.read_csv(io.StringIO(csv_data), index_col="Date", parse_dates=True)
        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.columns = ["open", "high", "low", "close", "volume"]
        df.index.name = "datetime"
        df.dropna(inplace=True)
        return df

    def fetch_daily(self, years: int = 5) -> pd.DataFrame:
        """Fetch daily OHLCV data for the last N years."""
        if HAS_YFINANCE:
            end = dt.datetime.now()
            start = end - dt.timedelta(days=years * 365)
            df = yf.download(self.ticker, start=start, end=end, interval="1d", progress=False)
            df = self._normalize_df(df)
        else:
            df = self._fetch_daily_fallback(years)
        self._daily_cache = df
        return df

    def fetch_intraday(self, interval: str = "5m", period: str = "60d") -> pd.DataFrame:
        """Fetch intraday OHLCV data.

        yfinance limits:
        - 1m data: last 7 days
        - 2m/5m/15m: last 60 days
        - 30m/1h: last 730 days

        Falls back to simulating from daily data if yfinance unavailable.
        """
        if HAS_YFINANCE:
            df = yf.download(self.ticker, period=period, interval=interval, progress=False)
            df = self._normalize_df(df)
            df.index = df.index.tz_localize(None) if df.index.tz is None else df.index.tz_convert("US/Eastern").tz_localize(None)
        else:
            # Fallback: fetch daily and simulate intraday
            days = int(period.replace("d", "")) if "d" in period else 60
            daily = self._fetch_daily_fallback(years=max(1, days // 365 + 1))
            daily = daily.tail(days)
            df = self.simulate_intraday_from_daily(daily)
        self._intraday_cache = df
        self._cache_date = dt.date.today()
        return df

    def fetch_max_intraday_history(self, interval: str = "5m") -> pd.DataFrame:
        """Fetch maximum available intraday data by stitching together chunks.

        For 5m data, yfinance allows ~60 days. For longer backtests, we use
        daily data and simulate intraday bars from OHLC.
        """
        # First get actual intraday data (most recent ~60 days)
        period_map = {"1m": "7d", "2m": "60d", "5m": "60d", "15m": "60d", "30m": "730d"}
        period = period_map.get(interval, "60d")
        return self.fetch_intraday(interval=interval, period=period)

    def get_previous_day_levels(self, intraday_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate previous day OHLC levels for each trading day in intraday data."""
        df = intraday_df.copy()
        df["date"] = df.index.date
        daily = df.groupby("date").agg(
            prev_open=("open", "first"),
            prev_high=("high", "max"),
            prev_low=("low", "min"),
            prev_close=("close", "last"),
            prev_volume=("volume", "sum"),
        )
        daily = daily.shift(1)  # Shift to make it "previous day"
        df = df.merge(daily, left_on="date", right_index=True, how="left")
        df.drop(columns=["date"], inplace=True)
        df.dropna(subset=["prev_close"], inplace=True)
        return df

    def simulate_intraday_from_daily(
        self, daily_df: pd.DataFrame, bars_per_day: int = 78
    ) -> pd.DataFrame:
        """Simulate intraday bars from daily OHLC for extended backtesting.

        Uses a simple path simulation: Open -> random walk -> Close with
        High/Low respected. This gives approximate intraday structure for
        backtesting pattern frequency over multiple years.

        78 bars = 6.5 hours * 12 (5-min bars per hour)
        """
        all_rows = []
        for idx, row in daily_df.iterrows():
            date = idx if isinstance(idx, dt.date) else idx.date()
            market_open = dt.datetime.combine(date, dt.time(9, 30))

            o, h, l, c = row["open"], row["high"], row["low"], row["close"]
            vol = row["volume"]

            # Generate price path using interpolation with noise
            np.random.seed(int(date.toordinal()))
            t = np.linspace(0, 1, bars_per_day)

            # Create a smooth path from open to close
            base = o + (c - o) * t

            # Add noise scaled by the day's range
            day_range = h - l if h > l else 0.01
            noise = np.cumsum(np.random.randn(bars_per_day)) * day_range * 0.05
            noise = noise - noise[-1] * t  # Ensure it ends at close

            prices = base + noise

            # Scale to respect high/low
            raw_max, raw_min = prices.max(), prices.min()
            if raw_max > raw_min:
                prices = l + (prices - raw_min) / (raw_max - raw_min) * (h - l)
            prices[0] = o
            prices[-1] = c

            # Build OHLCV bars
            vol_per_bar = vol / bars_per_day
            for i in range(bars_per_day):
                bar_time = market_open + dt.timedelta(minutes=5 * i)
                bar_prices = prices[max(0, i) : i + 2] if i < bars_per_day - 1 else [prices[i]]
                all_rows.append(
                    {
                        "datetime": bar_time,
                        "open": prices[i],
                        "high": max(bar_prices) + np.random.uniform(0, day_range * 0.005),
                        "low": min(bar_prices) - np.random.uniform(0, day_range * 0.005),
                        "close": prices[min(i + 1, bars_per_day - 1)] if i < bars_per_day - 1 else c,
                        "volume": int(vol_per_bar * np.random.uniform(0.5, 1.5)),
                    }
                )

        result = pd.DataFrame(all_rows).set_index("datetime")
        return result

    def get_today_data(self) -> Optional[pd.DataFrame]:
        """Fetch today's intraday data (for live monitoring)."""
        today = dt.date.today()
        if self._cache_date == today and self._intraday_cache is not None:
            mask = self._intraday_cache.index.date == today
            today_data = self._intraday_cache[mask]
            if len(today_data) > 0:
                return today_data
        # Re-fetch
        df = self.fetch_intraday(interval="5m", period="1d")
        mask = df.index.date == today
        return df[mask] if mask.any() else None

    def get_vwap(self, df: pd.DataFrame) -> pd.Series:
        """Calculate intraday VWAP.

        Resets each day for intraday data.
        """
        df = df.copy()
        df["date"] = df.index.date
        df["typical_price"] = (df["high"] + df["low"] + df["close"]) / 3
        df["tp_volume"] = df["typical_price"] * df["volume"]

        vwap = df.groupby("date").apply(
            lambda g: g["tp_volume"].cumsum() / g["volume"].cumsum(),
            include_groups=False,
        )
        if isinstance(vwap.index, pd.MultiIndex):
            vwap = vwap.droplevel(0)
        return vwap.reindex(df.index)
