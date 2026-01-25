#!/usr/bin/env python
"""
Migration: Add is_spectator and left_game fields to game_players table.
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
    logger.info("Running migration: Add is_spectator and left_game fields")
    
    with db_session() as session:
        try:
            # Check if columns already exist
            result = session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'game_players' 
                AND column_name IN ('is_spectator', 'left_game')
            """))
            existing_columns = [row[0] for row in result]
            
            # Add is_spectator column if it doesn't exist
            if 'is_spectator' not in existing_columns:
                logger.info("Adding is_spectator column...")
                session.execute(text("""
                    ALTER TABLE game_players 
                    ADD COLUMN is_spectator BOOLEAN DEFAULT NULL
                """))
                logger.info("is_spectator column added")
            else:
                logger.info("is_spectator column already exists")
            
            # Add left_game column if it doesn't exist
            if 'left_game' not in existing_columns:
                logger.info("Adding left_game column...")
                session.execute(text("""
                    ALTER TABLE game_players 
                    ADD COLUMN left_game BOOLEAN NOT NULL DEFAULT FALSE
                """))
                logger.info("left_game column added")
            else:
                logger.info("left_game column already exists")
            
            session.commit()
            logger.info("Migration completed successfully!")
            
        except Exception as e:
            logger.error(f"Error running migration: {e}", exc_info=True)
            session.rollback()
            sys.exit(1)


if __name__ == "__main__":
    main()
