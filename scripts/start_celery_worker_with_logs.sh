#!/bin/bash
# Script to start Celery worker with logging to file

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment
source venv/bin/activate

# Create logs directory if it doesn't exist
mkdir -p logs

# Start Celery worker with logging to file
echo "Starting Celery worker with logging to logs/celery_worker.log"
echo "Press Ctrl+C to stop"

celery -A tasks.celery_app worker \
    --loglevel=info \
    --logfile=logs/celery_worker.log \
    --pidfile=logs/celery_worker.pid
