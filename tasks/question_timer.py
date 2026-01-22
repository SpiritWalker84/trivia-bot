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
            logger.debug(f"User {user_id} answered, stopping timer")
            return
        
        # Get question data
        rq = session.query(RoundQuestion).filter(RoundQuestion.id == round_question_id).first()
        if not rq:
            return
        
        question = session.query(Question).filter(Question.id == rq.question_id).first()
        if not question:
            return
        
        round_obj = session.query(Round).filter(Round.id == round_id).first()
        if not round_obj:
            return
        
        # Rebuild question text
        theme_text = ""
        if round_obj.theme_id:
            theme = session.query(Theme).filter(Theme.id == round_obj.theme_id).first()
            if theme:
                theme_text = f" | Тема: {theme.name}"
        
        question_text = (
            f"🏁 Раунд {round_obj.round_number}/{config.config.ROUNDS_PER_GAME}{theme_text}\n"
            f"Вопрос {rq.question_number}/{config.config.QUESTIONS_PER_ROUND}:\n\n"
            f"❓ {question.question_text}\n\n"
        )
        
        # Build options
        if question.option_a:
            question_text += f"A) {question.option_a}\n"
        if question.option_b:
            question_text += f"B) {question.option_b}\n"
        if question.option_c:
            question_text += f"C) {question.option_c}\n"
        if question.option_d:
            question_text += f"D) {question.option_d}\n"
        
        # Visual progress bar
        total_bars = 20
        filled_bars = int((remaining / time_limit) * total_bars) if time_limit > 0 else 0
        empty_bars = total_bars - filled_bars
        progress_bar = "▓" * filled_bars + "░" * empty_bars
        
        question_text += f"\n⏱️ {remaining} сек [{progress_bar}]"
        
        # Rebuild keyboard to keep buttons
        from bot.keyboards import QuestionAnswerKeyboard
        options = {}
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
        bot = Bot(token=config.config.TELEGRAM_BOT_TOKEN)
        bot.edit_message_text(
            chat_id=user_id,
            message_id=message_id,
            text=question_text,
            reply_markup=keyboard
        )
    except Exception as e:
        # Message might be already edited or deleted, ignore
        logger.debug(f"Could not update timer message: {e}")
        return
    
    # Schedule next update if time remaining
    if remaining > 1:
        update_question_timer.apply_async(
            args=[game_id, round_id, round_question_id, user_id, message_id, remaining - 1, time_limit],
            countdown=1
        )
