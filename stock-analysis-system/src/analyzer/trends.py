"""
Trend analysis and trading signals.

Based on MA crossovers and RSI overbought/oversold levels.
"""

import logging
from typing import Optional

from src.analyzer.indicators import calculate_all_indicators

logger = logging.getLogger(__name__)


def analyze_trend(
    dates: list[str],
    open_prices: list[float],
    high: list[float],
    low: list[float],
    close: list[float],
    volume: list[int],
) -> dict:
    """
    Analyze trend based on technical indicators.

    Args:
        dates: List of date strings
        open_prices: List of opening prices
        high: List of high prices
        low: List of low prices
        close: List of closing prices
        volume: List of volumes

    Returns:
        Dict with trend analysis and signals
    """
    indicators = calculate_all_indicators(dates, open_prices, high, low, close, volume)

    ma5 = indicators["ma5"]
    ma10 = indicators["ma10"]
    ma20 = indicators["ma20"]
    ma60 = indicators["ma60"]
    rsi = indicators["rsi"]
    macd_hist = indicators["macd_histogram"]

    # Get latest values (non-None)
    latest_ma5 = _last_valid(ma5)
    latest_ma10 = _last_valid(ma10)
    latest_ma20 = _last_valid(ma20)
    latest_ma60 = _last_valid(ma60)
    latest_rsi = _last_valid(rsi)
    latest_macd_hist = _last_valid(macd_hist)

    # Trend determination
    trend = _determine_trend(ma5, ma10, ma20, ma60)

    # RSI analysis
    rsi_signal = _analyze_rsi(latest_rsi)

    # MACD analysis
    macd_signal = _analyze_macd(latest_macd_hist)

    # Golden/Death cross detection
    cross_signal = _detect_cross(ma5, ma10, ma20)

    # Overall signal
    signal = _generate_signal(trend, rsi_signal, macd_signal, cross_signal)

    return {
        "trend": trend,
        "rsi": round(latest_rsi, 2) if latest_rsi is not None else None,
        "rsi_signal": rsi_signal,
        "macd_histogram": round(latest_macd_hist, 4) if latest_macd_hist is not None else None,
        "macd_signal": macd_signal,
        "ma5": round(latest_ma5, 2) if latest_ma5 is not None else None,
        "ma10": round(latest_ma10, 2) if latest_ma10 is not None else None,
        "ma20": round(latest_ma20, 2) if latest_ma20 is not None else None,
        "ma60": round(latest_ma60, 2) if latest_ma60 is not None else None,
        "cross": cross_signal,
        "signal": signal,
        "signal_description": _signal_description(signal),
    }


def _last_valid(lst: list) -> Optional[float]:
    """Get the last non-None value from a list."""
    for v in reversed(lst):
        if v is not None:
            return v
    return None


def _determine_trend(ma5: list, ma10: list, ma20: list, ma60: list) -> str:
    """Determine overall trend based on moving averages."""
    latest_ma5 = _last_valid(ma5)
    latest_ma10 = _last_valid(ma10)
    latest_ma20 = _last_valid(ma20)
    latest_ma60 = _last_valid(ma60)

    if None in (latest_ma5, latest_ma10, latest_ma20, latest_ma60):
        return "unknown"

    # Strong uptrend: price > all MAs and MAs ascending
    if latest_ma5 > latest_ma10 > latest_ma20 > latest_ma60:
        return "strong_uptrend"
    # Uptrend: short MA above long MA
    elif latest_ma5 > latest_ma10 > latest_ma20:
        return "uptrend"
    # Strong downtrend: price below all MAs and MAs descending
    elif latest_ma5 < latest_ma10 < latest_ma20 < latest_ma60:
        return "strong_downtrend"
    # Downtrend: short MA below long MA
    elif latest_ma5 < latest_ma10 < latest_ma20:
        return "downtrend"
    # Sideways: MAs mixed
    else:
        return "sideways"


def _analyze_rsi(rsi: Optional[float]) -> str:
    """Analyze RSI level."""
    if rsi is None:
        return "unknown"
    if rsi >= 80:
        return "overbought"
    elif rsi >= 70:
        return "neutral_high"
    elif rsi <= 20:
        return "oversold"
    elif rsi <= 30:
        return "neutral_low"
    else:
        return "neutral"


def _analyze_macd(histogram: Optional[float]) -> str:
    """Analyze MACD histogram."""
    if histogram is None:
        return "unknown"
    if histogram > 0:
        return "bullish"
    elif histogram < 0:
        return "bearish"
    else:
        return "neutral"


def _detect_cross(ma5: list, ma10: list, ma20: list) -> Optional[dict]:
    """Detect MA crossover signals in recent bars."""
    if len(ma5) < 3 or len(ma10) < 3 or len(ma20) < 3:
        return None

    # Check last 3 bars for crossovers
    for i in range(len(ma5) - 1, max(len(ma5) - 4, -1), -1):
        ma5_prev, ma5_curr = ma5[i - 1], ma5[i]
        ma10_prev, ma10_curr = ma10[i - 1], ma10[i]
        ma20_prev, ma20_curr = ma20[i - 1], ma20[i]

        if None in (ma5_prev, ma5_curr, ma10_prev, ma10_curr, ma20_prev, ma20_curr):
            continue

        # Golden cross (MA5 crosses above MA10 and MA20)
        if ma5_prev <= ma10_prev and ma5_curr > ma10_curr and ma5_curr > ma20_curr:
            return {"type": "golden_cross", "date": None, "description": "MA5 crossed above MA10 and MA20 - Bullish signal"}

        # Death cross (MA5 crosses below MA10 and MA20)
        if ma5_prev >= ma10_prev and ma5_curr < ma10_curr and ma5_curr < ma20_curr:
            return {"type": "death_cross", "date": None, "description": "MA5 crossed below MA10 and MA20 - Bearish signal"}

    return None


def _generate_signal(trend: str, rsi_signal: str, macd_signal: str, cross: Optional[dict]) -> str:
    """Generate overall trading signal."""
    # Cross takes priority
    if cross is not None:
        if cross["type"] == "golden_cross":
            return "buy"
        elif cross["type"] == "death_cross":
            return "sell"

    # Strong trend signals
    if trend == "strong_uptrend" and macd_signal == "bullish" and rsi_signal not in ("overbought",):
        return "strong_buy"
    if trend == "strong_downtrend" and macd_signal == "bearish" and rsi_signal not in ("oversold",):
        return "strong_sell"

    # Normal signals
    if trend in ("strong_uptrend", "uptrend") and macd_signal == "bullish":
        if rsi_signal == "overbought":
            return "hold"  # Overbought despite uptrend
        return "buy"

    if trend in ("strong_downtrend", "downtrend") and macd_signal == "bearish":
        if rsi_signal == "oversold":
            return "hold"  # Oversold despite downtrend
        return "sell"

    # RSI extremes
    if rsi_signal == "oversold":
        return "buy"
    if rsi_signal == "overbought":
        return "sell"

    return "hold"


def _signal_description(signal: str) -> str:
    """Get human-readable description of signal."""
    descriptions = {
        "strong_buy": "强烈买入信号 - 强劲上升趋势，MACD看涨，RSI未超买",
        "buy": "买入信号 - 上升趋势，MACD看涨",
        "hold": "持有/观望 - 信号不明确或存在矛盾",
        "sell": "卖出信号 - 下降趋势，MACD看跌",
        "strong_sell": "强烈卖出信号 - 强劲下降趋势，MACD看跌，RSI未超卖",
    }
    return descriptions.get(signal, "未知信号")


def get_trading_signal(data: dict) -> dict:
    """
    Get trading signal from raw OHLCV data.

    Args:
        data: Dict with 'dates/open/high/low/close/volume' keys

    Returns:
        Dict with trend analysis results
    """
    return analyze_trend(
        dates=data["dates"],
        open_prices=data["open"],
        high=data["high"],
        low=data["low"],
        close=data["close"],
        volume=data["volume"],
    )
