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


def get_round_leaderboard_text(game_id: int, round_id: int, current_user_id: int = None) -> str:
    """
    Get current round leaderboard text showing player positions.
    
    Args:
        game_id: Game ID
        round_id: Round ID
        current_user_id: Optional current user ID to highlight in leaderboard
        
    Returns:
        Formatted leaderboard text
    """
    from database.models import GamePlayer, Answer, User
    
    if not game_id or not round_id:
        return ""
    
    with db_session() as session:
        # Get all alive players
        players = session.query(GamePlayer).filter(
            GamePlayer.game_id == game_id,
            GamePlayer.is_eliminated == False
        ).all()
        
        if not players:
            return ""
        
        # Get current round answers for each player
        player_scores = []
        for player in players:
            # Count correct answers in current round
            correct_count = session.query(Answer).filter(
                Answer.round_id == round_id,
                Answer.user_id == player.user_id,
                Answer.is_correct == True
            ).count()
            
            # Get user name
            user = session.query(User).filter(User.id == player.user_id).first()
            if user:
                player_name = user.full_name or user.username or f"User {user.id}"
                player_scores.append({
                    'user_id': player.user_id,
                    'name': player_name,
                    'score': correct_count,
                    'is_bot': player.is_bot
                })
        
        # Sort by score (descending), then by name (ascending) for tie-breaking
        player_scores.sort(key=lambda x: (-x['score'], x['name'].lower()))
        
        # Build leaderboard text
        leaderboard_lines = ["📊 Текущие результаты раунда:\n"]
        for i, player in enumerate(player_scores, 1):
            medal = ""
            if i == 1:
                medal = "🥇"
            elif i == 2:
                medal = "🥈"
            elif i == 3:
                medal = "🥉"
            
            # Highlight current user
            marker = "👤 " if player['user_id'] == current_user_id else ""
            bot_marker = "🤖 " if player['is_bot'] else ""
            
            leaderboard_lines.append(
                f"{medal} {i}. {marker}{bot_marker}{player['name']}: {player['score']} ✓"
            )
        
        return "\n".join(leaderboard_lines)


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
        logger.info(f"[SEND_QUESTION_START] user_id={user_id}, round_question_id={round_question.id}, question_id={question.id}")
        try:
            # Get current user ID and game/round info for leaderboard
            with db_session() as session:
                from database.models import User, Round
                db_user = session.query(User).filter(User.telegram_id == user_id).first()
                current_user_id = db_user.id if db_user else None
                
                # Get round to get game_id
                round_obj = session.query(Round).filter(Round.id == round_question.round_id).first()
                game_id = round_obj.game_id if round_obj else None
                round_id = round_question.round_id
            
            # Build question text
            theme_text = f" | Тема: {theme_name}" if theme_name else ""
            question_text = (
                f"🏁 Раунд {round_number}/{self.config.ROUNDS_PER_GAME}{theme_text}\n"
                f"Вопрос {question_number}/{self.config.QUESTIONS_PER_ROUND}:\n\n"
                f"❓ {question.question_text}\n\n"
            )
            
            # Add leaderboard
            leaderboard_text = get_round_leaderboard_text(
                game_id,
                round_id,
                current_user_id
            )
            if leaderboard_text:
                question_text += f"\n{leaderboard_text}\n"
            
            # Build options using shuffled mapping if available
            options = {}
            has_shuffled = bool(round_question.shuffled_options)
            
            # Explicitly access shuffled_options to ensure it's loaded from DB
            shuffled_opts = round_question.shuffled_options
            
            if has_shuffled:
                # Use shuffled options
                shuffled_mapping = round_question.shuffled_options
                # shuffled_mapping maps new_position -> original_position
                # So we need to get the original option text for each new position
                for new_pos in ['A', 'B', 'C', 'D']:
                    if new_pos in shuffled_mapping:
                        original_pos = shuffled_mapping[new_pos]
                        if original_pos == 'A' and question.option_a:
                            options[new_pos] = question.option_a
                        elif original_pos == 'B' and question.option_b:
                            options[new_pos] = question.option_b
                        elif original_pos == 'C' and question.option_c:
                            options[new_pos] = question.option_c
                        elif original_pos == 'D' and question.option_d:
                            options[new_pos] = question.option_d
            else:
                # Fallback to original options if no shuffling (backward compatibility)
                if question.option_a:
                    options['A'] = question.option_a
                if question.option_b:
                    options['B'] = question.option_b
                if question.option_c:
                    options['C'] = question.option_c
                if question.option_d:
                    options['D'] = question.option_d
                logger.info(f"Built ORIGINAL options dict: A={options.get('A', 'N/A')[:30]}, B={options.get('B', 'N/A')[:30]}, C={options.get('C', 'N/A')[:30]}, D={options.get('D', 'N/A')[:30]}")
            
            # Visual progress bar for timer
            time_limit = self.config.QUESTION_TIME_LIMIT
            total_bars = 20
            filled_bars = total_bars  # Start with full bar
            progress_bar = "▓" * filled_bars
            question_text += f"\n⏱️ {time_limit} сек [{progress_bar}]"
            
            # Create keyboard
            keyboard = QuestionAnswerKeyboard.get_keyboard(
                round_question.id,
                options
            )
            
            # Remove main menu keyboard when sending first question
            from telegram import ReplyKeyboardRemove
            
            # Check if this is the first question of the game (round 1, question 1)
            is_first_question = (round_number == 1 and question_number == 1)
            
            # Remove keyboard before sending first question
            if is_first_question:
                try:
                    await self.bot.send_message(
                        chat_id=user_id,
                        text="🎮 Игра началась!",
                        reply_markup=ReplyKeyboardRemove()
                    )
                except Exception as e:
                    logger.warning(f"Failed to remove keyboard for user {user_id}: {e}")
            
            # Send question message
            message = await self.bot.send_message(
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
            
            # Start countdown timer (update message every second)
            # Get game_id and round_id from round_question
            with db_session() as session:
                rq = session.query(RoundQuestion).filter(
                    RoundQuestion.id == round_question.id
                ).first()
                if not rq:
                    logger.error(f"RoundQuestion {round_question.id} not found")
                    return True
                
                round_obj = session.query(Round).filter(Round.id == rq.round_id).first()
                if not round_obj:
                    logger.error(f"Round {rq.round_id} not found")
                    return True
                
                game_id = round_obj.game_id
                round_id = round_obj.id
            
            from tasks.question_timer import start_question_timer
            from utils.logging import get_logger
            timer_logger = get_logger(__name__)
            time_limit = self.config.QUESTION_TIME_LIMIT
            timer_logger.info(f"Starting timer for question {round_question.id}, user {user_id}, time_limit={time_limit}")
            start_question_timer.delay(
                game_id=game_id,
                round_id=round_id,
                round_question_id=round_question.id,
                user_id=user_id,
                message_id=message.message_id,
                time_limit=time_limit
            )
            
            return True
            
        except TelegramError as e:
            logger.error(f"Failed to send question to user {user_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending question to user {user_id}: {e}")
            return False
    
    @telegram_retry
    async def send_question_to_spectator(
        self,
        user_id: int,
        round_question: RoundQuestion,
        question: Question,
        round_number: int,
        question_number: int,
        theme_name: Optional[str] = None
    ) -> bool:
        """
        Send question to spectator (eliminated player who chose to watch).
        Question is sent without answer buttons.
        
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
                f"👁️ ЗРИТЕЛЬ\n"
                f"🏁 Раунд {round_number}/{self.config.ROUNDS_PER_GAME}{theme_text}\n"
                f"Вопрос {question_number}/{self.config.QUESTIONS_PER_ROUND}:\n\n"
                f"❓ {question.question_text}\n\n"
            )
            
            # Add options text (for viewing only) - use shuffled options if available
            if round_question.shuffled_options:
                shuffled_mapping = round_question.shuffled_options
                for new_pos in ['A', 'B', 'C', 'D']:
                    if new_pos in shuffled_mapping:
                        original_pos = shuffled_mapping[new_pos]
                        option_text = None
                        if original_pos == 'A' and question.option_a:
                            option_text = question.option_a
                        elif original_pos == 'B' and question.option_b:
                            option_text = question.option_b
                        elif original_pos == 'C' and question.option_c:
                            option_text = question.option_c
                        elif original_pos == 'D' and question.option_d:
                            option_text = question.option_d
                        if option_text:
                            question_text += f"{new_pos}) {option_text}\n"
            else:
                # Fallback to original options
                if question.option_a:
                    question_text += f"A) {question.option_a}\n"
                if question.option_b:
                    question_text += f"B) {question.option_b}\n"
                if question.option_c:
                    question_text += f"C) {question.option_c}\n"
                if question.option_d:
                    question_text += f"D) {question.option_d}\n"
            
            question_text += "\n👁️ Вы наблюдаете за игрой"
            
            # Send message without keyboard (no answer buttons)
            await self.bot.send_message(
                chat_id=user_id,
                text=question_text
            )
            
            return True
            
        except TelegramError as e:
            logger.error(f"Failed to send question to spectator {user_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending question to spectator {user_id}: {e}")
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
            
            # Get alive players and spectators
            alive_players = [
                gp for gp in game.players
                if not gp.is_eliminated
            ]
            spectators = [
                gp for gp in game.players
                if gp.is_eliminated and gp.is_spectator is True and not gp.left_game
            ]
            
            results = {}
            # Send to alive players (with answer buttons)
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
            
            # Send to spectators (without answer buttons)
            for game_player in spectators:
                if game_player.is_bot:
                    continue
                
                user = session.query(User).filter(User.id == game_player.user_id).first()
                if not user or not user.telegram_id:
                    continue
                
                success = await self.send_question_to_spectator(
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
            
            # Send to all players (alive, spectators, but not those who left)
            for result in results:
                if not result['telegram_id']:
                    continue
                
                # Skip players who left the game
                game_player = next(
                    (gp for gp in all_players if gp.user_id == result['user_id']),
                    None
                )
                if game_player and game_player.left_game:
                    continue
                
                try:
                    # Check if this is the last round (game finished)
                    is_last_round = (round_number == self.config.ROUNDS_PER_GAME)
                    
                    # Restore main menu keyboard after game ends
                    from bot.keyboards import MainMenuKeyboard
                    reply_markup = MainMenuKeyboard.get_keyboard() if is_last_round else None
                    
                    await self.bot.send_message(
                        chat_id=result['telegram_id'],
                        text=results_text,
                        reply_markup=reply_markup
                    )
                except Exception as e:
                    logger.error(f"Failed to send results to {result['telegram_id']}: {e}")
            
            # Send elimination choice message to eliminated player (if not already spectator or left)
            if eliminated_user_id:
                eliminated_player = next(
                    (gp for gp in all_players if gp.user_id == eliminated_user_id),
                    None
                )
                if eliminated_player and not eliminated_player.is_bot:
                    # Check if player already made a choice
                    if eliminated_player.is_spectator is None and not eliminated_player.left_game:
                        eliminated_user = session.query(User).filter(
                            User.id == eliminated_user_id
                        ).first()
                        if eliminated_user and eliminated_user.telegram_id:
                            from bot.keyboards import EliminationChoiceKeyboard
                            choice_text = (
                                "🚫 Вы выбыли из игры!\n\n"
                                "Что вы хотите сделать?"
                            )
                            try:
                                message = await self.bot.send_message(
                                    chat_id=eliminated_user.telegram_id,
                                    text=choice_text,
                                    reply_markup=EliminationChoiceKeyboard.get_keyboard(
                                        game_id, eliminated_user_id
                                    )
                                )
                                
                                # Schedule automatic leave after 1 minute if no response
                                from tasks.elimination_auto_leave import auto_leave_game
                                auto_leave_game.apply_async(
                                    args=[game_id, eliminated_user_id],
                                    countdown=60  # 1 minute
                                )
                                logger.info(f"Scheduled auto-leave for eliminated player {eliminated_user_id} in game {game_id} after 60 seconds")
                            except Exception as e:
                                logger.error(f"Failed to send elimination choice to {eliminated_user.telegram_id}: {e}")
    
    @telegram_retry
    async def send_round_pause_notification(
        self,
        game_id: int,
        next_round_number: int
    ) -> None:
        """Send pause notification before next round."""
        with db_session() as session:
            game = session.query(Game).filter(Game.id == game_id).first()
            if not game:
                return
            
            # Get all alive players and spectators
            alive_players = [
                gp for gp in game.players
                if not gp.is_eliminated
            ]
            spectators = [
                gp for gp in game.players
                if gp.is_eliminated and gp.is_spectator is True and not gp.left_game
            ]
            
            pause_text = (
                f"⏸️ Пауза между раундами\n\n"
                f"Следующий раунд ({next_round_number}/{self.config.ROUNDS_PER_GAME}) "
                f"начнется через 1 минуту.\n"
                f"У вас есть время, чтобы посмотреть результаты."
            )
            
            # Send to all alive players
            for game_player in alive_players:
                if game_player.is_bot:
                    continue
                
                user = session.query(User).filter(User.id == game_player.user_id).first()
                if user and user.telegram_id:
                    try:
                        await self.bot.send_message(
                            chat_id=user.telegram_id,
                            text=pause_text
                        )
                    except Exception as e:
                        logger.error(f"Failed to send pause notification to {user.telegram_id}: {e}")
            
            # Send to spectators
            for game_player in spectators:
                if game_player.is_bot:
                    continue
                
                user = session.query(User).filter(User.id == game_player.user_id).first()
                if user and user.telegram_id:
                    try:
                        await self.bot.send_message(
                            chat_id=user.telegram_id,
                            text=pause_text
                        )
                    except Exception as e:
                        logger.error(f"Failed to send pause notification to spectator {user.telegram_id}: {e}")
    
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
                
                # Skip players who left the game
                if game_player.left_game:
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
            
            # Restore main menu keyboard after game ends
            from bot.keyboards import MainMenuKeyboard
            
            for game_player in game.players:
                if game_player.is_bot:
                    continue
                
                user = session.query(User).filter(User.id == game_player.user_id).first()
                if user and user.telegram_id:
                    try:
                        await self.bot.send_message(
                            chat_id=user.telegram_id,
                            text=message_text,
                            reply_markup=MainMenuKeyboard.get_keyboard()
                        )
                    except Exception as e:
                        logger.error(f"Failed to send early victory notification to {user.telegram_id}: {e}")
