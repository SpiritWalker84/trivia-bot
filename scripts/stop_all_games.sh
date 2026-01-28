#!/bin/bash
# Script to stop all active games
# Activates virtual environment, runs cleanup script, then deactivates

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "Error: Virtual environment not found at venv/"
    exit 1
fi

# Run cleanup script
python scripts/cleanup_games.py

# Store exit code
EXIT_CODE=$?

# Deactivate virtual environment
deactivate

# Exit with the same code as cleanup script
exit $EXIT_CODE
