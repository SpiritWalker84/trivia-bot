"""
Telegram keyboard and button definitions.
"""
from typing import List, Dict, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton


class MainMenuKeyboard:
    """Main menu keyboard."""
    
    @staticmethod
    def get_keyboard() -> ReplyKeyboardMarkup:
        """Get main menu keyboard."""
        keyboard = [
            [KeyboardButton("🏃 БЫСТРАЯ ИГРА")],
            [KeyboardButton("🤖 ТРЕНИРОВКА")],
            [KeyboardButton("👥 ПРИВАТНАЯ ИГРА")],
            [KeyboardButton("📊 РЕЙТИНГ"), KeyboardButton("📖 ПРАВИЛА")],
            [KeyboardButton("📊 Моя статистика")],
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


class GameVoteKeyboard:
    """Game vote keyboard for start/wait decision."""
    
    @staticmethod
    def get_keyboard(game_id: int) -> InlineKeyboardMarkup:
        """Get game vote keyboard."""
        keyboard = [
            [
                InlineKeyboardButton(
                    "▶️ НАЧАТЬ СЕЙЧАС",
                    callback_data=f"vote:start_now:{game_id}"
                ),
                InlineKeyboardButton(
                    "⏳ ЖДАТЬ ЕЩЁ 5 МИНУТ",
                    callback_data=f"vote:wait_more:{game_id}"
                )
            ]
        ]
        return InlineKeyboardMarkup(keyboard)


class QuestionAnswerKeyboard:
    """Question answer keyboard with options A, B, C, D."""
    
    @staticmethod
    def get_keyboard(round_question_id: int, options: Dict[str, str]) -> InlineKeyboardMarkup:
        """
        Get question answer keyboard.
        
        Args:
            round_question_id: Round question ID
            options: Dict mapping option letters to text
        """
        keyboard = []
        for option in ['A', 'B', 'C', 'D']:
            if option in options:
                keyboard.append([
                    InlineKeyboardButton(
                        f"{option}) {options[option]}",
                        callback_data=f"answer:{round_question_id}:{option}"
                    )
                ])
        return InlineKeyboardMarkup(keyboard)


class TrainingDifficultyKeyboard:
    """Training mode difficulty selection keyboard."""
    
    @staticmethod
    def get_keyboard() -> InlineKeyboardMarkup:
        """Get training difficulty keyboard."""
        keyboard = [
            [
                InlineKeyboardButton("Новичок", callback_data="training:novice"),
                InlineKeyboardButton("Любитель", callback_data="training:amateur"),
                InlineKeyboardButton("Эксперт", callback_data="training:expert")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)


class EliminationChoiceKeyboard:
    """Keyboard for eliminated player to choose spectator or leave."""
    
    @staticmethod
    def get_keyboard(game_id: int, user_id: int) -> InlineKeyboardMarkup:
        """Get elimination choice keyboard."""
        keyboard = [
            [
                InlineKeyboardButton(
                    "👁️ Остаться зрителем",
                    callback_data=f"elimination:spectator:{game_id}:{user_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "🚪 Выйти из игры",
                    callback_data=f"elimination:leave:{game_id}:{user_id}"
                )
            ]
        ]
        return InlineKeyboardMarkup(keyboard)


class AdminKeyboard:
    """Admin keyboard."""
    
    @staticmethod
    def get_main_keyboard() -> InlineKeyboardMarkup:
        """Get admin main menu keyboard."""
        keyboard = [
            [
                InlineKeyboardButton("🎮 Игры", callback_data="admin:games"),
                InlineKeyboardButton("👥 Пользователи", callback_data="admin:users")
            ],
            [
                InlineKeyboardButton("❓ Вопросы", callback_data="admin:questions"),
                InlineKeyboardButton("📊 Статистика", callback_data="admin:stats")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
