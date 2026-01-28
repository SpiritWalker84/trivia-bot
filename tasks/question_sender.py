"""
Question sender task - sends questions to players and handles timers.
"""
from datetime import datetime, timedelta
import pytz
from celery import Task
import asyncio
from telegram import Bot
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
    logger.info(
        f"send_question_to_players CALLED: game_id={game_id}, round_id={round_id}, round_question_id={round_question_id}"
    )
    
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
        # Wait a bit for displayed_at to be set
        import time
        time.sleep(0.5)  # Small delay to ensure displayed_at is set
        
        # Check if question was actually sent (displayed_at is set)
        # If not, retry sending after a delay
        question_number = None
        question_was_sent = False
        with db_session() as session:
            round_question = session.query(RoundQuestion).filter(
                RoundQuestion.id == round_question_id
            ).first()
            
            if round_question:
                question_number = round_question.question_number
                session.refresh(round_question)  # Get latest displayed_at status
                
                if round_question.displayed_at:
                    question_was_sent = True
                    # Calculate exact delay from displayed_at
                    elapsed = (datetime.now(pytz.UTC) - round_question.displayed_at).total_seconds()
                    remaining_time = max(0, config.config.QUESTION_TIME_LIMIT - elapsed)
                    # Add 3 second buffer to ensure timer reaches 0 and all updates complete
                    # Ensure minimum delay of at least QUESTION_TIME_LIMIT seconds
                    delay = max(int(remaining_time) + 3, config.config.QUESTION_TIME_LIMIT + 3)
                    logger.info(f"Using displayed_at for timing: elapsed={elapsed:.2f}s, remaining={remaining_time:.2f}s, delay={delay}s")
                else:
                    # Question was not sent (likely due to Flood control)
                    # Retry sending after a delay
                    logger.warning(
                        f"Question {round_question_id} (question_number={question_number}) was not sent "
                        f"(displayed_at is None). This might be due to Flood control. Retrying in 5 seconds..."
                    )
                    # Retry sending after 5 seconds (exponential backoff would be better, but simple retry for now)
                    send_question_to_players.apply_async(
                        args=[game_id, round_id, round_question_id],
                        countdown=5
                    )
                    return  # Don't schedule collect_answers yet
            else:
                # Fallback: use full time limit + 3 second buffer
                delay = config.config.QUESTION_TIME_LIMIT + 3
                logger.warning(f"RoundQuestion {round_question_id} not found, using fallback delay {delay}s")
        
        # Only schedule collect_answers if question was successfully sent
        if question_was_sent:
            # Schedule answer collection after time limit (with buffer to let timer reach 0)
            collect_answers.apply_async(
                args=[game_id, round_id, round_question_id],
                countdown=delay
            )
            logger.info(f"Scheduled collect_answers for question {round_question_id} with delay {delay} seconds")
            
            # Log which question was actually sent
            if question_number:
                logger.info(
                    f"send_question_to_players: Question {round_question_id} (question_number={question_number}) "
                    f"sent to players in game {game_id}, round_id={round_id}"
                )
        else:
            logger.warning(
                f"send_question_to_players: Question {round_question_id} (question_number={question_number}) "
                f"was not sent successfully. Retry scheduled."
            )
        
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
        
        # Get all alive players (exclude those who left the game)
        alive_players = [
            gp for gp in game.players
            if not gp.is_eliminated and not gp.left_game
        ]
        
        # For players who didn't answer, mark as incorrect with max time
        timed_out_user_ids = []
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
                timed_out_user_ids.append(game_player.user_id)
        
        session.commit()
        logger.info(
            f"collect_answers: round_question_id={round_question_id} timed_out_user_ids={timed_out_user_ids}"
        )

        # Notify users who didn't answer with the correct option
        if timed_out_user_ids:
            correct_option_display = round_question.correct_option_shuffled or question.correct_option
            logger.info(
                f"collect_answers: sending timeout feedback for round_question_id={round_question_id} "
                f"correct_option={correct_option_display}"
            )
            try:
                bot = Bot(token=config.config.TELEGRAM_BOT_TOKEN)
                for user_id in timed_out_user_ids:
                    try:
                        # Use a dedicated event loop to avoid "event loop is closed" issues in workers
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(
                            bot.send_message(
                                chat_id=user_id,
                                text=f"⏰ Время вышло. Правильный ответ: {correct_option_display}"
                            )
                        )
                        loop.close()
                    except Exception as send_error:
                        logger.warning(
                            f"Failed to send timeout feedback to user {user_id}: {send_error}"
                        )
            except Exception as e:
                logger.warning(f"Failed to create bot for timeout feedback: {e}")
        
        # Check if next question was already scheduled by checking if it's already displayed
        # This prevents duplicate scheduling when collect_answers is called multiple times
        next_question_number = round_question.question_number + 1
        next_question = session.query(RoundQuestion).filter(
            RoundQuestion.round_id == round_id,
            RoundQuestion.question_number == next_question_number
        ).first()
        
        if next_question and next_question.displayed_at:
            # Next question was already sent - don't schedule again
            logger.info(
                f"collect_answers: Question {round_question.question_number} finished, "
                f"but next question {next_question_number} was already sent. Skipping duplicate scheduling."
            )
            return
        
        # Send next question or finish round
        # Add a small delay to ensure all answers are processed and committed
        from tasks.bot_answers import send_next_question
        logger.info(
            f"collect_answers: Question {round_question.question_number} finished, "
            f"scheduling send_next_question for game {game_id}, round {round_id}, "
            f"current_question_number={round_question.question_number}"
        )
        send_next_question.apply_async(
            args=[game_id, round_id, round_question.question_number],
            countdown=1  # Small delay to ensure database commit is complete
        )
