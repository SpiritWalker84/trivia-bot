#!/usr/bin/env python
"""
Script to create database tables.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.session import get_db_session
from utils.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def main():
    """Create database tables."""
    logger.info("Creating database tables...")
    
    try:
        db = get_db_session()
        db.create_tables()
        logger.info("Database tables created successfully!")
    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
