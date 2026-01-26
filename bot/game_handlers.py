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
    
    logger.info(f"Handling answer: user={user.id if user else None}, round_question_id={round_question_id}, option={selected_option}")
    
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
        from decimal import Decimal
        if round_question.displayed_at:
            answer_time = (datetime.now(pytz.UTC) - round_question.displayed_at).total_seconds()
        else:
            answer_time = 0.0
        
        # Convert to Decimal for database compatibility
        answer_time_decimal = Decimal(str(answer_time))
        
        # Check if answer is correct (use shuffled correct option if available)
        # Only use shuffled option if both shuffled_options and correct_option_shuffled are set
        shuffled_opts = round_question.shuffled_options
        correct_shuffled = round_question.correct_option_shuffled
        original_correct = question.correct_option
        
        logger.info(f"[ANSWER_CHECK] round_question_id={round_question_id}, question_id={question.id}")
        logger.info(f"[ANSWER_CHECK] shuffled_options={shuffled_opts}, correct_option_shuffled={correct_shuffled}, original_correct={original_correct}")
        logger.info(f"[ANSWER_CHECK] user selected={selected_option.upper()}")
        
        has_shuffled = bool(shuffled_opts and correct_shuffled)
        
        if has_shuffled:
            correct_option = correct_shuffled.upper()
            logger.info(f"[ANSWER_CHECK] Using SHUFFLED correct option: {correct_option} (original was {original_correct})")
            logger.info(f"[ANSWER_CHECK] Shuffled mapping: {shuffled_opts}")
        else:
            # Fallback to original correct option (backward compatibility or no shuffling)
            correct_option = original_correct.upper()
            logger.info(f"[ANSWER_CHECK] Using ORIGINAL correct option: {correct_option} (has_shuffled={has_shuffled})")
        
        selected_upper = selected_option.upper()
        logger.info(f"[ANSWER_CHECK] Comparison: selected='{selected_upper}' vs correct='{correct_option}' (equal={selected_upper == correct_option})")
        is_correct = (selected_upper == correct_option)
        logger.info(f"[ANSWER_CHECK] Result: {'CORRECT ✓' if is_correct else 'INCORRECT ✗'} - user selected {selected_option}, correct was {correct_option}")
        
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
            answer_time=answer_time_decimal,
            answered_at=datetime.now(pytz.UTC)
        )
        session.add(answer)
        
        # Update game player stats
        if is_correct:
            game_player.total_score += 1
        game_player.total_time += answer_time_decimal
        
        session.commit()
        
        # Send feedback message immediately (callback already answered in main handler)
        # Format time: show seconds with 1 decimal place
        time_str = f"{float(answer_time_decimal):.1f}"
        try:
            if is_correct:
                await query.message.reply_text(f"✅ Правильно! (вы ответили за {time_str} сек)")
            else:
                # Use shuffled correct option if available
                correct_option_display = correct_option if round_question.correct_option_shuffled else question.correct_option
                await query.message.reply_text(f"❌ Неправильно. Правильный ответ: {correct_option_display} (вы ответили за {time_str} сек)")
        except Exception as e:
            logger.error(f"Failed to send answer feedback: {e}")
        
        # Check for early victory asynchronously via Celery (only in final round)
        # This avoids blocking the callback handler
        if game.is_final_stage:
            from tasks.game_tasks import check_early_victory_task
            check_early_victory_task.delay(
                game_id=game.id,
                round_id=round_obj.id,
                round_question_id=round_question_id,
                user_id=db_user.id,
                selected_option=selected_option.upper(),
                is_correct=is_correct,
                answer_time=float(answer_time_decimal)
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
