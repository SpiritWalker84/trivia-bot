"""
Round pause timer - updates pause message with countdown timer.
"""
from celery import Task
from tasks.celery_app import celery_app
from utils.logging import get_logger
from telegram import Bot
import config

logger = get_logger(__name__)


@celery_app.task(name="tasks.round_pause_timer.start_round_pause_timer", bind=True)
def start_round_pause_timer(
    self: Task,
    game_id: int,
    next_round: int,
    user_id: int,
    message_id: int,
    time_limit: int
) -> None:
    """
    Start countdown timer for round pause.
    Schedules updates every second using countdown.
    
    Args:
        game_id: Game ID
        next_round: Next round number
        user_id: User Telegram ID
        message_id: Message ID to update
        time_limit: Time limit in seconds (60)
    """
    # Schedule first update immediately
    logger.info(f"Starting round pause timer for game_id={game_id}, next_round={next_round}, user_id={user_id}, time_limit={time_limit}")
    update_round_pause_timer.apply_async(
        args=[game_id, next_round, user_id, message_id, time_limit, time_limit],
        countdown=0
    )


@celery_app.task(name="tasks.round_pause_timer.update_round_pause_timer")
def update_round_pause_timer(
    game_id: int,
    next_round: int,
    user_id: int,
    message_id: int,
    remaining: int,
    time_limit: int
) -> None:
    """
    Update pause message with countdown timer.
    
    Args:
        game_id: Game ID
        next_round: Next round number
        user_id: User Telegram ID
        message_id: Message ID to update
        remaining: Remaining seconds
        time_limit: Total time limit in seconds
    """
    from database.session import db_session
    from database.models import Game, Round
    
    # Check if game still exists and is in progress, and round hasn't started yet
    with db_session() as session:
        game = session.query(Game).filter(Game.id == game_id).first()
        if not game:
            logger.debug(f"Game {game_id} not found, stopping pause timer")
            return
        
        if game.status != 'in_progress':
            logger.debug(f"Game {game_id} is not in_progress (status: {game.status}), stopping pause timer")
            return
        
        # Check if round has already started (current_round >= next_round)
        if game.current_round and game.current_round >= next_round:
            logger.debug(f"Round {next_round} has already started (current_round={game.current_round}), stopping pause timer")
            return
        
        # Also check if the round object exists and is in progress (more reliable check)
        round_obj = session.query(Round).filter(
            Round.game_id == game_id,
            Round.round_number == next_round
        ).first()
        
        if round_obj and round_obj.status == 'in_progress':
            logger.debug(f"Round {next_round} already exists and is in_progress, stopping pause timer")
            return
    
    # Build pause message with timer
    pause_text = (
        f"⏸️ Пауза между раундами\n\n"
        f"Следующий раунд ({next_round}/{config.config.ROUNDS_PER_GAME}) начнется через {remaining} секунд.\n"
        f"У вас есть время, чтобы посмотреть результаты.\n\n"
    )
    
    # Add progress bar
    total_bars = 20
    filled_bars = int((remaining / time_limit) * total_bars) if time_limit > 0 else 0
    empty_bars = total_bars - filled_bars
    progress_bar = "▓" * filled_bars + "░" * empty_bars
    pause_text += f"⏱️ {remaining} сек [{progress_bar}]"
    
    try:
        logger.debug(f"Updating pause timer: remaining={remaining}, time_limit={time_limit}, user_id={user_id}, message_id={message_id}")
        bot = Bot(token=config.config.TELEGRAM_BOT_TOKEN)
        import asyncio
        from telegram.error import TelegramError, BadRequest
        
        asyncio.run(bot.edit_message_text(
            chat_id=user_id,
            message_id=message_id,
            text=pause_text,
            parse_mode="Markdown"
        ))
        logger.debug(f"Pause timer updated successfully: remaining={remaining}")
    except BadRequest as e:
        # Message might have been deleted or changed - stop timer
        if "message to edit not found" in str(e).lower() or "message is not modified" in str(e).lower():
            logger.debug(f"Pause timer message not found or not modified for user {user_id}, stopping timer")
            return
        else:
            logger.warning(f"Could not update pause timer message (BadRequest): {e}", exc_info=True)
    except TelegramError as e:
        # Other Telegram errors - stop timer to avoid spam
        logger.warning(f"Telegram error updating pause timer message: {e}, stopping timer")
        return
    except Exception as e:
        logger.warning(f"Could not update pause timer message: {e}, stopping timer", exc_info=True)
        return
    
    # Schedule next update if time remaining
    # Double-check that round hasn't started before scheduling next update
    with db_session() as session:
        game = session.query(Game).filter(Game.id == game_id).first()
        if not game or game.status != 'in_progress':
            logger.debug(f"Game {game_id} is not in_progress, stopping pause timer")
            return
        
        if game.current_round and game.current_round >= next_round:
            logger.debug(f"Round {next_round} has already started (current_round={game.current_round}), stopping pause timer")
            return
        
        # Also check if the round object exists and is in progress
        round_obj = session.query(Round).filter(
            Round.game_id == game_id,
            Round.round_number == next_round
        ).first()
        
        if round_obj and round_obj.status == 'in_progress':
            logger.debug(f"Round {next_round} already exists and is in_progress, stopping pause timer")
            return
    
    if remaining > 1:
        update_round_pause_timer.apply_async(
            args=[game_id, next_round, user_id, message_id, remaining - 1, time_limit],
            countdown=1
        )
    else:
        logger.debug(f"Pause timer finished for game {game_id}, next round {next_round}")
