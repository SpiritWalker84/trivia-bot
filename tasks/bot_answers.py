"""
Bot answers - automatic bot responses to questions.
"""
from datetime import datetime
import pytz
from celery import Task
from database.session import db_session
from database.models import Game, GamePlayer, Round, RoundQuestion, Answer, User
from tasks.celery_app import celery_app
from game.bots import BotAI, BotDifficulty
from game.engine import GameEngine
from utils.logging import get_logger
import config
import random
import asyncio

logger = get_logger(__name__)


@celery_app.task(name="tasks.bot_answers.process_bot_answers")
def process_bot_answers(game_id: int, round_id: int, round_question_id: int) -> None:
    """
    Process bot answers for a question.
    Bots answer with random delay based on their difficulty.
    
    Args:
        game_id: Game ID
        round_id: Round ID
        round_question_id: Round question ID
    """
    from database.models import Question
    
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
        
        question = session.query(Question).filter(
            Question.id == round_question.question_id
        ).first()
        if not question:
            return
        
        # Get all bot players
        bot_players = [
            gp for gp in game.players
            if gp.is_bot and not gp.is_eliminated
        ]
        
        # Process each bot
        for game_player in bot_players:
            # Check if bot already answered
            existing_answer = session.query(Answer).filter(
                Answer.round_question_id == round_question_id,
                Answer.user_id == game_player.user_id
            ).first()
            
            if existing_answer:
                continue
            
            # Get bot difficulty - prefer game's difficulty setting over player's stored difficulty
            # This fixes cases where games were created before the fix
            game_difficulty = None
            if game and game.bot_difficulty:
                game_difficulty = game.bot_difficulty
                # If player's difficulty doesn't match game's, fix it
                if game_player.bot_difficulty != game_difficulty:
                    logger.warning(
                        f"Bot {game_player.user_id} (player {game_player.id}) has wrong difficulty "
                        f"'{game_player.bot_difficulty}', should be '{game_difficulty}'. Fixing..."
                    )
                    game_player.bot_difficulty = game_difficulty
                    session.commit()
            
            # Use game difficulty if available, otherwise fall back to player's stored difficulty
            difficulty_str = game_difficulty or game_player.bot_difficulty or 'novice'
            try:
                difficulty = BotDifficulty(difficulty_str)
            except ValueError:
                difficulty = BotDifficulty.NOVICE
                difficulty_str = 'novice'
            
            # Create bot AI
            bot_ai = BotAI(difficulty)
            
            # Log bot difficulty for debugging
            logger.info(
                f"Bot {game_player.user_id} (player {game_player.id}) using difficulty: {difficulty_str} "
                f"(accuracy: {bot_ai.accuracy:.1%}, game_difficulty: {game.bot_difficulty if game else None})"
            )
            
            # Get available options (after shuffling)
            options = []
            if round_question.shuffled_options:
                # Use shuffled options - all new positions are available
                options = list(round_question.shuffled_options.keys())
                # Use shuffled correct option
                correct_option = round_question.correct_option_shuffled or question.correct_option
            else:
                # Fallback to original options (backward compatibility)
                if question.option_a:
                    options.append('A')
                if question.option_b:
                    options.append('B')
                if question.option_c:
                    options.append('C')
                if question.option_d:
                    options.append('D')
                correct_option = question.correct_option
            
            bot_answer = bot_ai.generate_answer(
                question.id,
                correct_option,
                options
            )
            
            # Calculate answer time (with delay)
            from decimal import Decimal
            if round_question.displayed_at:
                answer_time = (datetime.now(pytz.UTC) - round_question.displayed_at).total_seconds()
                # Add bot delay
                answer_time += bot_answer['delay_seconds']
            else:
                answer_time = bot_answer['delay_seconds']
            
            # Convert to Decimal for database compatibility
            answer_time_decimal = Decimal(str(answer_time))
            
            # Save answer
            answer = Answer(
                game_id=game_id,
                round_id=round_id,
                round_question_id=round_question_id,
                user_id=game_player.user_id,
                game_player_id=game_player.id,
                selected_option=bot_answer['selected_option'],
                is_correct=bot_answer['is_correct'],
                answer_time=answer_time_decimal,
                answered_at=datetime.now(pytz.UTC)
            )
            session.add(answer)
            
            # Update game player stats
            if bot_answer['is_correct']:
                game_player.total_score += 1
            game_player.total_time += answer_time_decimal
        
        session.commit()
        
        # Check for early victory after bot answers
        game_engine = GameEngine()
        winner_user_id = game_engine.check_early_victory(game_id, round_id)
        
        if winner_user_id:
            logger.info(f"Early victory detected after bot answers! Winner: {winner_user_id}")
            game_engine.finish_game(game_id, early_victory=True, winner_user_id=winner_user_id)
            
            # Send notifications
            try:
                from telegram import Bot
                from bot.game_notifications import GameNotifications
                
                bot = Bot(token=config.config.TELEGRAM_BOT_TOKEN)
                notifications = GameNotifications(bot)
                asyncio.run(notifications.send_early_victory_notification(
                    game_id, winner_user_id, 0, 0, 0
                ))
            except Exception as e:
                logger.error(f"Failed to send early victory notification: {e}")


@celery_app.task(name="tasks.bot_answers.send_next_question")
def send_next_question(game_id: int, round_id: int, current_question_number: int) -> None:
    """
    Send next question in round after previous question time expires.
    
    Args:
        game_id: Game ID
        round_id: Round ID
        current_question_number: Current question number
    """
    from database.models import RoundQuestion, Round, Game
    from sqlalchemy import func
    
    logger.info(
        f"send_next_question CALLED: game_id={game_id}, round_id={round_id}, "
        f"current_question_number={current_question_number}"
    )
    
    try:
        with db_session() as session:
            # CRITICAL: Lock the round to prevent parallel execution
            # This ensures only one send_next_question task can run at a time for this round
            # If another task already has the lock, this will raise OperationalError
            from sqlalchemy.exc import OperationalError
            try:
                round_obj = session.query(Round).filter(
                    Round.id == round_id
                ).with_for_update(nowait=True).first()
            except OperationalError as e:
                # Another task is already processing this round - skip this one
                logger.info(
                    f"Round {round_id} is locked by another task (likely processing question {current_question_number + 1}). "
                    f"Skipping this duplicate call."
                )
                return
            
            if not round_obj:
                logger.warning(f"Round {round_id} not found, skipping next question")
                return
            
            if round_obj.status != 'in_progress':
                logger.warning(f"Round {round_id} is not in_progress (status: {round_obj.status}), skipping next question")
                return
            
            # Verify game is still active (without lock, just check)
            game = session.query(Game).filter(Game.id == game_id).first()
            if not game or game.status != 'in_progress':
                logger.warning(f"Game {game_id} is not in_progress, skipping next question")
                return
            
            # Verify current question exists and is correct
            current_question = session.query(RoundQuestion).filter(
                RoundQuestion.round_id == round_id,
                RoundQuestion.question_number == current_question_number
            ).first()
            
            if not current_question:
                logger.error(f"Current question {current_question_number} not found in round {round_id}")
                return
            
            # Calculate next question number
            next_question_number = current_question_number + 1
            
            # Find the last question that was actually displayed (to prevent skipping)
            # This check is critical to prevent out-of-order question sending
            last_displayed_question = session.query(RoundQuestion).filter(
                RoundQuestion.round_id == round_id,
                RoundQuestion.displayed_at.isnot(None)
            ).order_by(RoundQuestion.question_number.desc()).first()
            
            if last_displayed_question:
                last_displayed_number = last_displayed_question.question_number
                
                # CRITICAL CHECK: Ensure we're sending questions in strict sequence
                # If next question (or later) was already displayed, this is a duplicate/out-of-order call
                if last_displayed_number >= next_question_number:
                    logger.warning(
                        f"DUPLICATE/OUT-OF-ORDER: Current question is {current_question_number}, "
                        f"next should be {next_question_number}, but question {last_displayed_number} "
                        f"was already displayed. This task is obsolete, skipping."
                    )
                    return
                
                # Safety check: if last displayed is significantly behind current, something is wrong
                # But allow if last displayed is current (normal case) or one behind (possible timing issue)
                if last_displayed_number < current_question_number - 1:
                    logger.warning(
                        f"SEQUENCE GAP: Current question is {current_question_number}, "
                        f"but last displayed is {last_displayed_number} (gap of {current_question_number - last_displayed_number}). "
                        f"This may indicate a problem, but continuing anyway."
                    )
                    # Don't return - continue processing, as this might be a timing issue
            
            # Get next question
            next_question = session.query(RoundQuestion).filter(
                RoundQuestion.round_id == round_id,
                RoundQuestion.question_number == next_question_number
            ).first()
            
            if not next_question:
                # Last question in round - finish round
                from tasks.game_tasks import finish_round_task
                logger.info(f"Last question ({current_question_number}) answered in round {round_obj.round_number} for game {game_id}, scheduling finish_round_task")
                finish_round_task.apply_async(
                    args=[game_id, round_obj.round_number],
                    countdown=2  # Small delay to ensure all answers are processed
                )
                return
            
            # Final check: verify next question hasn't been displayed yet
            # Refresh from database to get latest state (important for race conditions)
            session.refresh(next_question)
            if next_question.displayed_at:
                logger.warning(
                    f"Question {next_question_number} was already sent "
                    f"(displayed_at: {next_question.displayed_at}), skipping duplicate send"
                )
                return
            
            # Send next question with a short delay (1-2 seconds)
            # This ensures all processing is complete but keeps the game pace fast
            delay = 2  # 2 seconds delay between questions
            logger.info(f"Scheduling next question {next_question_number} with {delay}s delay after question {current_question_number}")
            
            from tasks.question_sender import send_question_to_players
            send_question_to_players.apply_async(
                args=[game_id, round_id, next_question.id],
                countdown=delay
            )
            
            # Process bot answers for next question (with additional delay)
            process_bot_answers.apply_async(
                args=[game_id, round_id, next_question.id],
                countdown=4  # Delay to let question be sent first
            )
            
            # Commit the transaction to release the lock
            session.commit()
            
    except Exception as e:
        logger.error(f"Error in send_next_question for game {game_id}, round {round_id}, question {current_question_number}: {e}", exc_info=True)