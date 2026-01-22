"""
Game handlers - handle game-related user actions (answers, votes, etc.)
"""
from typing import Optional
from datetime import datetime
import pytz
from telegram import Update
from telegram.ext import ContextTypes
from database.session import db_session
from database.models import Game, GamePlayer, Round, RoundQuestion, Answer, User, GameVote
from database.queries import UserQueries, GameQueries
from game.engine import GameEngine
from bot.game_notifications import GameNotifications
from utils.logging import get_logger
import config

logger = get_logger(__name__)


async def handle_answer(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    round_question_id: int,
    selected_option: str
) -> None:
    """
    Handle player's answer to a question.
    
    Args:
        update: Telegram update
        context: Bot context
        round_question_id: Round question ID
        selected_option: Selected option ('A', 'B', 'C', 'D')
    """
    query = update.callback_query
    user = update.effective_user
    
    if not user:
        await query.answer("Ошибка: пользователь не найден", show_alert=True)
        return
    
    with db_session() as session:
        # Get user from database
        db_user = UserQueries.get_user_by_telegram_id(session, user.id)
        if not db_user:
            await query.answer("Ошибка: пользователь не найден в базе", show_alert=True)
            return
        
        # Get round question
        round_question = session.query(RoundQuestion).filter(
            RoundQuestion.id == round_question_id
        ).first()
        
        if not round_question:
            await query.answer("Ошибка: вопрос не найден", show_alert=True)
            return
        
        # Check if question is still active
        round_obj = session.query(Round).filter(Round.id == round_question.round_id).first()
        if not round_obj or round_obj.status != 'in_progress':
            await query.answer("Время ответа истекло", show_alert=False)
            return
        
        # Check if user already answered
        existing_answer = session.query(Answer).filter(
            Answer.round_question_id == round_question_id,
            Answer.user_id == db_user.id
        ).first()
        
        if existing_answer:
            await query.answer("Вы уже ответили на этот вопрос", show_alert=False)
            return
        
        # Get question to check correct answer
        from database.models import Question
        question = session.query(Question).filter(
            Question.id == round_question.question_id
        ).first()
        
        if not question:
            await query.answer("Ошибка: вопрос не найден", show_alert=True)
            return
        
        # Calculate answer time
        if round_question.displayed_at:
            answer_time = (datetime.now(pytz.UTC) - round_question.displayed_at).total_seconds()
        else:
            answer_time = 0.0
        
        # Check if answer is correct
        is_correct = (selected_option.upper() == question.correct_option.upper())
        
        # Get game and game_player
        game = session.query(Game).filter(Game.id == round_obj.game_id).first()
        if not game:
            await query.answer("Ошибка: игра не найдена", show_alert=True)
            return
        
        game_player = session.query(GamePlayer).filter(
            GamePlayer.game_id == game.id,
            GamePlayer.user_id == db_user.id
        ).first()
        
        if not game_player or game_player.is_eliminated:
            await query.answer("Вы не участвуете в этой игре", show_alert=True)
            return
        
        # Save answer
        answer = Answer(
            game_id=game.id,
            round_id=round_obj.id,
            round_question_id=round_question_id,
            user_id=db_user.id,
            game_player_id=game_player.id,
            selected_option=selected_option.upper(),
            is_correct=is_correct,
            answer_time=answer_time,
            answered_at=datetime.now(pytz.UTC)
        )
        session.add(answer)
        
        # Update game player stats
        if is_correct:
            game_player.total_score += 1
        game_player.total_time += answer_time
        
        session.flush()
        
        # Check for early victory (only in final round)
        game_engine = GameEngine()
        early_victory_result = game_engine.process_answer_and_check_early_victory(
            game_id=game.id,
            round_id=round_obj.id,
            round_question_id=round_question_id,
            user_id=db_user.id,
            selected_option=selected_option.upper(),
            is_correct=is_correct,
            answer_time=answer_time
        )
        
        session.commit()
        
        # Respond to user
        if is_correct:
            await query.answer("✅ Правильно!", show_alert=False)
        else:
            await query.answer("❌ Неправильно", show_alert=False)
        
        # Handle early victory
        if early_victory_result['early_victory']:
            logger.info(f"Early victory in game {game.id}! Winner: {early_victory_result['winner_user_id']}")
            
            # Send notifications
            bot = context.bot
            notifications = GameNotifications(bot)
            
            # Get winner info for notification
            with db_session() as session:
                winner_user = session.query(User).filter(
                    User.id == early_victory_result['winner_user_id']
                ).first()
                
                # Get scores
                winner_answers = session.query(Answer).filter(
                    Answer.game_id == game.id,
                    Answer.round_id == round_obj.id,
                    Answer.user_id == early_victory_result['winner_user_id']
                ).all()
                winner_score = sum(1 for a in winner_answers if a.is_correct)
                
                alive_players = [gp for gp in game.players if not gp.is_eliminated]
                loser = next((p for p in alive_players if p.user_id != early_victory_result['winner_user_id']), None)
                loser_score = 0
                if loser:
                    loser_answers = session.query(Answer).filter(
                        Answer.game_id == game.id,
                        Answer.round_id == round_obj.id,
                        Answer.user_id == loser.user_id
                    ).all()
                    loser_score = sum(1 for a in loser_answers if a.is_correct)
                
                # Count remaining questions
                total_questions = session.query(RoundQuestion).filter(
                    RoundQuestion.round_id == round_obj.id
                ).count()
                answered_question_ids = set()
                for gp in alive_players:
                    answers = session.query(Answer).filter(
                        Answer.round_id == round_obj.id,
                        Answer.user_id == gp.user_id
                    ).all()
                    answered_question_ids.update(a.round_question_id for a in answers)
                questions_remaining = total_questions - len(answered_question_ids)
            
            await notifications.send_early_victory_notification(
                game_id=game.id,
                winner_user_id=early_victory_result['winner_user_id'],
                leader_score=winner_score,
                loser_score=loser_score,
                questions_remaining=questions_remaining
            )
            
            # Send final results
            await notifications.send_round_results(
                game_id=game.id,
                round_number=round_obj.round_number
            )


async def handle_vote(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    game_id: int,
    vote: str
) -> None:
    """
    Handle game vote (start_now or wait_more).
    
    Args:
        update: Telegram update
        context: Bot context
        game_id: Game ID
        vote: 'start_now' or 'wait_more'
    """
    query = update.callback_query
    user = update.effective_user
    
    if not user:
        await query.answer("Ошибка: пользователь не найден", show_alert=True)
        return
    
    with db_session() as session:
        # Get user from database
        db_user = UserQueries.get_user_by_telegram_id(session, user.id)
        if not db_user:
            await query.answer("Ошибка: пользователь не найден в базе", show_alert=True)
            return
        
        # Get game
        game = session.query(Game).filter(Game.id == game_id).first()
        if not game:
            await query.answer("Игра не найдена", show_alert=True)
            return
        
        # Check if game is in voting state
        if game.status != 'pre_start':
            await query.answer("Голосование уже завершено", show_alert=False)
            return
        
        # Check if user is in game
        game_player = session.query(GamePlayer).filter(
            GamePlayer.game_id == game_id,
            GamePlayer.user_id == db_user.id
        ).first()
        
        if not game_player:
            await query.answer("Вы не участвуете в этой игре", show_alert=True)
            return
        
        # Save or update vote
        existing_vote = session.query(GameVote).filter(
            GameVote.game_id == game_id,
            GameVote.user_id == db_user.id
        ).first()
        
        if existing_vote:
            existing_vote.vote = vote
            existing_vote.created_at = datetime.now(pytz.UTC)
        else:
            new_vote = GameVote(
                game_id=game_id,
                user_id=db_user.id,
                vote=vote
            )
            session.add(new_vote)
        
        session.commit()
        
        # Respond to user
        if vote == 'start_now':
            await query.answer("✅ Голос за старт учтён!", show_alert=False)
        else:
            await query.answer("⏳ Голос за ожидание учтён!", show_alert=False)
        
        # Update message to show vote status
        try:
            vote_text = "▶️ НАЧАТЬ СЕЙЧАС" if vote == 'start_now' else "⏳ ЖДАТЬ ЕЩЁ 5 МИНУТ"
            await query.edit_message_text(
                f"Ваш голос: {vote_text}\n\n"
                f"Ожидание других игроков..."
            )
        except Exception as e:
            logger.debug(f"Could not edit vote message: {e}")
