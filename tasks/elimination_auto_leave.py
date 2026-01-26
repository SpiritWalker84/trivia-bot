"""
Automatic leave game for eliminated players who don't respond.
"""
from celery import Task
from tasks.celery_app import celery_app
from utils.logging import get_logger
from database.session import db_session
from database.models import GamePlayer, User
from telegram import Bot
from bot.keyboards import MainMenuKeyboard
import config

logger = get_logger(__name__)


@celery_app.task(name="tasks.elimination_auto_leave.auto_leave_game")
def auto_leave_game(game_id: int, user_id: int) -> None:
    """
    Automatically leave game for eliminated player who didn't respond.
    
    Args:
        game_id: Game ID
        user_id: User ID
    """
    with db_session() as session:
        game_player = session.query(GamePlayer).filter(
            GamePlayer.game_id == game_id,
            GamePlayer.user_id == user_id
        ).first()
        
        if not game_player:
            logger.warning(f"GamePlayer not found for game_id={game_id}, user_id={user_id}")
            return
        
        # Check if player already made a choice
        if game_player.is_spectator is not None or game_player.left_game:
            logger.debug(f"Player {user_id} already made a choice, skipping auto-leave")
            return
        
        # Check if player is still eliminated
        if not game_player.is_eliminated:
            logger.debug(f"Player {user_id} is not eliminated anymore, skipping auto-leave")
            return
        
        # Auto-leave: set player as left
        game_player.is_spectator = False
        game_player.left_game = True
        session.commit()
        
        logger.info(f"Player {user_id} automatically left game {game_id} after timeout")
        
        # Send notification and show main menu
        user = session.query(User).filter(User.id == user_id).first()
        if user and user.telegram_id:
            try:
                bot = Bot(token=config.config.TELEGRAM_BOT_TOKEN)
                import asyncio
                asyncio.run(bot.send_message(
                    chat_id=user.telegram_id,
                    text="⏱️ Время выбора истекло.\n\n"
                         "👋 Вы автоматически вышли из игры.\n\n"
                         "Вы больше не будете получать уведомления об этой игре.",
                    reply_markup=MainMenuKeyboard.get_keyboard()
                ))
                logger.info(f"Sent auto-leave notification to user {user.telegram_id}")
            except Exception as e:
                logger.error(f"Failed to send auto-leave notification to user {user.telegram_id}: {e}")
