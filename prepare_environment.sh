#!/bin/bash

# Trivia Bot - Environment Preparation Script for Ubuntu
# Automatically installs and configures PostgreSQL, Redis, and database setup

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_NAME="trivia_bot"
DB_USER="trivia_user"
DB_PASSWORD="trivia_password"

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

# Check if running as root for certain operations
check_sudo() {
    if [ "$EUID" -ne 0 ]; then
        print_warning "Some operations require sudo. You may be prompted for password."
    fi
}

# ============================================
# PostgreSQL Installation and Setup
# ============================================
setup_postgresql() {
    print_info "Checking PostgreSQL..."
    
    if check_command psql; then
        PG_VERSION=$(psql --version | cut -d' ' -f3)
        print_success "PostgreSQL found (version $PG_VERSION)"
    else
        print_warning "PostgreSQL is not installed. Installing..."
        
        # Update package list
        sudo apt-get update
        
        # Install PostgreSQL
        sudo apt-get install -y postgresql postgresql-contrib
        
        print_success "PostgreSQL installed"
    fi
    
    # Check if PostgreSQL service is running
    if sudo systemctl is-active --quiet postgresql; then
        print_success "PostgreSQL service is running"
    else
        print_info "Starting PostgreSQL service..."
        sudo systemctl start postgresql
        sudo systemctl enable postgresql
        print_success "PostgreSQL service started and enabled"
    fi
    
    # Setup database and user
    print_info "Setting up database and user..."
    
    sudo -u postgres psql <<EOF
-- Create user if not exists
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = '$DB_USER') THEN
        CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';
        ALTER USER $DB_USER CREATEDB;
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
    
    # Test connection
    if PGPASSWORD=$DB_PASSWORD psql -h localhost -U $DB_USER -d $DB_NAME -c "SELECT 1;" &> /dev/null; then
        print_success "PostgreSQL connection test successful"
    else
        print_warning "PostgreSQL connection test failed, but setup completed"
    fi
}

# ============================================
# Redis Installation and Setup
# ============================================
setup_redis() {
    print_info "Checking Redis..."
    
    if check_command redis-cli; then
        REDIS_VERSION=$(redis-cli --version | cut -d' ' -f2)
        print_success "Redis found (version $REDIS_VERSION)"
    else
        print_warning "Redis is not installed. Installing..."
        
        # Update package list
        sudo apt-get update
        
        # Install Redis
        sudo apt-get install -y redis-server
        
        print_success "Redis installed"
    fi
    
    # Check if Redis service is running
    if sudo systemctl is-active --quiet redis-server; then
        print_success "Redis service is running"
    else
        print_info "Starting Redis service..."
        sudo systemctl start redis-server
        sudo systemctl enable redis-server
        print_success "Redis service started and enabled"
    fi
    
    # Test Redis connection
    if redis-cli ping &> /dev/null; then
        print_success "Redis connection test successful (PONG)"
    else
        print_error "Redis connection test failed"
        return 1
    fi
    
    # Configure Redis for persistence (optional)
    if ! grep -q "save 900 1" /etc/redis/redis.conf 2>/dev/null; then
        print_info "Redis persistence is already configured or file not accessible"
    fi
}

# ============================================
# Python Environment Setup
# ============================================
setup_python() {
    print_info "Checking Python..."
    
    if check_command python3; then
        PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
        print_success "Python found (version $PYTHON_VERSION)"
    else
        print_warning "Python 3 is not installed. Installing..."
        sudo apt-get update
        sudo apt-get install -y python3 python3-pip python3-venv
        print_success "Python 3 installed"
    fi
    
    # Check pip
    if check_command pip3; then
        print_success "pip3 found"
    else
        print_warning "pip3 not found. Installing..."
        sudo apt-get install -y python3-pip
    fi
}

# ============================================
# Database Tables Creation
# ============================================
setup_database_tables() {
    print_info "Setting up database tables..."
    
    # Check if .env exists
    if [ ! -f "$SCRIPT_DIR/.env" ]; then
        print_warning ".env file not found. Creating from .env.example..."
        if [ -f "$SCRIPT_DIR/.env.example" ]; then
            cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
            # Update DATABASE_URL with our credentials
            sed -i "s|postgresql://user:password@localhost:5432/trivia_bot|postgresql://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME|g" "$SCRIPT_DIR/.env"
            print_warning "Please edit .env file and set your TELEGRAM_BOT_TOKEN"
        else
            print_error ".env.example not found!"
            return 1
        fi
    fi
    
    # Activate virtual environment if exists
    if [ -d "$SCRIPT_DIR/venv" ]; then
        source "$SCRIPT_DIR/venv/bin/activate"
        print_info "Virtual environment activated"
    else
        print_warning "Virtual environment not found. Creating..."
        python3 -m venv "$SCRIPT_DIR/venv"
        source "$SCRIPT_DIR/venv/bin/activate"
        print_success "Virtual environment created"
    fi
    
    # Install dependencies if needed
    if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
        print_info "Installing Python dependencies..."
        pip install --upgrade pip --quiet
        pip install -r "$SCRIPT_DIR/requirements.txt" --quiet
        print_success "Dependencies installed"
    fi
    
    # Create database tables
    print_info "Creating database tables..."
    if python3 "$SCRIPT_DIR/scripts/create_tables.py" 2>/dev/null; then
        print_success "Database tables created"
    else
        print_warning "Database tables creation had issues, but continuing..."
    fi
}

# ============================================
# Main Function
# ============================================
main() {
    echo ""
    print_info "=========================================="
    print_info "Trivia Bot - Environment Preparation"
    print_info "=========================================="
    echo ""
    
    # Check sudo access
    check_sudo
    
    # Setup Python
    setup_python
    echo ""
    
    # Setup PostgreSQL
    setup_postgresql
    echo ""
    
    # Setup Redis
    setup_redis
    echo ""
    
    # Setup database tables
    setup_database_tables
    echo ""
    
    # Summary
    print_success "=========================================="
    print_success "Environment preparation completed!"
    print_success "=========================================="
    echo ""
    print_info "Next steps:"
    echo "  1. Edit .env file and set your TELEGRAM_BOT_TOKEN"
    echo "  2. (Optional) Add test data: python scripts/add_test_data.py"
    echo "  3. Start the bot: python main.py"
    echo "  4. Start Celery worker: celery -A tasks.celery_app worker --loglevel=info"
    echo "  5. Start Celery beat: celery -A tasks.celery_app beat --loglevel=info"
    echo ""
    print_info "Database credentials:"
    echo "  Database: $DB_NAME"
    echo "  User: $DB_USER"
    echo "  Password: $DB_PASSWORD"
    echo "  Connection: postgresql://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME"
    echo ""
}

# Run main function
main
