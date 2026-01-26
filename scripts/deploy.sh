#!/bin/bash

# Trivia Bot Deployment Script
# Автоматически обновляет код, применяет миграции и перезапускает сервисы

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$PROJECT_DIR/venv"

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

# Check if we're in the right directory
if [ ! -f "$PROJECT_DIR/main.py" ]; then
    print_error "main.py not found. Are you in the project directory?"
    exit 1
fi

print_info "=========================================="
print_info "Trivia Bot Deployment Script"
print_info "=========================================="
echo ""

# Step 1: Backup current state
print_info "Step 1: Creating backup..."
BACKUP_DIR="$PROJECT_DIR/backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
if [ -f "$PROJECT_DIR/tasks/bot_answers.py" ]; then
    cp "$PROJECT_DIR/tasks/bot_answers.py" "$BACKUP_DIR/" 2>/dev/null || true
fi
print_success "Backup created at $BACKUP_DIR"

# Step 2: Update code from git
print_info "Step 2: Updating code from git..."
cd "$PROJECT_DIR"

# Check if git is available
if ! command -v git &> /dev/null; then
    print_warning "Git is not installed. Skipping git pull..."
else
    # Check if we're in a git repository
    if [ -d ".git" ]; then
        print_info "Pulling latest changes from git..."
        git pull origin main || {
            print_warning "Git pull failed. Continuing with local code..."
        }
        print_success "Code updated from git"
    else
        print_warning "Not a git repository. Skipping git pull..."
    fi
fi

# Step 3: Activate virtual environment
print_info "Step 3: Activating virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
    print_error "Virtual environment not found at $VENV_DIR"
    print_info "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
print_success "Virtual environment activated"

# Step 4: Install/update dependencies
print_info "Step 4: Installing/updating dependencies..."
pip install --upgrade pip -q
pip install -r "$PROJECT_DIR/requirements.txt" -q
print_success "Dependencies updated"

# Step 5: Apply database migrations
print_info "Step 5: Applying database migrations..."

# Find all migration files
MIGRATIONS_DIR="$PROJECT_DIR/database/migrations"
if [ -d "$MIGRATIONS_DIR" ]; then
    for migration_file in "$MIGRATIONS_DIR"/*.py; do
        if [ -f "$migration_file" ]; then
            migration_name=$(basename "$migration_file")
            print_info "Running migration: $migration_name"
            python "$migration_file" || {
                print_warning "Migration $migration_name failed or already applied"
            }
        fi
    done
    print_success "Migrations applied"
else
    print_warning "Migrations directory not found. Skipping..."
fi

# Step 6: Verify bot_answers.py is updated
print_info "Step 6: Verifying bot_answers.py update..."
BOT_ANSWERS_FILE="$PROJECT_DIR/tasks/bot_answers.py"
if grep -q "shuffled_options" "$BOT_ANSWERS_FILE" 2>/dev/null; then
    print_success "bot_answers.py already updated with shuffled_options support"
else
    print_warning "bot_answers.py needs to be updated. Updating now..."
    
    # Use the fix script
    if [ -f "$PROJECT_DIR/scripts/fix_bot_answers.py" ]; then
        python "$PROJECT_DIR/scripts/fix_bot_answers.py" || {
            print_error "Failed to update bot_answers.py automatically"
            print_warning "Please update tasks/bot_answers.py manually (lines 81-96)"
        }
    else
        print_warning "fix_bot_answers.py not found. Please update tasks/bot_answers.py manually"
    fi
    
    # Verify update
    if grep -q "shuffled_options" "$BOT_ANSWERS_FILE" 2>/dev/null; then
        print_success "bot_answers.py updated successfully"
    else
        print_error "Failed to update bot_answers.py automatically"
        print_warning "Please update tasks/bot_answers.py manually (lines 81-96)"
    fi
fi

# Step 7: Restart services
print_info "Step 7: Restarting services..."

# Check if systemd services are installed
if systemctl list-units --type=service | grep -q "trivia-bot"; then
    print_info "Restarting systemd services..."
    sudo systemctl restart trivia-bot || print_warning "Failed to restart trivia-bot service"
    sudo systemctl restart trivia-bot-celery-worker || print_warning "Failed to restart celery-worker service"
    sudo systemctl restart trivia-bot-celery-beat || print_warning "Failed to restart celery-beat service"
    print_success "Systemd services restarted"
else
    print_warning "Systemd services not found. Please restart services manually:"
    echo "  - Bot: ./start.sh or python main.py"
    echo "  - Celery worker: celery -A tasks.celery_app worker --loglevel=info"
    echo "  - Celery beat: celery -A tasks.celery_app beat --loglevel=info"
fi

# Summary
echo ""
print_success "=========================================="
print_success "Deployment completed successfully!"
print_success "=========================================="
echo ""
print_info "Summary:"
echo "  ✓ Code updated from git"
echo "  ✓ Dependencies installed/updated"
echo "  ✓ Database migrations applied"
echo "  ✓ bot_answers.py updated"
echo "  ✓ Services restarted"
echo ""
print_info "Next steps:"
echo "  1. Check service status: sudo systemctl status trivia-bot"
echo "  2. Check logs: sudo journalctl -u trivia-bot -f"
echo "  3. Test the bot to ensure everything works"
echo ""
