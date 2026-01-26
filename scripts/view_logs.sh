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
echo "5. Search for invitation/notification sending"
echo "6. Search for private game events"
echo "7. Search for shuffled options / answer checking"
echo "8. Search for specific text"
echo ""

read -p "Enter choice [1-8]: " choice

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
        echo "=== Processing user_shared ==="
        grep -i "Processing user_shared\|Received user_shared\|user_shared\|Extracted selected_user_id" "$LOG_FILE" | tail -n 50
        ;;
    5)
        echo "Searching for invitation/notification sending..."
        echo "=== Attempting to send invitation ==="
        grep -i "Attempting to send invitation\|Successfully sent invitation\|Failed to send notification\|send_message" "$LOG_FILE" | tail -n 50
        echo ""
        echo "=== Full context around invitation attempts ==="
        grep -B 5 -A 5 -i "Attempting to send invitation\|Failed to send notification" "$LOG_FILE" | tail -n 100
        ;;
    6)
        echo "Searching for private game events..."
        grep -i "private game\|create_private_game\|handle_private_game" "$LOG_FILE" | tail -n 50
        ;;
    7)
        echo "Searching for shuffled options and answer checking..."
        echo "=== Shuffling and answer checks ==="
        grep -i "shuffl\|Answer is\|Using.*correct option\|Answer check" "$LOG_FILE" | tail -n 100
        echo ""
        echo "=== Full context around answer checks ==="
        grep -B 3 -A 3 -i "Answer is\|Using.*correct option" "$LOG_FILE" | tail -n 150
        ;;
    8)
        read -p "Enter search text: " search_text
        echo "Searching for: $search_text"
        grep -i "$search_text" "$LOG_FILE" | tail -n 50
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac
