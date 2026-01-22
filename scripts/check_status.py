#!/usr/bin/env python
"""
Script to check system status.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.session import db_session
from database.models import Game, User, Question, Theme, Pool
from utils.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def main():
    """Check system status."""
    print("=" * 50)
    print("SYSTEM STATUS")
    print("=" * 50)
    
    with db_session() as session:
        # Count users
        total_users = session.query(User).count()
        real_users = session.query(User).filter(User.is_bot == False).count()
        bots = session.query(User).filter(User.is_bot == True).count()
        
        print(f"\n👥 Users:")
        print(f"  Total: {total_users}")
        print(f"  Real users: {real_users}")
        print(f"  Bots: {bots}")
        
        # Count themes
        themes_count = session.query(Theme).count()
        print(f"\n📚 Themes: {themes_count}")
        
        # Count questions
        questions_count = session.query(Question).count()
        approved_questions = session.query(Question).filter(Question.is_approved == True).count()
        print(f"\n❓ Questions:")
        print(f"  Total: {questions_count}")
        print(f"  Approved: {approved_questions}")
        
        # Count games
        total_games = session.query(Game).count()
        active_games = session.query(Game).filter(
            Game.status.in_(['pre_start', 'in_progress'])
        ).count()
        finished_games = session.query(Game).filter(Game.status == 'finished').count()
        
        print(f"\n🎮 Games:")
        print(f"  Total: {total_games}")
        print(f"  Active: {active_games}")
        print(f"  Finished: {finished_games}")
        
        # Count pools
        active_pools = session.query(Pool).filter(Pool.status == 'waiting').count()
        print(f"\n🏊 Pools:")
        print(f"  Active: {active_pools}")
        
        # Active games details
        if active_games > 0:
            print(f"\n📊 Active Games Details:")
            active = session.query(Game).filter(
                Game.status.in_(['pre_start', 'in_progress'])
            ).all()
            for game in active:
                players_count = len([p for p in game.players if not p.is_eliminated])
                print(f"  Game {game.id}: {game.status}, {players_count} players, round {game.current_round}")
    
    print("\n" + "=" * 50)


if __name__ == "__main__":
    main()
