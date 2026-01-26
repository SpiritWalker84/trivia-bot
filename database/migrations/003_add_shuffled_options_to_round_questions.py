#!/usr/bin/env python
"""
Migration: Add shuffled_options and correct_option_shuffled fields to round_questions table.
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
    logger.info("Running migration: Add shuffled_options and correct_option_shuffled fields to round_questions table")
    
    with db_session() as session:
        try:
            # Check if columns already exist
            result = session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'round_questions' 
                AND column_name IN ('shuffled_options', 'correct_option_shuffled')
            """))
            existing = [row[0] for row in result.fetchall()]
            
            if 'shuffled_options' not in existing:
                logger.info("Adding shuffled_options column...")
                session.execute(text("""
                    ALTER TABLE round_questions 
                    ADD COLUMN shuffled_options JSONB DEFAULT NULL
                """))
                logger.info("shuffled_options column added")
            else:
                logger.info("shuffled_options column already exists")
            
            if 'correct_option_shuffled' not in existing:
                logger.info("Adding correct_option_shuffled column...")
                session.execute(text("""
                    ALTER TABLE round_questions 
                    ADD COLUMN correct_option_shuffled CHAR(1) DEFAULT NULL
                """))
                logger.info("correct_option_shuffled column added")
            else:
                logger.info("correct_option_shuffled column already exists")
            
            session.commit()
            logger.info("Migration completed successfully!")
            
        except Exception as e:
            logger.error(f"Error running migration: {e}", exc_info=True)
            session.rollback()
            sys.exit(1)


if __name__ == "__main__":
    main()
