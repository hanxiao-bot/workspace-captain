#!/bin/bash
set -e

echo "Starting Stock Analysis System..."

# Set Python path
export PYTHONPATH=/app:$PYTHONPATH

# Initialize database if not exists
echo "Initializing database..."
python -c "
import os
import sys
sys.path.insert(0, '/app')
from src.collector.fetcher import DatabaseManager
db = DatabaseManager()
db.init_db()
print('Database initialized successfully.')
"

# Start FastAPI with uvicorn
echo "Starting API server..."
exec uvicorn src.api.main:app \
    --host "${STOCK_API_HOST:-0.0.0.0}" \
    --port "${STOCK_API_PORT:-8000}" \
    --log-level "${LOG_LEVEL:-info}"
