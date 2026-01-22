#!/bin/bash

# Trivia Bot Setup Script for Ubuntu
# Автоматизирует установку и настройку проекта

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
PYTHON_VERSION="3.12"

# Functions
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

check_command() {
    if command -v "$1" &> /dev/null; then
        return 0
    else
        return 1
    fi
}

# Step 1: Check prerequisites
print_info "Checking prerequisites..."

# Check Python
if ! check_command python3; then
    print_error "Python 3 is not installed. Installing..."
    sudo apt-get update
    sudo apt-get install -y python3 python3-pip python3-venv
fi

PYTHON3_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
print_success "Python $PYTHON3_VERSION found"

# Check PostgreSQL
if ! check_command psql; then
    print_warning "PostgreSQL is not installed. Installing..."
    sudo apt-get update
    sudo apt-get install -y postgresql postgresql-contrib
    sudo systemctl start postgresql
    sudo systemctl enable postgresql
    print_success "PostgreSQL installed and started"
else
    print_success "PostgreSQL found"
    # Ensure PostgreSQL is running
    sudo systemctl start postgresql || true
fi

# Check Redis
if ! check_command redis-cli; then
    print_warning "Redis is not installed. Installing..."
    sudo apt-get update
    sudo apt-get install -y redis-server
    sudo systemctl start redis-server
    sudo systemctl enable redis-server
    print_success "Redis installed and started"
else
    print_success "Redis found"
    # Ensure Redis is running
    sudo systemctl start redis-server || true
fi

# Step 2: Create virtual environment
print_info "Creating virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    print_success "Virtual environment created"
else
    print_warning "Virtual environment already exists"
fi

# Step 3: Activate virtual environment and install dependencies
print_info "Installing Python dependencies..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r requirements.txt
print_success "Dependencies installed"

# Step 4: Setup PostgreSQL database
print_info "Setting up PostgreSQL database..."

# Read database config from .env or use defaults
if [ -f .env ]; then
    source .env
    DB_NAME="${DB_NAME:-trivia_bot}"
    DB_USER="${DB_USER:-trivia_user}"
    DB_PASSWORD="${DB_PASSWORD:-trivia_password}"
else
    print_warning ".env file not found, using default values"
    DB_NAME="trivia_bot"
    DB_USER="trivia_user"
    DB_PASSWORD="trivia_password"
fi

# Create database and user
print_info "Creating PostgreSQL database and user..."
sudo -u postgres psql <<EOF
-- Create user if not exists
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = '$DB_USER') THEN
        CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';
    END IF;
END
\$\$;

-- Create database if not exists
SELECT 'CREATE DATABASE $DB_NAME'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$DB_NAME')\gexec

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
ALTER DATABASE $DB_NAME OWNER TO $DB_USER;
EOF

print_success "PostgreSQL database '$DB_NAME' and user '$DB_USER' created"

# Step 5: Create .env file if it doesn't exist
if [ ! -f .env ]; then
    print_info "Creating .env file from .env.example..."
    if [ -f .env.example ]; then
        cp .env.example .env
        print_warning "Please edit .env file and set your configuration values:"
        print_warning "  - TELEGRAM_BOT_TOKEN"
        print_warning "  - DATABASE_URL (using: postgresql://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME)"
        print_warning "  - REDIS_URL"
        print_warning "  - CELERY_BROKER_URL"
        print_warning "  - CELERY_RESULT_BACKEND"
        
        # Update .env with database credentials
        sed -i "s|postgresql://user:password@localhost:5432/trivia_bot|postgresql://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME|g" .env
    else
        print_error ".env.example not found!"
        exit 1
    fi
else
    print_info ".env file already exists"
fi

# Step 6: Create database tables
print_info "Creating database tables..."
python3 <<EOF
import sys
sys.path.insert(0, '$SCRIPT_DIR')

from database.session import get_db_session
from utils.logging import setup_logging

# Setup logging
setup_logging()

# Create tables
try:
    db = get_db_session()
    db.create_tables()
    print("Database tables created successfully")
except Exception as e:
    print(f"Error creating tables: {e}")
    sys.exit(1)
EOF

print_success "Database tables created"

# Step 7: Create systemd service files (optional)
print_info "Creating systemd service files..."

# Create directory for service files
mkdir -p systemd

# Bot service
cat > systemd/trivia-bot.service <<EOF
[Unit]
Description=Trivia Bot Telegram Bot
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$SCRIPT_DIR
Environment="PATH=$VENV_DIR/bin"
ExecStart=$VENV_DIR/bin/python $SCRIPT_DIR/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Celery worker service
cat > systemd/trivia-bot-celery-worker.service <<EOF
[Unit]
Description=Trivia Bot Celery Worker
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$SCRIPT_DIR
Environment="PATH=$VENV_DIR/bin"
ExecStart=$VENV_DIR/bin/celery -A tasks.celery_app worker --loglevel=info
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Celery beat service
cat > systemd/trivia-bot-celery-beat.service <<EOF
[Unit]
Description=Trivia Bot Celery Beat (Scheduler)
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$SCRIPT_DIR
Environment="PATH=$VENV_DIR/bin"
ExecStart=$VENV_DIR/bin/celery -A tasks.celery_app beat --loglevel=info
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

print_success "Systemd service files created in systemd/ directory"

# Step 8: Create startup script
print_info "Creating startup script..."

cat > start.sh <<'EOF'
#!/bin/bash

# Trivia Bot Startup Script
# Starts bot, Celery worker, and Celery beat

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
LOGS_DIR="$SCRIPT_DIR/logs"

# Create logs directory
mkdir -p "$LOGS_DIR"

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# Check if .env exists
if [ ! -f .env ]; then
    echo "Error: .env file not found. Please create it from .env.example"
    exit 1
fi

# Function to cleanup on exit
cleanup() {
    echo "Stopping services..."
    kill $BOT_PID $CELERY_WORKER_PID $CELERY_BEAT_PID 2>/dev/null || true
    exit
}

trap cleanup SIGINT SIGTERM

# Start Celery worker
echo "Starting Celery worker..."
celery -A tasks.celery_app worker --loglevel=info --logfile="$LOGS_DIR/celery_worker.log" &
CELERY_WORKER_PID=$!

# Start Celery beat
echo "Starting Celery beat..."
celery -A tasks.celery_app beat --loglevel=info --logfile="$LOGS_DIR/celery_beat.log" &
CELERY_BEAT_PID=$!

# Wait a bit for Celery to start
sleep 3

# Start bot
echo "Starting Telegram bot..."
python main.py &
BOT_PID=$!

echo "All services started!"
echo "Bot PID: $BOT_PID"
echo "Celery Worker PID: $CELERY_WORKER_PID"
echo "Celery Beat PID: $CELERY_BEAT_PID"
echo ""
echo "Logs:"
echo "  Bot: $LOGS_DIR/trivia_bot.log"
echo "  Celery Worker: $LOGS_DIR/celery_worker.log"
echo "  Celery Beat: $LOGS_DIR/celery_beat.log"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for all processes
wait
EOF

chmod +x start.sh
print_success "Startup script created (start.sh)"

# Step 9: Create stop script
print_info "Creating stop script..."

cat > stop.sh <<'EOF'
#!/bin/bash

# Trivia Bot Stop Script

echo "Stopping Trivia Bot services..."

# Kill bot process
pkill -f "python.*main.py" || true

# Kill Celery processes
pkill -f "celery.*worker" || true
pkill -f "celery.*beat" || true

echo "All services stopped"
EOF

chmod +x stop.sh
print_success "Stop script created (stop.sh)"

# Summary
echo ""
print_success "=========================================="
print_success "Setup completed successfully!"
print_success "=========================================="
echo ""
print_info "Next steps:"
echo "  1. Edit .env file and set your TELEGRAM_BOT_TOKEN"
echo "  2. Review other configuration in .env"
echo ""
print_info "To start the bot:"
echo "  ./start.sh                    # Start all services in foreground"
echo ""
print_info "Or use systemd services (recommended for production):"
echo "  sudo cp systemd/*.service /etc/systemd/system/"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable trivia-bot trivia-bot-celery-worker trivia-bot-celery-beat"
echo "  sudo systemctl start trivia-bot trivia-bot-celery-worker trivia-bot-celery-beat"
echo ""
print_info "To stop the bot:"
echo "  ./stop.sh                     # Stop all services"
echo ""
print_info "To check logs:"
echo "  tail -f logs/trivia_bot.log"
echo "  tail -f logs/celery_worker.log"
echo "  tail -f logs/celery_beat.log"
echo ""
