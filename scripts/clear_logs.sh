#!/bin/bash
# Script to clear log files

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_DIR/logs/trivia_bot.log"
CELERY_WORKER_LOG="$PROJECT_DIR/logs/celery_worker.log"
CELERY_BEAT_LOG="$PROJECT_DIR/logs/celery_beat.log"

echo "=== Trivia Bot Logs Cleaner ==="
echo ""
echo "This will clear the following log files:"
echo "  - $LOG_FILE"
echo "  - $CELERY_WORKER_LOG (if exists)"
echo "  - $CELERY_BEAT_LOG (if exists)"
echo ""
read -p "Are you sure you want to clear all logs? [y/N]: " confirm

if [[ "$confirm" =~ ^[Yy]$ ]]; then
    # Clear main bot log
    if [ -f "$LOG_FILE" ]; then
        > "$LOG_FILE"
        echo "✅ Cleared: $LOG_FILE"
    else
        echo "⚠️  Log file not found: $LOG_FILE"
    fi
    
    # Clear Celery worker log
    if [ -f "$CELERY_WORKER_LOG" ]; then
        > "$CELERY_WORKER_LOG"
        echo "✅ Cleared: $CELERY_WORKER_LOG"
    else
        echo "ℹ️  Celery worker log not found (may not exist): $CELERY_WORKER_LOG"
    fi
    
    # Clear Celery beat log
    if [ -f "$CELERY_BEAT_LOG" ]; then
        > "$CELERY_BEAT_LOG"
        echo "✅ Cleared: $CELERY_BEAT_LOG"
    else
        echo "ℹ️  Celery beat log not found (may not exist): $CELERY_BEAT_LOG"
    fi
    
    echo ""
    echo "✅ All log files cleared!"
    echo ""
    echo "You can now test the bot and check fresh logs using:"
    echo "  bash scripts/view_logs.sh"
else
    echo "❌ Cancelled. Logs were not cleared."
    exit 0
fi
