"""
Stock data fetcher using yfinance.

Fetches OHLCV data and stores it in SQLite database.
"""

import logging
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

import yfinance as yf

logger = logging.getLogger(__name__)

DATABASE_PATH = os.getenv("DATABASE_PATH", "/app/data/stocks.db")


class DatabaseManager:
    """Manages SQLite database for stock data."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DATABASE_PATH
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    def init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Stocks tracking table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tracked_stocks (
                    symbol TEXT PRIMARY KEY,
                    name TEXT,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Price history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    date DATE NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume INTEGER,
                    adjusted_close REAL,
                    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, date)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_price_history_symbol_date
                ON price_history(symbol, date)
            """)

            conn.commit()
        logger.info("Database initialized at %s", self.db_path)

    def get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        return sqlite3.connect(self.db_path)

    def add_tracked_stock(self, symbol: str, name: Optional[str] = None) -> bool:
        """Add a stock to tracking list."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR IGNORE INTO tracked_stocks (symbol, name) VALUES (?, ?)",
                    (symbol.upper(), name or symbol.upper()),
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error("Failed to add tracked stock %s: %s", symbol, e)
            return False

    def get_tracked_stocks(self) -> list[dict]:
        """Get all tracked stocks."""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tracked_stocks ORDER BY added_at DESC")
            return [dict(row) for row in cursor.fetchall()]

    def save_price_data(self, symbol: str, data: dict) -> int:
        """Save price data to database. Returns number of rows inserted."""
        if not data or "dates" not in data:
            return 0

        rows = 0
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for i, date_str in enumerate(data["dates"]):
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO price_history
                    (symbol, date, open, high, low, close, volume, adjusted_close)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        symbol.upper(),
                        date_str,
                        data["open"][i],
                        data["high"][i],
                        data["low"][i],
                        data["close"][i],
                        int(data["volume"][i]),
                        data.get("adj_close", data["close"])[i],
                    ),
                )
                rows += 1
            conn.commit()
        return rows

    def get_price_history(
        self, symbol: str, days: int = 30
    ) -> Optional[dict]:
        """Get price history for a symbol."""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT date, open, high, low, close, volume, adjusted_close
                FROM price_history
                WHERE symbol = ?
                ORDER BY date DESC
                LIMIT ?
                """,
                (symbol.upper(), days),
            )
            rows = cursor.fetchall()
            if not rows:
                return None

            # Reverse to get chronological order
            rows = list(reversed(rows))
            return {
                "dates": [r["date"] for r in rows],
                "open": [r["open"] for r in rows],
                "high": [r["high"] for r in rows],
                "low": [r["low"] for r in rows],
                "close": [r["close"] for r in rows],
                "volume": [r["volume"] for r in rows],
                "adj_close": [r["adjusted_close"] for r in rows],
            }


def fetch_stock_data(
    symbol: str,
    period: str = "1y",
    interval: str = "1d",
) -> Optional[dict]:
    """
    Fetch stock data from yfinance.

    Args:
        symbol: Stock ticker symbol
        period: Data period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
        interval: Data interval (1m, 2m, 5m, 15m, 30m, 60m, 1d, 1wk, 1mo)

    Returns:
        Dictionary with OHLCV data or None on failure.
    """
    try:
        logger.info("Fetching data for %s (period=%s, interval=%s)", symbol, period, interval)
        ticker = yf.Ticker(symbol.upper())
        df = ticker.history(period=period, interval=interval)

        if df.empty:
            logger.warning("No data returned for %s", symbol)
            return None

        df = df.reset_index()
        if "Datetime" in df.columns:
            df["Date"] = df["Datetime"]
        
        # Handle timezone-aware datetimes
        if hasattr(df["Date"].dtype, 'tz') and df["Date"].dtype.tz is not None:
            df["Date"] = df["Date"].dt.tz_localize(None)

        return {
            "dates": df["Date"].dt.strftime("%Y-%m-%d").tolist(),
            "open": df["Open"].tolist(),
            "high": df["High"].tolist(),
            "low": df["Low"].tolist(),
            "close": df["Close"].tolist(),
            "volume": df["Volume"].tolist(),
            "adj_close": df["Close"].tolist(),  # yfinance history includes adj close
        }
    except Exception as e:
        logger.error("Failed to fetch data for %s: %s", symbol, e)
        return None


def fetch_and_save(
    symbol: str,
    period: str = "1y",
    interval: str = "1d",
    db_path: Optional[str] = None,
) -> bool:
    """
    Fetch stock data and save to database.

    Args:
        symbol: Stock ticker symbol
        period: Data period
        interval: Data interval
        db_path: Optional database path override

    Returns:
        True if successful, False otherwise.
    """
    data = fetch_stock_data(symbol, period, interval)
    if data is None:
        return False

    db = DatabaseManager(db_path)
    rows = db.save_price_data(symbol.upper(), data)
    logger.info("Saved %d rows for %s", rows, symbol)
    return True


def get_stock_info(symbol: str) -> Optional[dict]:
    """
    Get basic stock information.

    Args:
        symbol: Stock ticker symbol

    Returns:
        Dictionary with stock info or None on failure.
    """
    try:
        ticker = yf.Ticker(symbol.upper())
        info = ticker.info
        return {
            "symbol": symbol.upper(),
            "name": info.get("shortName", info.get("longName", symbol.upper())),
            "current_price": info.get("currentPrice", info.get("regularMarketPrice")),
            "market_cap": info.get("marketCap"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "description": info.get("longBusinessSummary", "")[:500],
        }
    except Exception as e:
        logger.error("Failed to get info for %s: %s", symbol, e)
        return None
