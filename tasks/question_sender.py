"""
Question sender task - sends questions to players and handles timers.
"""
from datetime import datetime, timedelta
import pytz
from celery import Task
from database.session import db_session
from database.models import Game, Round, RoundQuestion
from tasks.celery_app import celery_app
from utils.logging import get_logger
import config

logger = get_logger(__name__)


@celery_app.task(name="tasks.question_sender.send_question_to_players")
def send_question_to_players(game_id: int, round_id: int, round_question_id: int) -> None:
    """
    Send question to all players in game.
    
    This task is called when it's time to send a question to players.
    """
    from telegram import Bot
    from bot.game_notifications import GameNotifications
    
    # Update round status to in_progress if this is the first question
    with db_session() as session:
        round_obj = session.query(Round).filter(Round.id == round_id).first()
        if round_obj and round_obj.status == 'not_started':
            round_obj.status = 'in_progress'
            if not round_obj.started_at:
                round_obj.started_at = datetime.now(pytz.UTC)
            session.commit()
    
    try:
        bot = Bot(token=config.config.TELEGRAM_BOT_TOKEN)
        notifications = GameNotifications(bot)
        
        # Send question to all players (async, but we're in sync context)
        import asyncio
        results = asyncio.run(
            notifications.send_question_to_all_players(
                game_id, round_id, round_question_id
            )
        )
        
        # Process bot answers (with small delay)
        from tasks.bot_answers import process_bot_answers
        process_bot_answers.apply_async(
            args=[game_id, round_id, round_question_id],
            countdown=1  # Small delay to let question be sent first
        )
        
        # Get displayed_at time to calculate exact delay
        with db_session() as session:
            round_question = session.query(RoundQuestion).filter(
                RoundQuestion.id == round_question_id
            ).first()
            
            if round_question and round_question.displayed_at:
                # Calculate exact delay from displayed_at
                elapsed = (datetime.now(pytz.UTC) - round_question.displayed_at).total_seconds()
                remaining_time = max(0, config.config.QUESTION_TIME_LIMIT - elapsed)
                # Add 1 second buffer to ensure timer reaches 0
                delay = int(remaining_time) + 1
            else:
                # Fallback: use full time limit + buffer
                delay = config.config.QUESTION_TIME_LIMIT + 1
        
        # Schedule answer collection after time limit (with buffer to let timer reach 0)
        collect_answers.apply_async(
            args=[game_id, round_id, round_question_id],
            countdown=delay
        )
        logger.info(f"Scheduled collect_answers for question {round_question_id} with delay {delay} seconds")
        
        logger.info(f"Question {round_question_id} sent to players in game {game_id}")
        
    except Exception as e:
        logger.error(f"Error sending question {round_question_id}: {e}")


@celery_app.task(name="tasks.question_sender.collect_answers")
def collect_answers(game_id: int, round_id: int, round_question_id: int) -> None:
    """
    Collect answers after time limit expires.
    Mark unanswered questions as incorrect.
    """
    from database.models import Answer, GamePlayer, User, RoundQuestion
    from game.engine import GameEngine
    
    with db_session() as session:
        round_obj = session.query(Round).filter(Round.id == round_id).first()
        if not round_obj:
            return
        
        game = session.query(Game).filter(Game.id == game_id).first()
        if not game:
            return
        
        round_question = session.query(RoundQuestion).filter(
            RoundQuestion.id == round_question_id
        ).first()
        if not round_question:
            return
        
        # Get question to check correct answer
        from database.models import Question
        question = session.query(Question).filter(
            Question.id == round_question.question_id
        ).first()
        if not question:
            return
        
        # Get all alive players
        alive_players = [
            gp for gp in game.players
            if not gp.is_eliminated
        ]
        
        # For players who didn't answer, mark as incorrect with max time
        for game_player in alive_players:
            if game_player.is_bot:
                # Bots answer automatically (handled separately)
                continue
            
            existing_answer = session.query(Answer).filter(
                Answer.round_question_id == round_question_id,
                Answer.user_id == game_player.user_id
            ).first()
            
            if not existing_answer:
                # No answer - mark as incorrect
                from decimal import Decimal
                max_time = Decimal(str(config.config.QUESTION_TIME_LIMIT))
                answer = Answer(
                    game_id=game_id,
                    round_id=round_id,
                    round_question_id=round_question_id,
                    user_id=game_player.user_id,
                    game_player_id=game_player.id,
                    selected_option=None,
                    is_correct=False,
                    answer_time=max_time,  # Max time
                    answered_at=datetime.now(pytz.UTC)
                )
                session.add(answer)
                game_player.total_time += max_time
        
        session.commit()
        
        # Send next question or finish round
        from tasks.bot_answers import send_next_question
        send_next_question.delay(
            game_id, round_id, round_question.question_number
        )
