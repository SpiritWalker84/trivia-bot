#!/bin/bash

# Script to install systemd services for Trivia Bot
# Run this after setup.sh if you want to use systemd

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -d "$SCRIPT_DIR/systemd" ]; then
    echo "Error: systemd directory not found. Please run setup.sh first."
    exit 1
fi

echo "Installing systemd services..."

# Copy service files
sudo cp "$SCRIPT_DIR/systemd"/*.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable services
sudo systemctl enable trivia-bot.service
sudo systemctl enable trivia-bot-celery-worker.service
sudo systemctl enable trivia-bot-celery-beat.service

echo "Services installed and enabled!"
echo ""
echo "To start services:"
echo "  sudo systemctl start trivia-bot trivia-bot-celery-worker trivia-bot-celery-beat"
echo ""
echo "To check status:"
echo "  sudo systemctl status trivia-bot"
echo "  sudo systemctl status trivia-bot-celery-worker"
echo "  sudo systemctl status trivia-bot-celery-beat"
echo ""
echo "To view logs:"
echo "  sudo journalctl -u trivia-bot -f"
echo "  sudo journalctl -u trivia-bot-celery-worker -f"
echo "  sudo journalctl -u trivia-bot-celery-beat -f"
