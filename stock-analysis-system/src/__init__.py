"""Stock Analysis System - Main Package."""

from src.collector.fetcher import (
    DatabaseManager,
    fetch_and_save,
    fetch_stock_data,
    get_stock_info,
)
from src.analyzer.indicators import calculate_all_indicators, indicators_from_dict
from src.analyzer.trends import analyze_trend, get_trading_signal
from src.visualizer.charts import create_candlestick_chart, save_chart_html, chart_from_indicators

__version__ = "1.0.0"

__all__ = [
    # Collector
    "DatabaseManager",
    "fetch_and_save",
    "fetch_stock_data",
    "get_stock_info",
    # Analyzer
    "calculate_all_indicators",
    "indicators_from_dict",
    "analyze_trend",
    "get_trading_signal",
    # Visualizer
    "create_candlestick_chart",
    "save_chart_html",
    "chart_from_indicators",
]
