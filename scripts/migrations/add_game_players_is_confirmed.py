"""
Add is_confirmed column to game_players table.
Run once on server.
"""
import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


def main() -> None:
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is not set.")
        sys.exit(1)

    engine = create_engine(database_url)
    with engine.begin() as conn:
        # Check if column already exists
        exists = conn.execute(text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'game_players'
              AND column_name = 'is_confirmed'
            """
        )).first()

        if exists:
            print("Column game_players.is_confirmed already exists. Nothing to do.")
            return

        conn.execute(text(
            """
            ALTER TABLE game_players
            ADD COLUMN is_confirmed BOOLEAN NOT NULL DEFAULT TRUE
            """
        ))

        print("Added column game_players.is_confirmed successfully.")


if __name__ == "__main__":
    main()
