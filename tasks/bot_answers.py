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
            
            # Get bot difficulty
            difficulty_str = game_player.bot_difficulty or 'novice'
            try:
                difficulty = BotDifficulty(difficulty_str)
            except ValueError:
                difficulty = BotDifficulty.NOVICE
            
            # Create bot AI
            bot_ai = BotAI(difficulty)
            
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
    from database.models import RoundQuestion
    from tasks.question_sender import send_question_to_players
    
    with db_session() as session:
        # Check if there are more questions
        next_question_number = current_question_number + 1
        
        next_question = session.query(RoundQuestion).filter(
            RoundQuestion.round_id == round_id,
            RoundQuestion.question_number == next_question_number
        ).first()
        
        if next_question:
            # Send next question with a short delay (1-2 seconds)
            # This ensures all processing is complete but keeps the game pace fast
            delay = 2  # 2 seconds delay between questions
            logger.info(f"Scheduling next question {next_question_number} with {delay}s delay after question {current_question_number}")
            send_question_to_players.apply_async(
                args=[game_id, round_id, next_question.id],
                countdown=delay
            )
            
            # Process bot answers for next question (with additional delay)
            from tasks.bot_answers import process_bot_answers
            process_bot_answers.apply_async(
                args=[game_id, round_id, next_question.id],
                countdown=4  # Delay to let question be sent first
            )
        else:
            # Last question in round - finish round
            from tasks.game_tasks import finish_round_task
            from database.models import Round
            round_obj = session.query(Round).filter(Round.id == round_id).first()
            if round_obj:
                logger.info(f"Last question ({current_question_number}) answered in round {round_obj.round_number} for game {game_id}, scheduling finish_round_task")
                finish_round_task.apply_async(
                    args=[game_id, round_obj.round_number],
                    countdown=2  # Small delay to ensure all answers are processed
                )
            else:
                logger.error(f"Round {round_id} not found when trying to finish round")