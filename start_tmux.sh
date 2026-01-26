#!/bin/bash

# Trivia Bot - Tmux Startup Script for Ubuntu
# Проверяет/создает виртуальную среду и запускает 3 процесса в tmux панелях

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
TMUX_SESSION="trivia-bot"
PYTHON_VERSION="3"

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

# Check if tmux is installed
check_tmux() {
    if ! check_command tmux; then
        print_error "tmux is not installed. Installing..."
        sudo apt-get update
        sudo apt-get install -y tmux
        print_success "tmux installed"
    else
        print_success "tmux found"
    fi
}

# Check and create virtual environment
setup_venv() {
    print_info "Checking virtual environment..."
    
    if [ ! -d "$VENV_DIR" ]; then
        print_warning "Virtual environment not found. Creating..."
        
        # Check Python
        if ! check_command python3; then
            print_error "Python 3 is not installed. Installing..."
            sudo apt-get update
            sudo apt-get install -y python3 python3-pip python3-venv
        fi
        
        # Create virtual environment
        python3 -m venv "$VENV_DIR"
        print_success "Virtual environment created"
    else
        print_success "Virtual environment already exists"
    fi
    
    # Activate virtual environment
    source "$VENV_DIR/bin/activate"
    
    # Upgrade pip
    print_info "Upgrading pip..."
    pip install --upgrade pip --quiet
    
    # Install dependencies
    if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
        print_info "Installing/updating dependencies..."
        pip install -r "$SCRIPT_DIR/requirements.txt" --quiet
        print_success "Dependencies installed"
    else
        print_warning "requirements.txt not found"
    fi
}

# Check if tmux session exists
session_exists() {
    tmux has-session -t "$TMUX_SESSION" 2>/dev/null
}

# Kill existing session if exists
kill_session() {
    if session_exists; then
        print_warning "Tmux session '$TMUX_SESSION' already exists. Killing it..."
        tmux kill-session -t "$TMUX_SESSION"
        sleep 1
    fi
}

# Start tmux session with 3 panes
start_tmux_session() {
    print_info "Starting tmux session with 3 panes..."
    
    # Change to project directory
    cd "$SCRIPT_DIR"
    
    # Activate virtual environment path
    VENV_ACTIVATE="$VENV_DIR/bin/activate"
    
    # Create new tmux session with first pane (main.py)
    tmux new-session -d -s "$TMUX_SESSION" -x 200 -y 50 \
        "source $VENV_ACTIVATE && python main.py"
    
    # Create logs directory if it doesn't exist
    mkdir -p "$SCRIPT_DIR/logs"
    
    # Split window horizontally (creates 2 panes)
    tmux split-window -h -t "$TMUX_SESSION" \
        "source $VENV_ACTIVATE && celery -A tasks.celery_app worker --loglevel=info --logfile=$SCRIPT_DIR/logs/celery_worker.log"
    
    # Split the right pane vertically (creates 3 panes)
    tmux split-window -v -t "$TMUX_SESSION" \
        "source $VENV_ACTIVATE && celery -A tasks.celery_app beat --loglevel=info"
    
    # Select pane 0 (main.py) and resize panes to equal size
    tmux select-pane -t 0
    tmux select-layout -t "$TMUX_SESSION" tiled
    
    # Set pane titles
    tmux select-pane -t 0 -T "Main Bot"
    tmux select-pane -t 1 -T "Celery Worker"
    tmux select-pane -t 2 -T "Celery Beat"
    
    print_success "Tmux session started"
}

# Main function
main() {
    echo ""
    print_info "=========================================="
    print_info "Trivia Bot - Tmux Startup Script"
    print_info "=========================================="
    echo ""
    
    # Check tmux
    check_tmux
    echo ""
    
    # Setup virtual environment
    setup_venv
    echo ""
    
    # Kill existing session if exists
    kill_session
    
    # Start tmux session
    start_tmux_session
    
    # Show instructions
    echo ""
    print_success "=========================================="
    print_success "All processes started in tmux!"
    print_success "=========================================="
    echo ""
    print_info "Tmux session name: $TMUX_SESSION"
    echo ""
    print_info "To attach to the session:"
    echo "  tmux attach -t $TMUX_SESSION"
    echo ""
    print_info "To detach from session (keep it running):"
    echo "  Press: Ctrl+B, then D"
    echo ""
    print_info "To kill the session:"
    echo "  tmux kill-session -t $TMUX_SESSION"
    echo ""
    print_info "Pane layout:"
    echo "  [0] Main Bot (python main.py)"
    echo "  [1] Celery Worker"
    echo "  [2] Celery Beat"
    echo ""
    print_info "To switch between panes:"
    echo "  Ctrl+B, then arrow keys"
    echo ""
    
    # Ask if user wants to attach now
    read -p "Attach to tmux session now? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        tmux attach -t "$TMUX_SESSION"
    else
        print_info "Session is running in background. Use 'tmux attach -t $TMUX_SESSION' to view it."
    fi
}

# Run main function
main
