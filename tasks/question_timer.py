"""
Question timer - updates question message with countdown timer.
"""
from celery import Task
from tasks.celery_app import celery_app
from utils.logging import get_logger
from telegram import Bot
import config

logger = get_logger(__name__)


@celery_app.task(name="tasks.question_timer.start_question_timer", bind=True)
def start_question_timer(
    self: Task,
    game_id: int,
    round_id: int,
    round_question_id: int,
    user_id: int,
    message_id: int,
    time_limit: int
) -> None:
    """
    Start countdown timer for question.
    Schedules updates every second using countdown.
    
    Args:
        game_id: Game ID
        round_id: Round ID
        round_question_id: Round question ID
        user_id: User Telegram ID
        message_id: Message ID to update
        time_limit: Time limit in seconds
    """
    # Schedule first update immediately
    logger.info(f"Starting question timer for round_question_id={round_question_id}, user_id={user_id}, time_limit={time_limit}")
    update_question_timer.apply_async(
        args=[game_id, round_id, round_question_id, user_id, message_id, time_limit, time_limit],
        countdown=0
    )


@celery_app.task(name="tasks.question_timer.update_question_timer")
def update_question_timer(
    game_id: int,
    round_id: int,
    round_question_id: int,
    user_id: int,
    message_id: int,
    remaining: int,
    time_limit: int
) -> None:
    """
    Update question message with countdown timer.
    
    Args:
        game_id: Game ID
        round_id: Round ID
        round_question_id: Round question ID
        user_id: User Telegram ID
        message_id: Message ID to update
        remaining: Remaining seconds
    """
    from database.session import db_session
    from database.models import RoundQuestion, Answer, Round, Question, Theme
    
    # Check if user already answered (stop timer if answered)
    with db_session() as session:
        existing_answer = session.query(Answer).filter(
            Answer.round_question_id == round_question_id,
            Answer.user_id == user_id
        ).first()
        
        if existing_answer:
            # User answered, stop timer
            logger.debug(f"User {user_id} answered, stopping timer for round_question_id={round_question_id}")
            return
        
        # Get question data
        rq = session.query(RoundQuestion).filter(RoundQuestion.id == round_question_id).first()
        if not rq:
            logger.debug(f"RoundQuestion {round_question_id} not found, stopping timer")
            return
        
        question = session.query(Question).filter(Question.id == rq.question_id).first()
        if not question:
            logger.debug(f"Question not found for round_question_id={round_question_id}, stopping timer")
            return
        
        round_obj = session.query(Round).filter(Round.id == round_id).first()
        if not round_obj:
            logger.debug(f"Round {round_id} not found, stopping timer")
            return
        
        # Rebuild question text
        theme_text = ""
        if round_obj.theme_id:
            theme = session.query(Theme).filter(Theme.id == round_obj.theme_id).first()
            if theme:
                theme_text = f" | Тема: {theme.name}"
        
        # Start with header
        question_text = (
            f"🏁 Раунд {round_obj.round_number}/{config.config.ROUNDS_PER_GAME}{theme_text}\n"
            f"Вопрос {rq.question_number}/{config.config.QUESTIONS_PER_ROUND}:\n\n"
        )
        
        # Add leaderboard FIRST (before question) if available (only if not first question)
        if rq.question_number > 1 and round_obj:
            try:
                from bot.round_leaderboard import get_round_leaderboard
                from database.models import User
                db_user = session.query(User).filter(User.telegram_id == user_id).first()
                current_user_id = db_user.id if db_user else None
                
                # Verify we're using the correct round_id
                logger.debug(f"Timer update: round_id={round_id}, round_obj.id={round_obj.id}, question_number={rq.question_number}")
                
                leaderboard_text, _ = get_round_leaderboard(
                    round_obj.game_id,
                    round_obj.id,  # Use round_obj.id to ensure we have the correct round
                    current_user_id
                )
                if leaderboard_text:
                    question_text += f"{leaderboard_text}\n\n"
            except Exception as e:
                logger.warning(f"Failed to add leaderboard to timer update: {e}", exc_info=True)
                # Continue without leaderboard
        
        # Add question text AFTER leaderboard (so it's visible on mobile)
        question_text += f"❓ {question.question_text}\n\n"
        
        # Visual progress bar
        total_bars = 20
        filled_bars = int((remaining / time_limit) * total_bars) if time_limit > 0 else 0
        empty_bars = total_bars - filled_bars
        progress_bar = "▓" * filled_bars + "░" * empty_bars
        
        question_text += f"\n⏱️ {remaining} сек [{progress_bar}]"
        
        # Rebuild keyboard to keep buttons (use shuffled options if available)
        from bot.keyboards import QuestionAnswerKeyboard
        options = {}
        
        # Use shuffled options if available, otherwise use original
        if rq.shuffled_options:
            shuffled_mapping = rq.shuffled_options
            logger.debug(f"[TIMER] Using shuffled options for round_question_id={round_question_id}: {shuffled_mapping}")
            for new_pos in ['A', 'B', 'C', 'D']:
                if new_pos in shuffled_mapping:
                    original_pos = shuffled_mapping[new_pos]
                    if original_pos == 'A' and question.option_a:
                        options[new_pos] = question.option_a
                    elif original_pos == 'B' and question.option_b:
                        options[new_pos] = question.option_b
                    elif original_pos == 'C' and question.option_c:
                        options[new_pos] = question.option_c
                    elif original_pos == 'D' and question.option_d:
                        options[new_pos] = question.option_d
        else:
            # Fallback to original options if no shuffling
            logger.debug(f"[TIMER] Using original options for round_question_id={round_question_id} (no shuffling)")
            if question.option_a:
                options['A'] = question.option_a
            if question.option_b:
                options['B'] = question.option_b
            if question.option_c:
                options['C'] = question.option_c
            if question.option_d:
                options['D'] = question.option_d
        
        keyboard = QuestionAnswerKeyboard.get_keyboard(round_question_id, options)
    
    # Update message with keyboard preserved
    try:
        logger.info(f"Updating timer: remaining={remaining}, time_limit={time_limit}, user_id={user_id}, message_id={message_id}")
        bot = Bot(token=config.config.TELEGRAM_BOT_TOKEN)
        import asyncio
        asyncio.run(bot.edit_message_text(
            chat_id=user_id,
            message_id=message_id,
            text=question_text,
            reply_markup=keyboard
        ))
        logger.info(f"Timer updated successfully: remaining={remaining}")
    except Exception as e:
        # Message might be already edited or deleted, ignore
        logger.warning(f"Could not update timer message: {e}", exc_info=True)
        # Don't return - continue scheduling next update
    
    # Schedule next update if time remaining
    if remaining > 1:
        # Check if question is still active before scheduling next update
        with db_session() as session:
            # Check if user answered
            existing_answer = session.query(Answer).filter(
                Answer.round_question_id == round_question_id,
                Answer.user_id == user_id
            ).first()
            
            if existing_answer:
                logger.debug(f"User {user_id} answered, stopping timer")
                return
            
            # Check if next question was already displayed (sent to players)
            rq = session.query(RoundQuestion).filter(RoundQuestion.id == round_question_id).first()
            if rq:
                next_question = session.query(RoundQuestion).filter(
                    RoundQuestion.round_id == round_id,
                    RoundQuestion.question_number == rq.question_number + 1,
                    RoundQuestion.displayed_at.isnot(None)  # Next question was already sent
                ).first()
                
                if next_question:
                    logger.debug(f"Next question already displayed (question_number={next_question.question_number}), stopping timer for round_question_id={round_question_id}")
                    return
        
        # Schedule next update
        update_question_timer.apply_async(
            args=[game_id, round_id, round_question_id, user_id, message_id, remaining - 1, time_limit],
            countdown=1
        )
    else:
        # Time expired, stop timer
        logger.debug(f"Time expired for round_question_id={round_question_id}, user_id={user_id}, stopping timer")
