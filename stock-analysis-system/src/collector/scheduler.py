"""
Scheduler for periodic stock data updates.

Uses APScheduler to fetch data daily after market close.
"""

import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def create_daily_update_job(fetch_func, symbols: list[str], hour: int = 18, minute: int = 30):
    """
    Create a daily job to update stock data.

    Args:
        fetch_func: Function to call for fetching data
        symbols: List of stock symbols to update
        hour: Hour to run (default 18:30 after market close)
        minute: Minute to run
    """
    def job():
        logger.info("Running scheduled data update for %d symbols", len(symbols))
        for symbol in symbols:
            try:
                fetch_func(symbol)
                logger.info("Updated %s", symbol)
            except Exception as e:
                logger.error("Failed to update %s: %s", symbol, e)

    trigger = CronTrigger(hour=hour, minute=minute)
    scheduler.add_job(job, trigger, id="daily_stock_update", replace_existing=True)
    logger.info("Scheduled daily update at %02d:%02d for symbols: %s", hour, minute, symbols)


def start_scheduler():
    """Start the background scheduler."""
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started")


def stop_scheduler():
    """Stop the background scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")
