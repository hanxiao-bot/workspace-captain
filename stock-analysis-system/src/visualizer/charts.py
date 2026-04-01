"""
Interactive chart generation using Plotly.

Generates candlestick charts with MA overlays and optional MACD/RSI subplots.
"""

import logging
import os
from typing import Optional

import plotly.graph_objects as go
from plotly.subplots import make_subplots

logger = logging.getLogger(__name__)


def create_candlestick_chart(
    dates: list[str],
    open_prices: list[float],
    high: list[float],
    low: list[float],
    close: list[float],
    volume: list[int],
    symbol: str = "Stock",
    show_ma: bool = True,
    ma5: Optional[list] = None,
    ma10: Optional[list] = None,
    ma20: Optional[list] = None,
    ma60: Optional[list] = None,
    show_macd: bool = False,
    macd: Optional[list] = None,
    macd_signal: Optional[list] = None,
    macd_histogram: Optional[list] = None,
    show_rsi: bool = False,
    rsi: Optional[list] = None,
    width: int = 1200,
    height: int = 800,
) -> str:
    """
    Create an interactive candlestick chart with optional indicators.

    Args:
        dates: List of date strings
        open_prices: List of opening prices
        high: List of high prices
        low: List of low prices
        close: List of closing prices
        volume: List of volumes
        symbol: Stock symbol for title
        show_ma: Whether to show MA lines
        ma5, ma10, ma20, ma60: MA data lists
        show_macd: Whether to show MACD subplot
        macd, macd_signal, macd_histogram: MACD data lists
        show_rsi: Whether to show RSI subplot
        rsi: RSI data list
        width: Chart width in pixels
        height: Chart height in pixels

    Returns:
        HTML string of the chart
    """
    rows = 1
    row_heights = [1.0]
    specs = [[{"type": " candlestick"}]]

    if show_macd:
        rows += 1
        row_heights.append(0.3)
        specs.append([{"type": "bar"}])

    if show_rsi:
        rows += 1
        row_heights.append(0.25)
        specs.append([{"type": "scatter"}])

    fig = make_subplots(
        rows=rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=row_heights,
        specs=specs,
        subplot_titles=([""] if rows > 1 else None),
    )

    # Candlestick chart
    fig.add_trace(
        go.Candlestick(
            x=dates,
            open=open_prices,
            high=high,
            low=low,
            close=close,
            name="OHLC",
            increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350",
        ),
        row=1,
        col=1,
    )

    # Volume bars
    colors = ["#26a69a" if close[i] >= open_prices[i] else "#ef5350" for i in range(len(close))]
    fig.add_trace(
        go.Bar(x=dates, y=volume, name="Volume", marker=dict(color=colors, opacity=0.5), showlegend=False),
        row=1,
        col=1,
    )

    # Moving averages
    if show_ma:
        if ma5:
            fig.add_trace(go.Scatter(x=dates, y=ma5, name="MA5", line=dict(color="#2196F3", width=1.5), connectgaps=False), row=1, col=1)
        if ma10:
            fig.add_trace(go.Scatter(x=dates, y=ma10, name="MA10", line=dict(color="#FF9800", width=1.5), connectgaps=False), row=1, col=1)
        if ma20:
            fig.add_trace(go.Scatter(x=dates, y=ma20, name="MA20", line=dict(color="#9C27B0", width=1.5), connectgaps=False), row=1, col=1)
        if ma60:
            fig.add_trace(go.Scatter(x=dates, y=ma60, name="MA60", line=dict(color="#795548", width=1.5), connectgaps=False), row=1, col=1)

    current_row = 1

    # MACD subplot
    if show_macd:
        current_row += 1
        hist_colors = ["#26a69a" if h >= 0 else "#ef5350" for h in (macd_histogram or [])]
        fig.add_trace(
            go.Bar(x=dates, y=macd_histogram or [], name="MACD Hist", marker=dict(color=hist_colors), showlegend=False),
            row=current_row,
            col=1,
        )
        if macd:
            fig.add_trace(go.Scatter(x=dates, y=macd, name="MACD", line=dict(color="#2196F3"), showlegend=False), row=current_row, col=1)
        if macd_signal:
            fig.add_trace(go.Scatter(x=dates, y=macd_signal, name="Signal", line=dict(color="#FF9800"), showlegend=False), row=current_row, col=1)

    # RSI subplot
    if show_rsi:
        current_row += 1
        fig.add_trace(go.Scatter(x=dates, y=rsi or [], name="RSI", line=dict(color="#9C27B0", width=1.5)), row=current_row, col=1)
        # Overbought/oversold lines
        fig.add_hline(y=70, line_dash="dash", line_color="red", opacity=0.5, row=current_row, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", opacity=0.5, row=current_row, col=1)

    # Update layout
    fig.update_layout(
        title=dict(text=f"{symbol} - K Line Chart", font=dict(size=20), x=0.5),
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        width=width,
        height=height,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=50, r=50, t=80, b=50),
    )

    # Update y-axes
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=1, col=1)
    if show_macd:
        fig.update_yaxes(title_text="MACD", row=current_row if not show_rsi else current_row - 1, col=1)
    if show_rsi:
        fig.update_yaxes(title_text="RSI", row=current_row, col=1, range=[0, 100])

    return fig.to_html(full_html=False, include_plotlyjs="cdn")


def save_chart_html(
    filepath: str,
    dates: list[str],
    open_prices: list[float],
    high: list[float],
    low: list[float],
    close: list[float],
    volume: list[int],
    symbol: str = "Stock",
    show_ma: bool = True,
    ma5: Optional[list] = None,
    ma10: Optional[list] = None,
    ma20: Optional[list] = None,
    ma60: Optional[list] = None,
    show_macd: bool = False,
    macd: Optional[list] = None,
    macd_signal: Optional[list] = None,
    macd_histogram: Optional[list] = None,
    show_rsi: bool = False,
    rsi: Optional[list] = None,
) -> str:
    """
    Save chart to HTML file.

    Returns the filepath saved.
    """
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)

    html = create_candlestick_chart(
        dates=dates,
        open_prices=open_prices,
        high=high,
        low=low,
        close=close,
        volume=volume,
        symbol=symbol,
        show_ma=show_ma,
        ma5=ma5,
        ma10=ma10,
        ma20=ma20,
        ma60=ma60,
        show_macd=show_macd,
        macd=macd,
        macd_signal=macd_signal,
        macd_histogram=macd_histogram,
        show_rsi=show_rsi,
        rsi=rsi,
    )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"<!-- {symbol} Chart -->\n")
        f.write(html)

    logger.info("Chart saved to %s", filepath)
    return filepath


def chart_from_indicators(data: dict, symbol: str = "Stock") -> str:
    """
    Create chart from indicator data dict.

    Args:
        data: Dict with OHLCV + indicator data (from analyzer)
        symbol: Stock symbol

    Returns:
        HTML string
    """
    return create_candlestick_chart(
        dates=data["dates"],
        open_prices=data["open"],
        high=data["high"],
        low=data["low"],
        close=data["close"],
        volume=data["volume"],
        symbol=symbol,
        show_ma=True,
        ma5=data.get("ma5"),
        ma10=data.get("ma10"),
        ma20=data.get("ma20"),
        ma60=data.get("ma60"),
        show_macd=True,
        macd=data.get("macd"),
        macd_signal=data.get("macd_signal"),
        macd_histogram=data.get("macd_histogram"),
        show_rsi=True,
        rsi=data.get("rsi"),
    )
