"""
Technical indicators calculation.

Supports MA, MACD, RSI, Bollinger Bands using yfinance OHLCV data format.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def calculate_ma(close: list[float], period: int) -> list[Optional[float]]:
    """
    Calculate Moving Average.

    Args:
        close: List of closing prices
        period: MA period (e.g., 5, 10, 20, 60)

    Returns:
        List of MA values (None for periods before sufficient data)
    """
    if len(close) < period:
        return [None] * len(close)

    result = []
    for i in range(len(close)):
        if i < period - 1:
            result.append(None)
        else:
            result.append(round(sum(close[i - period + 1 : i + 1]) / period, 4))
    return result


def calculate_macd(
    close: list[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> dict:
    """
    Calculate MACD (Moving Average Convergence Divergence).

    Args:
        close: List of closing prices
        fast_period: Fast EMA period (default 12)
        slow_period: Slow EMA period (default 26)
        signal_period: Signal line period (default 9)

    Returns:
        Dict with 'macd', 'signal', 'histogram' lists
    """
    if len(close) < slow_period:
        return {"macd": [None] * len(close), "signal": [None] * len(close), "histogram": [None] * len(close)}

    # Calculate EMAs
    ema_fast = _ema(close, fast_period)
    ema_slow = _ema(close, slow_period)

    # MACD line = Fast EMA - Slow EMA
    macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]

    # Signal line = 9-period EMA of MACD line
    signal_line = _ema(macd_line, signal_period)

    # Histogram = MACD - Signal
    histogram = [m - s if m is not None and s is not None else None for m, s in zip(macd_line, signal_line)]

    return {
        "macd": [round(v, 4) if v is not None else None for v in macd_line],
        "signal": [round(v, 4) if v is not None else None for v in signal_line],
        "histogram": [round(v, 4) if v is not None else None for v in histogram],
    }


def _ema(data: list[float], period: int) -> list[Optional[float]]:
    """Calculate Exponential Moving Average."""
    if len(data) < period:
        return [None] * len(data)

    result = [None] * (period - 1)
    multiplier = 2 / (period + 1)

    # Start with SMA for first EMA value
    sma = sum(data[:period]) / period
    result.append(round(sma, 4))

    for i in range(period, len(data)):
        ema = (data[i] - result[-1]) * multiplier + result[-1]
        result.append(round(ema, 4))

    return result


def calculate_rsi(close: list[float], period: int = 14) -> list[Optional[float]]:
    """
    Calculate RSI (Relative Strength Index).

    Args:
        close: List of closing prices
        period: RSI period (default 14)

    Returns:
        List of RSI values (0-100)
    """
    if len(close) < period + 1:
        return [None] * len(close)

    # Calculate price changes
    deltas = [close[i] - close[i - 1] for i in range(1, len(close))]

    # Separate gains and losses
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]

    result: list[Optional[float]] = [None] * period

    # First average (simple moving average)
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    if avg_loss == 0:
        result.append(100.0)
    else:
        rs = avg_gain / avg_loss
        result.append(round(100 - 100 / (1 + rs), 2))

    # Subsequent values (Wilder's smoothing)
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            result.append(100.0)
        else:
            rs = avg_gain / avg_loss
            result.append(round(100 - 100 / (1 + rs), 2))

    return result


def calculate_bollinger_bands(
    close: list[float],
    period: int = 20,
    std_dev: float = 2.0,
) -> dict:
    """
    Calculate Bollinger Bands.

    Args:
        close: List of closing prices
        period: Moving average period (default 20)
        std_dev: Number of standard deviations (default 2.0)

    Returns:
        Dict with 'upper', 'middle', 'lower' lists
    """
    if len(close) < period:
        return {"upper": [None] * len(close), "middle": [None] * len(close), "lower": [None] * len(close)}

    middle = calculate_ma(close, period)

    upper = []
    lower = []

    for i in range(len(close)):
        if i < period - 1:
            upper.append(None)
            lower.append(None)
        else:
            slice_data = close[i - period + 1 : i + 1]
            std = np.std(slice_data)
            m = middle[i]
            if m is not None:
                upper.append(round(m + std_dev * std, 4))
                lower.append(round(m - std_dev * std, 4))
            else:
                upper.append(None)
                lower.append(None)

    return {"upper": upper, "middle": middle, "lower": lower}


def calculate_all_indicators(
    dates: list[str],
    open_prices: list[float],
    high: list[float],
    low: list[float],
    close: list[float],
    volume: list[int],
) -> dict:
    """
    Calculate all technical indicators for OHLCV data.

    Args:
        dates: List of date strings
        open_prices: List of opening prices
        high: List of high prices
        low: List of low prices
        close: List of closing prices
        volume: List of volumes

    Returns:
        Dict containing all indicators
    """
    logger.info("Calculating indicators for %d data points", len(close))

    # Moving Averages
    ma5 = calculate_ma(close, 5)
    ma10 = calculate_ma(close, 10)
    ma20 = calculate_ma(close, 20)
    ma60 = calculate_ma(close, 60)

    # MACD
    macd = calculate_macd(close, fast_period=12, slow_period=26, signal_period=9)

    # RSI
    rsi = calculate_rsi(close, period=14)

    # Bollinger Bands
    bb = calculate_bollinger_bands(close, period=20, std_dev=2.0)

    return {
        "dates": dates,
        "open": open_prices,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "ma5": ma5,
        "ma10": ma10,
        "ma20": ma20,
        "ma60": ma60,
        "macd": macd["macd"],
        "macd_signal": macd["signal"],
        "macd_histogram": macd["histogram"],
        "rsi": rsi,
        "bb_upper": bb["upper"],
        "bb_middle": bb["middle"],
        "bb_lower": bb["lower"],
    }


def indicators_from_dict(data: dict) -> dict:
    """
    Calculate indicators from a dictionary with OHLCV data.
    Compatible with yfinance/collector data format.

    Args:
        data: Dict with 'dates/open/high/low/close/volume' keys

    Returns:
        Dict with all calculated indicators
    """
    return calculate_all_indicators(
        dates=data["dates"],
        open_prices=data["open"],
        high=data["high"],
        low=data["low"],
        close=data["close"],
        volume=data["volume"],
    )
