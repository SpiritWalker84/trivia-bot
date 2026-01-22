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
    
    game_engine = GameEngine()
    eliminated_user_id = game_engine.finish_round(game_id, round_number)
    
    # Send round results
    try:
        bot = Bot(token=config.config.TELEGRAM_BOT_TOKEN)
        notifications = GameNotifications(bot)
        asyncio.run(notifications.send_round_results(
            game_id, round_number, eliminated_user_id
        ))
    except Exception as e:
        logger.error(f"Failed to send round results: {e}")
    
    if eliminated_user_id == -1:
        logger.info(f"Game {game_id} round {round_number}: Tie-break needed")
        # TODO: Trigger tie-break
    elif eliminated_user_id:
        logger.info(f"Game {game_id} round {round_number}: Player {eliminated_user_id} eliminated")
        
        # Check if game should continue
        with db_session() as session:
            game = session.query(Game).filter(Game.id == game_id).first()
            if not game:
                return
            
            alive_count = len([gp for gp in game.players if not gp.is_eliminated])
            
            if alive_count <= 1:
                # Game finished
                finish_game_task.delay(game_id)
            elif round_number < config.config.ROUNDS_PER_GAME:
                # Continue to next round
                start_next_round_task.delay(game_id, round_number + 1)
            else:
                # Last round finished
                finish_game_task.delay(game_id)
    else:
        logger.warning(f"Game {game_id} round {round_number}: No player eliminated")


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
    
    game_engine = GameEngine()
    
    with db_session() as session:
        game = session.query(Game).filter(Game.id == game_id).first()
        if not game:
            return
        
        # Create round
        round_obj = game_engine._create_round(
            session, game_id, round_number, game.theme_id
        )
        
        if not round_obj:
            logger.error(f"Failed to create round {round_number} for game {game_id}")
            return
        
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
            from tasks.question_sender import send_question_to_players
            send_question_to_players.delay(
                game_id, round_obj.id, first_question.id
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
