"""
Game notifications - sending questions and game updates to players.
"""
from typing import List, Dict, Optional
from datetime import datetime
import pytz
from telegram import Bot
from telegram.error import TelegramError
from database.session import db_session
from database.models import Game, GamePlayer, Round, RoundQuestion, Question, User, Answer
from database.queries import UserQueries
from bot.keyboards import QuestionAnswerKeyboard, GameVoteKeyboard
from utils.retry import telegram_retry
from utils.logging import get_logger
import config

logger = get_logger(__name__)


class GameNotifications:
    """Handles sending game notifications to players."""
    
    def __init__(self, bot: Bot):
        """Initialize game notifications."""
        self.bot = bot
        self.config = config.config
    
    @telegram_retry
    async def send_question_to_player(
        self,
        user_id: int,
        round_question: RoundQuestion,
        question: Question,
        round_number: int,
        question_number: int,
        theme_name: Optional[str] = None
    ) -> bool:
        """
        Send question to player in private message.
        
        Args:
            user_id: Telegram user ID
            round_question: RoundQuestion object
            question: Question object
            round_number: Round number
            question_number: Question number in round
            theme_name: Optional theme name
        
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Build question text
            theme_text = f" | Тема: {theme_name}" if theme_name else ""
            question_text = (
                f"🏁 Раунд {round_number}/{self.config.ROUNDS_PER_GAME}{theme_text}\n"
                f"Вопрос {question_number}/{self.config.QUESTIONS_PER_ROUND}:\n\n"
                f"❓ {question.question_text}\n\n"
            )
            
            # Build options
            options = {}
            options_text = ""
            if question.option_a:
                options['A'] = question.option_a
                options_text += f"A) {question.option_a}\n"
            if question.option_b:
                options['B'] = question.option_b
                options_text += f"B) {question.option_b}\n"
            if question.option_c:
                options['C'] = question.option_c
                options_text += f"C) {question.option_c}\n"
            if question.option_d:
                options['D'] = question.option_d
                options_text += f"D) {question.option_d}\n"
            
            question_text += options_text
            question_text += f"\n⏱️ {self.config.QUESTION_TIME_LIMIT} секунд"
            
            # Create keyboard
            keyboard = QuestionAnswerKeyboard.get_keyboard(
                round_question.id,
                options
            )
            
            # Send message
            await self.bot.send_message(
                chat_id=user_id,
                text=question_text,
                reply_markup=keyboard
            )
            
            # Update displayed_at
            with db_session() as session:
                round_question_obj = session.query(RoundQuestion).filter(
                    RoundQuestion.id == round_question.id
                ).first()
                if round_question_obj:
                    round_question_obj.displayed_at = datetime.now(pytz.UTC)
                    session.commit()
            
            return True
            
        except TelegramError as e:
            logger.error(f"Failed to send question to user {user_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending question to user {user_id}: {e}")
            return False
    
    @telegram_retry
    async def send_question_to_all_players(
        self,
        game_id: int,
        round_id: int,
        round_question_id: int
    ) -> Dict[int, bool]:
        """
        Send question to all alive players in game.
        
        Returns:
            Dict mapping user_id to success status
        """
        with db_session() as session:
            game = session.query(Game).filter(Game.id == game_id).first()
            if not game:
                return {}
            
            round_obj = session.query(Round).filter(Round.id == round_id).first()
            if not round_obj:
                return {}
            
            round_question = session.query(RoundQuestion).filter(
                RoundQuestion.id == round_question_id
            ).first()
            if not round_question:
                return {}
            
            question = session.query(Question).filter(
                Question.id == round_question.question_id
            ).first()
            if not question:
                return {}
            
            # Get theme name
            theme_name = None
            if round_obj.theme_id:
                from database.models import Theme
                theme = session.query(Theme).filter(Theme.id == round_obj.theme_id).first()
                if theme:
                    theme_name = theme.name
            
            # Get alive players
            alive_players = [
                gp for gp in game.players
                if not gp.is_eliminated
            ]
            
            results = {}
            for game_player in alive_players:
                # Skip bots (they answer automatically)
                if game_player.is_bot:
                    continue
                
                # Get user telegram_id
                user = session.query(User).filter(User.id == game_player.user_id).first()
                if not user or not user.telegram_id:
                    continue
                
                success = await self.send_question_to_player(
                    user.telegram_id,
                    round_question,
                    question,
                    round_obj.round_number,
                    round_question.question_number,
                    theme_name
                )
                results[user.telegram_id] = success
            
            return results
    
    @telegram_retry
    async def send_round_results(
        self,
        game_id: int,
        round_number: int,
        eliminated_user_id: Optional[int] = None
    ) -> None:
        """
        Send round results to all players.
        
        Args:
            game_id: Game ID
            round_number: Round number
            eliminated_user_id: Optional eliminated user ID
        """
        with db_session() as session:
            game = session.query(Game).filter(Game.id == game_id).first()
            if not game:
                return
            
            round_obj = session.query(Round).filter(
                Round.game_id == game_id,
                Round.round_number == round_number
            ).first()
            if not round_obj:
                return
            
            # Get all players (including eliminated)
            all_players = game.players
            
            # Collect round results
            results = []
            for game_player in all_players:
                answers = session.query(Answer).filter(
                    Answer.game_id == game_id,
                    Answer.round_id == round_obj.id,
                    Answer.user_id == game_player.user_id
                ).all()
                
                correct_count = sum(1 for a in answers if a.is_correct)
                total_time = sum(float(a.answer_time or 0) for a in answers)
                
                user = session.query(User).filter(User.id == game_player.user_id).first()
                username = user.username or user.full_name or f"ID{user.id}" if user else f"Bot_{game_player.id}"
                
                results.append({
                    'user_id': game_player.user_id,
                    'telegram_id': user.telegram_id if user else None,
                    'username': username,
                    'correct_answers': correct_count,
                    'total_time': total_time,
                    'is_eliminated': game_player.is_eliminated,
                    'is_bot': game_player.is_bot
                })
            
            # Sort by score (descending) and time (ascending)
            results.sort(key=lambda x: (-x['correct_answers'], x['total_time']))
            
            # Build results text
            results_text = (
                f"📊 ИТОГИ РАУНДА {round_number}/{self.config.ROUNDS_PER_GAME}\n\n"
            )
            
            for i, result in enumerate(results, 1):
                status = "🚫" if result['is_eliminated'] else "✅"
                bot_mark = " (бот)" if result['is_bot'] else ""
                results_text += (
                    f"{i}. {result['username']}{bot_mark} - "
                    f"{result['correct_answers']}/10 ({result['total_time']:.1f}с) {status}\n"
                )
            
            if eliminated_user_id:
                eliminated = next((r for r in results if r['user_id'] == eliminated_user_id), None)
                if eliminated:
                    results_text += f"\n🚫 Выбывает: {eliminated['username']}"
            
            # Send to all players
            for result in results:
                if result['telegram_id']:
                    try:
                        await self.bot.send_message(
                            chat_id=result['telegram_id'],
                            text=results_text
                        )
                    except Exception as e:
                        logger.error(f"Failed to send results to {result['telegram_id']}: {e}")
    
    @telegram_retry
    async def send_vote_message(
        self,
        game_id: int,
        player_count: int
    ) -> None:
        """Send vote message to all players in game."""
        with db_session() as session:
            game = session.query(Game).filter(Game.id == game_id).first()
            if not game:
                return
            
            players = [
                gp for gp in game.players
                if not gp.is_bot
            ]
            
            keyboard = GameVoteKeyboard.get_keyboard(game_id)
            message_text = (
                f"Игроков сейчас: {player_count}.\n"
                f"Начать игру с ботами или подождать ещё 5 минут?"
            )
            
            for game_player in players:
                user = session.query(User).filter(User.id == game_player.user_id).first()
                if user and user.telegram_id:
                    try:
                        await self.bot.send_message(
                            chat_id=user.telegram_id,
                            text=message_text,
                            reply_markup=keyboard
                        )
                    except Exception as e:
                        logger.error(f"Failed to send vote message to {user.telegram_id}: {e}")
    
    @telegram_retry
    async def send_game_start_notification(
        self,
        game_id: int
    ) -> None:
        """Send game start notification to all players."""
        with db_session() as session:
            game = session.query(Game).filter(Game.id == game_id).first()
            if not game:
                return
            
            players = game.players
            
            message_text = (
                "🎮 Игра начинается!\n\n"
                "Сейчас вы получите первый вопрос.\n"
                "Удачи!"
            )
            
            for game_player in players:
                if game_player.is_bot:
                    continue
                
                user = session.query(User).filter(User.id == game_player.user_id).first()
                if user and user.telegram_id:
                    try:
                        await self.bot.send_message(
                            chat_id=user.telegram_id,
                            text=message_text
                        )
                    except Exception as e:
                        logger.error(f"Failed to send start notification to {user.telegram_id}: {e}")
    
    @telegram_retry
    async def send_early_victory_notification(
        self,
        game_id: int,
        winner_user_id: int,
        leader_score: int,
        loser_score: int,
        questions_remaining: int
    ) -> None:
        """Send early victory notification."""
        with db_session() as session:
            game = session.query(Game).filter(Game.id == game_id).first()
            if not game:
                return
            
            winner_user = session.query(User).filter(User.id == winner_user_id).first()
            winner_name = winner_user.username or winner_user.full_name if winner_user else "Победитель"
            
            message_text = (
                f"🏆 ДОСРОЧНАЯ ПОБЕДА!\n\n"
                f"Победитель: {winner_name}\n"
                f"Счёт: {leader_score} vs {loser_score}\n"
                f"Осталось вопросов: {questions_remaining}\n\n"
                f"Игра завершена досрочно!"
            )
            
            for game_player in game.players:
                if game_player.is_bot:
                    continue
                
                user = session.query(User).filter(User.id == game_player.user_id).first()
                if user and user.telegram_id:
                    try:
                        await self.bot.send_message(
                            chat_id=user.telegram_id,
                            text=message_text
                        )
                    except Exception as e:
                        logger.error(f"Failed to send early victory notification to {user.telegram_id}: {e}")
