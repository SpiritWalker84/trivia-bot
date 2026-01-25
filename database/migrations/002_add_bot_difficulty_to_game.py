#!/usr/bin/env python
"""
Migration: Add bot_difficulty field to games table.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.session import db_session
from sqlalchemy import text
from utils.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def main():
    """Run migration."""
    logger.info("Running migration: Add bot_difficulty field to games table")
    
    with db_session() as session:
        try:
            # Check if column already exists
            result = session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'games' 
                AND column_name = 'bot_difficulty'
            """))
            existing = result.fetchone()
            
            if existing:
                logger.info("bot_difficulty column already exists")
            else:
                logger.info("Adding bot_difficulty column...")
                session.execute(text("""
                    ALTER TABLE games 
                    ADD COLUMN bot_difficulty VARCHAR(20) DEFAULT NULL
                """))
                logger.info("bot_difficulty column added")
            
            session.commit()
            logger.info("Migration completed successfully!")
            
        except Exception as e:
            logger.error(f"Error running migration: {e}", exc_info=True)
            session.rollback()
            sys.exit(1)


if __name__ == "__main__":
    main()
