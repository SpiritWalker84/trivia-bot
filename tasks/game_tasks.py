"""
Game tasks - background tasks for game operations.
"""
from datetime import datetime
import pytz
from celery import Task
from tasks.celery_app import celery_app
from utils.logging import get_logger
from game.engine import GameEngine
from telegram import Bot
from bot.game_notifications import GameNotifications
from database.session import db_session
from database.models import Game, Round, User, Answer, RoundQuestion, GamePlayer
import config
import asyncio

logger = get_logger(__name__)


@celery_app.task(name="tasks.game_tasks.start_game_task")
def start_game_task(game_id: int) -> None:
    """
    Start a game - create first round and send first question.
    
    Args:
        game_id: Game ID
    """
    game_engine = GameEngine()
    if game_engine.start_game(game_id):
        logger.info(f"Game {game_id} started successfully")
        
        # Send start notification
        try:
            bot = Bot(token=config.config.TELEGRAM_BOT_TOKEN)
            notifications = GameNotifications(bot)
            asyncio.run(notifications.send_game_start_notification(game_id))
        except Exception as e:
            logger.error(f"Failed to send start notification: {e}")
        
        # Send first question
        from database.session import db_session
        from database.models import Game, Round, RoundQuestion
        
        with db_session() as session:
            game = session.query(Game).filter(Game.id == game_id).first()
            if not game:
                return
            
            round_obj = session.query(Round).filter(
                Round.game_id == game_id,
                Round.round_number == 1
            ).first()
            
            if round_obj:
                first_question = session.query(RoundQuestion).filter(
                    RoundQuestion.round_id == round_obj.id,
                    RoundQuestion.question_number == 1
                ).first()
                
                if first_question:
                    from tasks.question_sender import send_question_to_players
                    send_question_to_players.delay(
                        game_id, round_obj.id, first_question.id
                    )
    else:
        logger.error(f"Failed to start game {game_id}")


@celery_app.task(name="tasks.game_tasks.finish_round_task")
def finish_round_task(game_id: int, round_number: int) -> None:
    """
    Finish a round and determine eliminated player.
    
    Args:
        game_id: Game ID
        round_number: Round number
    """
    from database.session import db_session
    from database.models import Game, Round
    
    logger.info(f"Finishing round {round_number} for game {game_id}")
    
    # Check if game still exists and is active
    with db_session() as session:
        game = session.query(Game).filter(Game.id == game_id).first()
        if not game:
            logger.warning(f"Game {game_id} not found when trying to finish round {round_number}")
            return
        
        if game.status in ('cancelled', 'finished'):
            logger.info(f"Game {game_id} is {game.status}, skipping round {round_number} finish")
            return
        
        # Check if round is still relevant
        round_obj = session.query(Round).filter(
            Round.game_id == game_id,
            Round.round_number == round_number
        ).first()
        if not round_obj:
            logger.warning(f"Round {round_number} not found for game {game_id}")
            return
        
        # Check if game has moved to a different round
        if game.current_round and game.current_round > round_number:
            logger.info(f"Game {game_id} has moved to round {game.current_round}, skipping old round {round_number} finish")
            return
    
    game_engine = GameEngine()
    eliminated_user_id = game_engine.finish_round(game_id, round_number)
    logger.info(f"Round {round_number} finished, eliminated_user_id={eliminated_user_id}")
    
    # Send round results BEFORE updating current_round to ensure results are sent
    try:
        bot = Bot(token=config.config.TELEGRAM_BOT_TOKEN)
        notifications = GameNotifications(bot)
        logger.info(f"Attempting to send round {round_number} results for game {game_id}")
        asyncio.run(notifications.send_round_results(
            game_id, round_number, eliminated_user_id
        ))
        logger.info(f"Round results sent successfully for game {game_id}, round {round_number}")
    except Exception as e:
        logger.error(f"Failed to send round results for game {game_id}, round {round_number}: {e}", exc_info=True)
    
    # Check if game should continue
    with db_session() as session:
        game = session.query(Game).filter(Game.id == game_id).first()
        if not game:
            logger.error(f"Game {game_id} not found after finishing round {round_number}")
            return
        
        # Update game current_round
        game.current_round = round_number
        session.commit()
        
        alive_count = len([gp for gp in game.players if not gp.is_eliminated])
        logger.info(f"Game {game_id} after round {round_number}: {alive_count} players alive, ROUNDS_PER_GAME={config.config.ROUNDS_PER_GAME}")
        
        if alive_count <= 1:
            # Game finished
            logger.info(f"Game {game_id}: Only {alive_count} player(s) alive, finishing game")
            finish_game_task.delay(game_id)
        elif round_number < config.config.ROUNDS_PER_GAME:
            # Continue to next round after 30 second pause
            next_round = round_number + 1
            logger.info(f"Game {game_id}: Continuing to round {next_round} (current: {round_number}, max: {config.config.ROUNDS_PER_GAME}) after 30 second pause")
            
            # Send pause notification
            try:
                bot = Bot(token=config.config.TELEGRAM_BOT_TOKEN)
                notifications = GameNotifications(bot)
                asyncio.run(notifications.send_round_pause_notification(
                    game_id, next_round
                ))
                logger.info(f"Pause notification sent for game {game_id}, next round {next_round}")
            except Exception as e:
                logger.error(f"Failed to send pause notification: {e}", exc_info=True)
            
            # Schedule next round after 30 seconds
            start_next_round_task.apply_async(
                args=[game_id, next_round],
                countdown=30  # 30 second pause to let players review results
            )
        else:
            # Last round finished
            logger.info(f"Game {game_id}: Last round ({round_number}) finished, finishing game")
            finish_game_task.delay(game_id)


@celery_app.task(name="tasks.game_tasks.start_next_round_task")
def start_next_round_task(game_id: int, round_number: int) -> None:
    """
    Start next round - create round and send first question.
    
    Args:
        game_id: Game ID
        round_number: Next round number
    """
    from database.session import db_session
    from database.models import Game, Round, RoundQuestion
    from game.engine import GameEngine
    
    logger.info(f"Starting round {round_number} for game {game_id}")
    game_engine = GameEngine()
    
    with db_session() as session:
        game = session.query(Game).filter(Game.id == game_id).first()
        if not game:
            logger.error(f"Game {game_id} not found when starting round {round_number}")
            return
        
        # Create round
        round_obj = game_engine._create_round(
            session, game_id, round_number, game.theme_id
        )
        
        if not round_obj:
            logger.error(f"Failed to create round {round_number} for game {game_id}")
            return
        
        logger.info(f"Round {round_number} created for game {game_id}, round_id={round_obj.id}")
        game.current_round = round_number
        round_obj.status = 'in_progress'
        round_obj.started_at = datetime.now(pytz.UTC)
        session.commit()
        
        # Send first question
        first_question = session.query(RoundQuestion).filter(
            RoundQuestion.round_id == round_obj.id,
            RoundQuestion.question_number == 1
        ).first()
        
        if first_question:
            logger.info(f"Sending first question {first_question.id} for round {round_number} in game {game_id}")
            from tasks.question_sender import send_question_to_players
            send_question_to_players.delay(
                game_id, round_obj.id, first_question.id
            )
        else:
            logger.error(f"First question not found for round {round_number} in game {game_id}")


@celery_app.task(name="tasks.game_tasks.check_early_victory_task")
def check_early_victory_task(
    game_id: int,
    round_id: int,
    round_question_id: int,
    user_id: int,
    selected_option: str,
    is_correct: bool,
    answer_time: float
) -> None:
    """
    Check for early victory after answer (only in final round).
    Answer is already saved, so we just check the condition.
    
    Args:
        game_id: Game ID
        round_id: Round ID
        round_question_id: Round question ID (not used, but kept for compatibility)
        user_id: User ID who answered
        selected_option: Selected option (not used, but kept for compatibility)
        is_correct: Whether answer is correct (not used, but kept for compatibility)
        answer_time: Time taken to answer (not used, but kept for compatibility)
    """
    game_engine = GameEngine()
    
    # Check for early victory (answer is already saved in callback handler)
    winner_user_id = game_engine.check_early_victory(game_id, round_id)
    
    if winner_user_id:
        logger.info(f"Early victory in game {game_id}! Winner: {winner_user_id}")
        # Finish game
        game_engine.finish_game(game_id, early_victory=True, winner_user_id=winner_user_id)
        # Send notification
        send_early_victory_notification_task.delay(
            game_id=game_id,
            round_id=round_id,
            winner_user_id=winner_user_id
        )


@celery_app.task(name="tasks.game_tasks.send_early_victory_notification_task")
def send_early_victory_notification_task(game_id: int, round_id: int, winner_user_id: int) -> None:
    """
    Send early victory notification.
    
    Args:
        game_id: Game ID
        round_id: Round ID
        winner_user_id: Winner user ID
    """
    from database.models import User, Answer, RoundQuestion, GamePlayer
    from bot.game_notifications import GameNotifications
    
    try:
        bot = Bot(token=config.config.TELEGRAM_BOT_TOKEN)
        notifications = GameNotifications(bot)
        
        with db_session() as session:
            winner_user = session.query(User).filter(User.id == winner_user_id).first()
            
            # Get scores
            winner_answers = session.query(Answer).filter(
                Answer.game_id == game_id,
                Answer.round_id == round_id,
                Answer.user_id == winner_user_id
            ).all()
            winner_score = sum(1 for a in winner_answers if a.is_correct)
            
            # Get alive players
            game = session.query(Game).filter(Game.id == game_id).first()
            if not game:
                return
            
            alive_players = session.query(GamePlayer).filter(
                GamePlayer.game_id == game_id,
                GamePlayer.is_eliminated == False
            ).all()
            
            loser = next((p for p in alive_players if p.user_id != winner_user_id), None)
            loser_score = 0
            if loser:
                loser_answers = session.query(Answer).filter(
                    Answer.game_id == game_id,
                    Answer.round_id == round_id,
                    Answer.user_id == loser.user_id
                ).all()
                loser_score = sum(1 for a in loser_answers if a.is_correct)
            
            # Count remaining questions
            total_questions = session.query(RoundQuestion).filter(
                RoundQuestion.round_id == round_id
            ).count()
            answered_question_ids = set()
            for gp in alive_players:
                answers = session.query(Answer).filter(
                    Answer.round_id == round_id,
                    Answer.user_id == gp.user_id
                ).all()
                answered_question_ids.update(a.round_question_id for a in answers)
            questions_remaining = total_questions - len(answered_question_ids)
        
        # Send notification
        asyncio.run(notifications.send_early_victory_notification(
            game_id=game_id,
            winner_user_id=winner_user_id,
            leader_score=winner_score,
            loser_score=loser_score,
            questions_remaining=questions_remaining
        ))
        
        # Send final results
        with db_session() as session2:
            round_obj = session2.query(Round).filter(Round.id == round_id).first()
            if round_obj:
                asyncio.run(notifications.send_round_results(
                    game_id=game_id,
                    round_number=round_obj.round_number
                ))
            
    except Exception as e:
        logger.error(f"Error sending early victory notification: {e}", exc_info=True)


@celery_app.task(name="tasks.game_tasks.finish_game_task")
def finish_game_task(game_id: int) -> None:
    """
    Finish a game and update ratings.
    
    Args:
        game_id: Game ID
    """
    game_engine = GameEngine()
    if game_engine.finish_game(game_id):
        logger.info(f"Game {game_id} finished successfully")
    else:
        logger.error(f"Failed to finish game {game_id}")
