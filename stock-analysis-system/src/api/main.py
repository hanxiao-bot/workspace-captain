"""
Stock Analysis API.

FastAPI application providing stock data, indicators, charts, and trading signals.
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from src.analyzer.indicators import calculate_all_indicators
from src.analyzer.trends import analyze_trend
from src.collector.fetcher import DatabaseManager, fetch_and_save, fetch_stock_data, get_stock_info
from src.visualizer.charts import chart_from_indicators

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Environment
API_PORT = int(os.getenv("STOCK_API_PORT", "8000"))
DATABASE_PATH = os.getenv("DATABASE_PATH", "/app/data/stocks.db")
TEMPLATES_DIR = os.getenv("TEMPLATES_DIR", "/app/templates")

# Global templates instance
templates: Optional[Jinja2Templates] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    global templates
    logger.info("Starting Stock Analysis API...")
    # Initialize database
    db = DatabaseManager(DATABASE_PATH)
    db.init_db()
    logger.info("Database initialized at %s", DATABASE_PATH)
    # Initialize templates
    templates = Jinja2Templates(directory=TEMPLATES_DIR)
    logger.info("Templates loaded from %s", TEMPLATES_DIR)
    yield
    logger.info("Shutting down Stock Analysis API...")


app = FastAPI(
    title="Stock Analysis API",
    description="Stock data collection, analysis, and visualization API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request/Response Models ---

class AddStockRequest(BaseModel):
    symbol: str


class StockInfo(BaseModel):
    symbol: str
    name: Optional[str] = None
    current_price: Optional[float] = None
    market_cap: Optional[int] = None
    sector: Optional[str] = None
    industry: Optional[str] = None


class TrackedStock(BaseModel):
    symbol: str
    name: Optional[str] = None
    added_at: Optional[str] = None


# --- Health Check ---

@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "stock-analysis-api"}


# --- Stock Endpoints ---

@app.get("/stock/{symbol}", tags=["Stock"])
async def get_stock(symbol: str):
    """
    Get stock basic information.

    Fetches latest info from yfinance (name, price, PE, etc.)
    """
    symbol = symbol.upper()
    info = get_stock_info(symbol)
    if info is None:
        raise HTTPException(status_code=404, detail=f"Could not fetch info for {symbol}")
    return info


@app.get("/stock/{symbol}/history", tags=["Stock"])
async def get_stock_history(symbol: str, days: int = Query(default=30, ge=1, le=3650)):
    """
    Get K-line historical data.

    Returns OHLCV data from local database.
    """
    symbol = symbol.upper()
    db = DatabaseManager(DATABASE_PATH)
    data = db.get_price_history(symbol, days=days)
    if data is None:
        raise HTTPException(status_code=404, detail=f"No data found for {symbol}")
    return {
        "symbol": symbol,
        "days": days,
        "dates": data["dates"],
        "open": data["open"],
        "high": data["high"],
        "low": data["low"],
        "close": data["close"],
        "volume": data["volume"],
    }


@app.get("/stock/{symbol}/indicators", tags=["Stock"])
async def get_stock_indicators(symbol: str, days: int = Query(default=60, ge=10, le=3650)):
    """
    Get technical indicators.

    Calculates MA, MACD, RSI, Bollinger Bands from stored data.
    """
    symbol = symbol.upper()
    db = DatabaseManager(DATABASE_PATH)
    data = db.get_price_history(symbol, days=days)
    if data is None:
        raise HTTPException(status_code=404, detail=f"No data found for {symbol}")

    indicators = calculate_all_indicators(
        dates=data["dates"],
        open_prices=data["open"],
        high=data["high"],
        low=data["low"],
        close=data["close"],
        volume=data["volume"],
    )

    # Add trend analysis
    trend = analyze_trend(
        dates=data["dates"],
        open_prices=data["open"],
        high=data["high"],
        low=data["low"],
        close=data["close"],
        volume=data["volume"],
    )

    return {
        "symbol": symbol,
        "indicators": indicators,
        "trend": trend,
    }


@app.get("/stock/{symbol}/chart", tags=["Stock"], response_class=HTMLResponse)
async def get_stock_chart(
    symbol: str,
    days: int = Query(default=30, ge=5, le=3650),
    show_macd: bool = Query(default=False),
    show_rsi: bool = Query(default=False),
):
    """
    Get interactive Plotly chart (HTML).

    Returns K-line chart with optional MACD and RSI subplots.
    """
    symbol = symbol.upper()
    db = DatabaseManager(DATABASE_PATH)
    data = db.get_price_history(symbol, days=days)
    if data is None:
        raise HTTPException(status_code=404, detail=f"No data found for {symbol}")

    indicators = calculate_all_indicators(
        dates=data["dates"],
        open_prices=data["open"],
        high=data["high"],
        low=data["low"],
        close=data["close"],
        volume=data["volume"],
    )
    indicators["symbol"] = symbol

    html = chart_from_indicators(indicators, symbol=symbol)
    return html


@app.post("/stock/{symbol}/fetch", tags=["Stock"])
async def fetch_stock_data_api(symbol: str):
    """
    Manually trigger data fetch for a stock.

    Fetches latest data from yfinance and saves to database.
    """
    symbol = symbol.upper()
    logger.info("Manual fetch triggered for %s", symbol)
    success = fetch_and_save(symbol, period="1y", interval="1d")
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to fetch data for {symbol}")

    # Add to tracked stocks if not already
    db = DatabaseManager(DATABASE_PATH)
    db.add_tracked_stock(symbol)

    return {"status": "success", "symbol": symbol, "message": "Data fetched and saved"}


# --- Tracked Stocks Endpoints ---

@app.get("/stocks", tags=["Stocks"])
async def list_tracked_stocks():
    """
    List all tracked stocks.
    """
    db = DatabaseManager(DATABASE_PATH)
    stocks = db.get_tracked_stocks()
    return {"stocks": stocks, "count": len(stocks)}


@app.post("/stocks", tags=["Stocks"])
async def add_tracked_stock(request: AddStockRequest):
    """
    Add a stock to the tracked list.
    """
    symbol = request.symbol.upper()
    db = DatabaseManager(DATABASE_PATH)

    # First try to fetch data
    success = fetch_and_save(symbol, period="1y", interval="1d")
    if not success:
        logger.warning("Could not fetch data for %s, adding to watchlist only", symbol)

    # Add to tracked list
    info = get_stock_info(symbol)
    name = info.get("name") if info else symbol
    db.add_tracked_stock(symbol, name=name)

    return {"status": "success", "symbol": symbol, "name": name}


# --- Dashboard Route ---
def _get_latest_value(lst: list) -> Optional[float]:
    """Get last non-None value from a list."""
    if not lst:
        return None
    for v in reversed(lst):
        if v is not None:
            return round(v, 4) if v else v
    return None


def _format_signal_badge(signal: str) -> dict:
    """Format signal with color and label."""
    mapping = {
        "strong_buy":  {"label": "强烈买入", "badge": "bg-success"},
        "buy":          {"label": "买入",     "badge": "bg-success"},
        "hold":         {"label": "持有",     "badge": "bg-warning text-dark"},
        "sell":         {"label": "卖出",     "badge": "bg-danger"},
        "strong_sell":  {"label": "强烈卖出","badge": "bg-danger"},
    }
    return mapping.get(signal, {"label": signal, "badge": "bg-secondary"})


@app.get("/dashboard", tags=["Dashboard"], response_class=HTMLResponse)
async def dashboard_home(
    request: Request,
    symbol: str = Query(default="AAPL", description="Stock symbol"),
    days: int = Query(default=30, ge=5, le=365),
):
    """
    Render the main dashboard page for a stock symbol.
    Data is fetched directly from local modules (no HTTP calls).
    """
    symbol = symbol.upper().strip()

    db = DatabaseManager(DATABASE_PATH)
    data = db.get_price_history(symbol, days=days)
    if data is None:
        raise HTTPException(status_code=404, detail=f"No data found for {symbol}")

    # Calculate indicators locally
    indicators = calculate_all_indicators(
        dates=data["dates"],
        open_prices=data["open"],
        high=data["high"],
        low=data["low"],
        close=data["close"],
        volume=data["volume"],
    )

    # Analyze trend locally
    trend = analyze_trend(
        dates=data["dates"],
        open_prices=data["open"],
        high=data["high"],
        low=data["low"],
        close=data["close"],
        volume=data["volume"],
    )

    # Build chart HTML
    chart_data = dict(data)
    chart_data["symbol"] = symbol
    chart_data.update(indicators)
    chart_html = chart_from_indicators(chart_data, symbol=symbol)

    # Extract latest values
    latest = {
        "ma5":      _get_latest_value(indicators.get("ma5", [])),
        "ma10":     _get_latest_value(indicators.get("ma10", [])),
        "ma20":     _get_latest_value(indicators.get("ma20", [])),
        "ma60":     _get_latest_value(indicators.get("ma60", [])),
        "rsi":      _get_latest_value(indicators.get("rsi", [])),
        "macd":     _get_latest_value(indicators.get("macd", [])),
        "macd_sig": _get_latest_value(indicators.get("macd_signal", [])),
        "macd_hist": _get_latest_value(indicators.get("macd_histogram", [])),
        "bb_upper": _get_latest_value(indicators.get("bb_upper", [])),
        "bb_middle": _get_latest_value(indicators.get("bb_middle", [])),
        "bb_lower": _get_latest_value(indicators.get("bb_lower", [])),
        "close":    _get_latest_value(data.get("close", [])),
    }

    # Signal badge
    signal_raw = trend.get("signal", "hold")
    signal_badge = _format_signal_badge(signal_raw)

    # Trend label
    trend_labels = {
        "strong_uptrend":   "强势上升",
        "uptrend":          "上升趋势",
        "sideways":         "横盘整理",
        "downtrend":        "下降趋势",
        "strong_downtrend": "强势下降",
        "unknown":          "未知",
    }
    trend_label = trend_labels.get(trend.get("trend", ""), trend.get("trend", ""))

    # Build OHLCV table rows (last 30 days)
    dates = data.get("dates", [])
    ohlcv_rows = []
    for i in range(max(0, len(dates) - 30), len(dates)):
        ohlcv_rows.append({
            "date":   dates[i],
            "open":   round(data["open"][i], 2)   if i < len(data["open"])   else None,
            "high":   round(data["high"][i], 2)   if i < len(data["high"])   else None,
            "low":    round(data["low"][i], 2)    if i < len(data["low"])    else None,
            "close":  round(data["close"][i], 2)  if i < len(data["close"])  else None,
            "volume": data["volume"][i]           if i < len(data["volume"]) else None,
        })
    ohlcv_rows.reverse()

    if templates is None:
        raise RuntimeError("Templates not initialized")

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "symbol": symbol,
            "days": days,
            "chart_html": chart_html,
            "latest": latest,
            "trend": trend,
            "trend_label": trend_label,
            "signal_badge": signal_badge,
            "ohlcv_rows": ohlcv_rows,
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=API_PORT)
