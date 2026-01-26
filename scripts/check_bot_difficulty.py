#!/usr/bin/env python3
"""
Скрипт для проверки и исправления bot_difficulty в game_players.
Проверяет, что все боты в игре имеют правильную сложность из game.bot_difficulty.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.session import db_session
from database.models import Game, GamePlayer
from utils.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def check_and_fix_bot_difficulty(game_id: int = None):
    """
    Проверяет и исправляет bot_difficulty для ботов в играх.
    
    Args:
        game_id: ID конкретной игры (если None, проверяет все активные игры)
    """
    with db_session() as session:
        if game_id:
            games = [session.query(Game).filter(Game.id == game_id).first()]
            if not games[0]:
                logger.error(f"Game {game_id} not found")
                return
        else:
            # Проверяем все активные игры
            games = session.query(Game).filter(
                Game.status.in_(['waiting', 'in_progress'])
            ).all()
        
        logger.info(f"Checking {len(games)} game(s)...")
        
        for game in games:
            if not game.bot_difficulty:
                logger.info(f"Game {game.id}: no bot_difficulty set, skipping")
                continue
            
            expected_difficulty = game.bot_difficulty
            logger.info(f"Game {game.id}: expected bot_difficulty = '{expected_difficulty}'")
            
            # Получаем всех ботов в игре
            bot_players = session.query(GamePlayer).filter(
                GamePlayer.game_id == game.id,
                GamePlayer.is_bot == True
            ).all()
            
            fixed_count = 0
            for bot_player in bot_players:
                if bot_player.bot_difficulty != expected_difficulty:
                    logger.warning(
                        f"Game {game.id}, Bot {bot_player.user_id} (player {bot_player.id}): "
                        f"wrong difficulty '{bot_player.bot_difficulty}', should be '{expected_difficulty}'"
                    )
                    bot_player.bot_difficulty = expected_difficulty
                    fixed_count += 1
                else:
                    logger.debug(
                        f"Game {game.id}, Bot {bot_player.user_id}: correct difficulty '{bot_player.bot_difficulty}'"
                    )
            
            if fixed_count > 0:
                session.commit()
                logger.info(f"Game {game.id}: fixed {fixed_count} bot(s)")
            else:
                logger.info(f"Game {game.id}: all bots have correct difficulty")


def main():
    """Основная функция."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Check and fix bot difficulty in games')
    parser.add_argument('--game-id', type=int, help='Check specific game ID')
    args = parser.parse_args()
    
    try:
        check_and_fix_bot_difficulty(game_id=args.game_id)
        print("\n[OK] Check completed!")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        print(f"\n[ERROR] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
