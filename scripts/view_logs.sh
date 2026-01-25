#!/bin/bash
# Script to view logs easily

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_DIR/logs/trivia_bot.log"

echo "=== Trivia Bot Logs Viewer ==="
echo ""
echo "Choose what to view:"
echo "1. Live bot logs (tail -f)"
echo "2. Last 100 lines"
echo "3. Search for errors"
echo "4. Search for user_shared events"
echo "5. Search for specific text"
echo ""

read -p "Enter choice [1-5]: " choice

case $choice in
    1)
        echo "Showing live logs (Ctrl+C to exit)..."
        tail -f "$LOG_FILE"
        ;;
    2)
        echo "Last 100 lines:"
        tail -n 100 "$LOG_FILE"
        ;;
    3)
        echo "Searching for errors..."
        grep -i error "$LOG_FILE" | tail -n 50
        ;;
    4)
        echo "Searching for user_shared events..."
        grep -i "user_shared\|Processing user_shared\|Received user_shared" "$LOG_FILE" | tail -n 50
        ;;
    5)
        read -p "Enter search text: " search_text
        echo "Searching for: $search_text"
        grep -i "$search_text" "$LOG_FILE" | tail -n 50
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac
