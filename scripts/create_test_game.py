#!/usr/bin/env python
"""
Script to create a test game with bots for quick testing.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.session import db_session
from database.models import Game, GamePlayer
from database.queries import UserQueries, GameQueries
import config
from tasks.game_tasks import start_game_task
from utils.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def main():
    """Create test game."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Create test game')
    parser.add_argument('--telegram-id', type=int, help='Your Telegram ID (for training game)')
    parser.add_argument('--type', choices=['training', 'quick'], default='training',
                       help='Game type (default: training)')
    parser.add_argument('--players', type=int, default=10, help='Total players (default: 10)')
    
    args = parser.parse_args()
    
    with db_session() as session:
        if args.type == 'training':
            if not args.telegram_id:
                logger.error("--telegram-id is required for training game")
                sys.exit(1)
            
            # Get user
            user = UserQueries.get_user_by_telegram_id(session, args.telegram_id)
            if not user:
                logger.error(f"User with telegram_id {args.telegram_id} not found")
                logger.info("Please run /start in bot first to create user")
                sys.exit(1)
            
            # Create game
            game = GameQueries.create_game(
                session,
                game_type='training',
                creator_id=user.id,
                total_rounds=config.config.ROUNDS_PER_GAME
            )
            
            # Add user
            game_player = GamePlayer(
                game_id=game.id,
                user_id=user.id,
                is_bot=False,
                join_order=1
            )
            session.add(game_player)
            
            # Add bots
            bots_needed = args.players - 1
            bots = UserQueries.get_bots(session, limit=bots_needed)
            
            if len(bots) < bots_needed:
                logger.warning(f"Only {len(bots)} bots available, need {bots_needed}")
                logger.info("Run scripts/add_test_data.py to create more bots")
            
            for i, bot in enumerate(bots, 2):
                bot_player = GamePlayer(
                    game_id=game.id,
                    user_id=bot.id,
                    is_bot=True,
                    bot_difficulty=bot.bot_difficulty,
                    join_order=i
                )
                session.add(bot_player)
            
            session.commit()
            
            logger.info(f"Created training game {game.id} with {len(bots) + 1} players")
            logger.info(f"Starting game...")
            
            # Start game
            start_game_task.delay(game.id)
            
            logger.info(f"Game {game.id} started! Check your Telegram for questions.")
            
        else:  # quick game
            logger.info("Quick game creation not implemented yet")
            logger.info("Use the bot interface to join quick game queue")


if __name__ == "__main__":
    main()
