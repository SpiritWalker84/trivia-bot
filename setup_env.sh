#!/bin/bash

# Quick .env setup script for Ubuntu server
# Creates .env file with correct database credentials

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Default database credentials (matching setup.sh and prepare_environment.sh)
DB_NAME="trivia_bot"
DB_USER="trivia_user"
DB_PASSWORD="trivia_password"

print_info "Setting up .env file..."

# Check if .env already exists
if [ -f "$SCRIPT_DIR/.env" ]; then
    print_warning ".env file already exists"
    read -p "Overwrite existing .env file? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Keeping existing .env file"
        exit 0
    fi
    print_info "Backing up existing .env to .env.backup"
    cp "$SCRIPT_DIR/.env" "$SCRIPT_DIR/.env.backup"
fi

# Create .env file
cat > "$SCRIPT_DIR/.env" <<EOF
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_ADMIN_IDS=

# Database Configuration
# Default credentials created by setup.sh and prepare_environment.sh
DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20

# Redis Configuration
REDIS_URL=redis://localhost:6379/0
REDIS_CACHE_TTL=300

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# Application Settings
MAX_ACTIVE_GAMES=500
MAX_QUESTIONS_IN_DB=50000
POOL_CHECK_INTERVAL=300
VOTE_DURATION=45
QUESTION_TIME_LIMIT=20
TIE_BREAK_TIME_LIMIT=20

# Game Settings
ROUNDS_PER_GAME=10
QUESTIONS_PER_ROUND=10
PLAYERS_PER_GAME=10
MIN_PLAYERS_FOR_QUICK_START=10
MIN_PLAYERS_FOR_VOTE=3

# Bot Settings
BOT_MIN_RESPONSE_DELAY=3
BOT_MAX_RESPONSE_DELAY=15
BOT_NOVICE_ACCURACY=0.4
BOT_AMATEUR_ACCURACY=0.6
BOT_EXPERT_ACCURACY=0.85

# Rating System
RATING_WINNER_BONUS=20
RATING_SECOND_BONUS=12
RATING_THIRD_BONUS=8
RATING_4_5_BONUS=4
RATING_6_8_BONUS=0
RATING_9_10_PENALTY=-4

# Retry Settings
TELEGRAM_RETRY_ATTEMPTS=5
TELEGRAM_RETRY_BACKOFF_BASE=1.0
DATABASE_RETRY_ATTEMPTS=3
DATABASE_RETRY_DELAY=1.0

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/trivia_bot.log
LOG_FORMAT=%(asctime)s - %(name)s - %(levelname)s - %(message)s

# Environment
ENVIRONMENT=development
DEBUG=true

# Cache TTLs (in seconds)
CACHE_USER_PROFILE_TTL=600
CACHE_RATING_TOP100_TTL=600
CACHE_THEMES_TTL=86400
CACHE_BOT_SETTINGS_TTL=86400
EOF

print_success ".env file created at $SCRIPT_DIR/.env"
echo ""
print_warning "IMPORTANT: You must edit .env file and set:"
print_warning "  - TELEGRAM_BOT_TOKEN (required!)"
print_warning ""
print_info "To edit .env file:"
echo "  nano $SCRIPT_DIR/.env"
echo ""
print_info "Database credentials (already set):"
echo "  Database: $DB_NAME"
echo "  User: $DB_USER"
echo "  Password: $DB_PASSWORD"
echo "  Connection: postgresql://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME"
echo ""
