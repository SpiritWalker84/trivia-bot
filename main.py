"""
Main entry point for Trivia Bot.
"""
import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
import config
from utils.logging import setup_logging, get_logger
from utils.errors import ConfigurationError

# Setup logging
setup_logging()
logger = get_logger(__name__)


async def start_command(update: Update, context) -> None:
    """Handle /start command."""
    from database.session import db_session
    from database.queries import UserQueries
    from bot.keyboards import MainMenuKeyboard
    
    user = update.effective_user
    logger.info(f"User {user.id} ({user.username}) started the bot")
    
    # Get or create user in database
    with db_session() as session:
        db_user = UserQueries.get_or_create_user(
            session,
            telegram_id=user.id,
            username=user.username,
            full_name=f"{user.first_name} {user.last_name or ''}".strip()
        )
    
    welcome_text = (
        "🎮 Добро пожаловать в Brain Survivor!\n\n"
        "Это викторина на выбывание:\n"
        "• 10 участников\n"
        "• 10 раундов по 10 вопросов\n"
        "• После каждого раунда выбывает один игрок\n"
        "• Финал: битва двух финалистов\n\n"
        "Выберите режим игры:"
    )
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=MainMenuKeyboard.get_keyboard()
    )


async def help_command(update: Update, context) -> None:
    """Handle /help command."""
    help_text = (
        "📖 Помощь по Brain Survivor\n\n"
        "/start - Начать\n"
        "/help - Эта справка\n"
        "/stats - Моя статистика\n"
        "/rating - Рейтинг\n\n"
        "Режимы игры:\n"
        "🏃 Быстрая игра - игра с другими игроками\n"
        "🤖 Тренировка - игра против ботов\n"
        "👥 Приватная игра - игра с друзьями"
    )
    await update.message.reply_text(help_text)


async def message_handler(update: Update, context) -> None:
    """Handle text messages."""
    text = update.message.text
    
    if text == "🏃 БЫСТРАЯ ИГРА":
        await handle_quick_game(update, context)
    elif text == "🤖 ТРЕНИРОВКА":
        await handle_training(update, context)
    elif text == "👥 ПРИВАТНАЯ ИГРА":
        await handle_private_game(update, context)
    elif text == "📊 РЕЙТИНГ":
        await handle_rating(update, context)
    elif text == "📖 ПРАВИЛА":
        await handle_rules(update, context)
    elif text == "📊 Моя статистика":
        await handle_stats(update, context)
    else:
        await update.message.reply_text(
            "Не понимаю эту команду. Используйте меню или /help"
        )


async def handle_quick_game(update: Update, context) -> None:
    """Handle quick game button."""
    from database.session import db_session
    from database.queries import PoolQueries
    from bot.keyboards import MainMenuKeyboard
    
    user_id = update.effective_user.id
    
    with db_session() as session:
        # Get or create active pool
        pool = PoolQueries.get_or_create_active_pool(session)
        
        # Add player to pool
        try:
            PoolQueries.add_player_to_pool(session, pool.id, user_id)
        except Exception as e:
            logger.error(f"Error adding player to pool: {e}")
            await update.message.reply_text(
                "Произошла ошибка. Попробуйте позже.",
                reply_markup=MainMenuKeyboard.get_keyboard()
            )
            return
    
    await update.message.reply_text(
        "✅ Вы добавлены в очередь быстрой игры.\n\n"
        "Ожидание других игроков...\n"
        "Каждые 5 минут система проверяет очередь.",
        reply_markup=MainMenuKeyboard.get_keyboard()
    )


async def handle_training(update: Update, context) -> None:
    """Handle training button."""
    from bot.keyboards import TrainingDifficultyKeyboard
    
    await update.message.reply_text(
        "🤖 Выберите сложность ботов:",
        reply_markup=TrainingDifficultyKeyboard.get_keyboard()
    )


async def handle_private_game(update: Update, context) -> None:
    """Handle private game button."""
    await update.message.reply_text(
        "👥 Приватная игра\n\n"
        "Эта функция будет доступна в следующих версиях."
    )


async def handle_rating(update: Update, context) -> None:
    """Handle rating button."""
    from database.session import db_session
    from database.queries import UserQueries
    
    with db_session() as session:
        top_users = UserQueries.get_rating_top(session, limit=10)
    
    if not top_users:
        await update.message.reply_text("Рейтинг пуст.")
        return
    
    rating_text = "📊 ТОП-10 ИГРОКОВ\n\n"
    for i, user in enumerate(top_users, 1):
        username = user.username or user.full_name or f"ID{user.id}"
        rating_text += f"{i}. {username} - {user.rating} очков\n"
    
    await update.message.reply_text(rating_text)


async def handle_rules(update: Update, context) -> None:
    """Handle rules button."""
    rules_text = (
        "📖 ПРАВИЛА ИГРЫ\n\n"
        "🎯 Суть:\n"
        "10 участников играют 10 раундов по 10 вопросов.\n\n"
        "📉 Выбывание:\n"
        "После каждого раунда выбывает 1 игрок с наименьшим количеством правильных ответов.\n"
        "При равенстве очков выбывает тот, у кого больше суммарное время на ответы.\n\n"
        "🏆 Финал:\n"
        "Битва двух финалистов в 10 раундах."
    )
    await update.message.reply_text(rules_text)


async def handle_stats(update: Update, context) -> None:
    """Handle stats button."""
    from database.session import db_session
    from database.queries import UserQueries
    
    user_id = update.effective_user.id
    
    with db_session() as session:
        user = UserQueries.get_user_by_telegram_id(session, user_id)
        if not user:
            await update.message.reply_text("Пользователь не найден.")
            return
        
        win_rate = (user.games_won / user.games_played * 100) if user.games_played > 0 else 0
        
        stats_text = (
            f"📊 МОЯ СТАТИСТИКА\n\n"
            f"🏆 Рейтинг: {user.rating}\n"
            f"🎮 Игр сыграно: {user.games_played}\n"
            f"✅ Побед: {user.games_won}\n"
            f"📈 Процент побед: {win_rate:.1f}%"
        )
        
        await update.message.reply_text(stats_text)


async def callback_query_handler(update: Update, context) -> None:
    """Handle callback queries (inline button clicks)."""
    query = update.callback_query
    
    try:
        data = query.data
        if data.startswith("vote:"):
            await query.answer()  # Answer immediately for votes
            await handle_vote(update, context, data)
        elif data.startswith("answer:"):
            # Don't answer here - handle_answer will do it with feedback
            await handle_answer(update, context, data)
        elif data.startswith("training:"):
            await query.answer()
            await handle_training_difficulty(update, context, data)
        elif data.startswith("admin:"):
            await query.answer()
            await handle_admin(update, context, data)
        else:
            logger.warning(f"Unknown callback data: {data}")
            await query.answer("Неизвестная команда", show_alert=False)
    except Exception as e:
        logger.error(f"Error handling callback query: {e}", exc_info=True)
        # Try to answer callback to prevent button from hanging
        try:
            await query.answer("Произошла ошибка", show_alert=True)
        except:
            pass


async def handle_vote(update: Update, context, data: str) -> None:
    """Handle game vote callback."""
    from bot.game_handlers import handle_vote as handle_vote_action
    
    # Parse callback data: vote:start_now:123 or vote:wait_more:123
    parts = data.split(":")
    if len(parts) != 3:
        await update.callback_query.answer("Ошибка в данных", show_alert=True)
        return
    
    vote_type = parts[1]  # 'start_now' or 'wait_more'
    try:
        game_id = int(parts[2])
    except ValueError:
        await update.callback_query.answer("Ошибка: неверный ID игры", show_alert=True)
        return
    
    await handle_vote_action(update, context, game_id, vote_type)


async def handle_answer(update: Update, context, data: str) -> None:
    """Handle answer callback."""
    from bot.game_handlers import handle_answer as handle_answer_action
    
    # Parse callback data: answer:123:A
    parts = data.split(":")
    if len(parts) != 3:
        await update.callback_query.answer("Ошибка в данных", show_alert=True)
        return
    
    try:
        round_question_id = int(parts[1])
    except ValueError:
        await update.callback_query.answer("Ошибка: неверный ID вопроса", show_alert=True)
        return
    
    selected_option = parts[2].upper()  # 'A', 'B', 'C', 'D'
    
    if selected_option not in ['A', 'B', 'C', 'D']:
        await update.callback_query.answer("Ошибка: неверный вариант ответа", show_alert=True)
        return
    
    await handle_answer_action(update, context, round_question_id, selected_option)


async def handle_training_difficulty(update: Update, context, data: str) -> None:
    """Handle training difficulty selection."""
    # TODO: Implement training game start
    difficulty = data.split(":")[1]
    await update.callback_query.message.reply_text(
        f"Тренировка со сложностью {difficulty} будет запущена..."
    )


async def handle_admin(update: Update, context, data: str) -> None:
    """Handle admin callbacks."""
    # TODO: Implement admin handlers
    await update.callback_query.answer("Админ-панель (в разработке)")


def main() -> None:
    """Main function to start the bot."""
    try:
        # Validate configuration
        config.config.validate()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        raise ConfigurationError(str(e))
    
    # Create application
    application = Application.builder().token(config.config.TELEGRAM_BOT_TOKEN).build()
    
    # Register handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    application.add_handler(CallbackQueryHandler(callback_query_handler))
    
    # Start bot
    logger.info("Starting Trivia Bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
