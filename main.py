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
    from bot.private_game import handle_private_game_invite, handle_private_game_callback
    
    user = update.effective_user
    logger.info(f"User {user.id} ({user.username}) started the bot")
    
    # Check if there's a parameter (e.g., /start private_123)
    args = context.args
    if args and len(args) > 0:
        param = args[0]
        if param.startswith("private_"):
            try:
                game_id = int(param.split("_")[1])
                await handle_private_game_invite(update, context, game_id)
                return
            except (ValueError, IndexError):
                logger.warning(f"Invalid private game invite parameter: {param}")
    
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
        "🤖 Тренировка с ботами - игра против ботов\n"
        "👥 Приватная игра - игра с друзьями"
    )
    await update.message.reply_text(help_text)


async def user_shared_handler(update: Update, context) -> None:
    """Handle user_shared updates (when user selects a contact via request_user button)."""
    if not update.message:
        return
    
    # Check for user_shared attribute (use getattr to avoid AttributeError)
    user_shared = getattr(update.message, 'user_shared', None)
    if user_shared:
        logger.info(f"Received user_shared update: {user_shared}, type: {type(user_shared)}")
        logger.info(f"Full update.message: {update.message}")
        logger.info(f"update.message attributes: {dir(update.message)}")
        from bot.private_game import handle_private_game_users_selected
        await handle_private_game_users_selected(update, context, user_shared)
        return
    else:
        logger.debug(f"Message received but no user_shared attribute. Message type: {type(update.message)}")


async def message_handler(update: Update, context) -> None:
    """Handle text messages."""
    # This handler only processes text messages
    # user_shared is handled by user_shared_handler
    
    text = update.message.text if update.message else None
    if not text:
        logger.warning(f"Message handler received update with no text: {update}")
        return
    
    if text == "🏃 БЫСТРАЯ ИГРА":
        await handle_quick_game(update, context)
    elif text == "🤖 ТРЕНИРОВКА С БОТАМИ":
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
    from bot.private_game import create_private_game
    await create_private_game(update, context)


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
    from bot.private_game import handle_private_game_callback
    
    query = update.callback_query
    
    try:
        data = query.data
        logger.debug(f"Callback query received: {data[:50]}...")
        if data.startswith("vote:"):
            await query.answer()  # Answer immediately for votes
            await handle_vote(update, context, data)
        elif data.startswith("answer:"):
            # Answer immediately to prevent button hanging, then process
            await query.answer()  # Answer immediately
            await handle_answer(update, context, data)
        elif data.startswith("training:"):
            await query.answer()
            await handle_training_difficulty(update, context, data)
        elif data.startswith("private:"):
            await query.answer()
            await handle_private_game_callback(update, context, data)
        elif data.startswith("elimination:"):
            await query.answer()
            await handle_elimination_choice(update, context, data)
        elif data.startswith("leave_game:"):
            await query.answer()
            await handle_leave_game(update, context, data)
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


async def handle_elimination_choice(update: Update, context, data: str) -> None:
    """Handle elimination choice callback (spectator or leave)."""
    from database.session import db_session
    from database.models import GamePlayer, User
    
    query = update.callback_query
    user = update.effective_user
    
    # Parse callback data: elimination:spectator:123:456 or elimination:leave:123:456
    parts = data.split(":")
    if len(parts) != 4:
        await query.answer("Ошибка в данных", show_alert=True)
        return
    
    choice = parts[1]  # 'spectator' or 'leave'
    try:
        game_id = int(parts[2])
        user_id = int(parts[3])
    except ValueError:
        await query.answer("Ошибка: неверный ID", show_alert=True)
        return
    
    # Verify that this is the correct user
    with db_session() as session:
        db_user = session.query(User).filter(User.telegram_id == user.id).first()
        if not db_user or db_user.id != user_id:
            await query.answer("Ошибка: неверный пользователь", show_alert=True)
            return
        
        game_player = session.query(GamePlayer).filter(
            GamePlayer.game_id == game_id,
            GamePlayer.user_id == user_id
        ).first()
        
        if not game_player:
            await query.answer("Ошибка: игрок не найден", show_alert=True)
            return
        
        if not game_player.is_eliminated:
            await query.answer("Вы еще не выбыли из игры", show_alert=True)
            return
        
        if game_player.left_game:
            await query.answer("Вы уже вышли из игры", show_alert=True)
            return
        
        # Update player status
        if choice == "spectator":
            game_player.is_spectator = True
            await query.message.edit_text(
                "✅ Вы остались зрителем!\n\n"
                "Вы будете видеть вопросы и результаты раундов, но не сможете отвечать."
            )
        elif choice == "leave":
            game_player.is_spectator = False
            game_player.left_game = True
            session.commit()
            
            # Show main menu after leaving
            from bot.keyboards import MainMenuKeyboard
            await query.message.edit_text(
                "👋 Вы вышли из игры.\n\n"
                "Вы больше не будете получать уведомления об этой игре."
            )
            await query.message.reply_text(
                "Главное меню:",
                reply_markup=MainMenuKeyboard.get_keyboard()
            )
            
            logger.info(f"Player {user_id} chose {choice} for game {game_id}")
            return
        else:
            await query.answer("Неизвестный выбор", show_alert=True)
            return
        
        session.commit()
        logger.info(f"Player {user_id} chose {choice} for game {game_id}")


async def handle_leave_game(update: Update, context, data: str) -> None:
    """Handle leave-game callback (player exits and stops notifications)."""
    from database.session import db_session
    from database.models import GamePlayer, User
    
    query = update.callback_query
    user = update.effective_user
    
    # Parse callback data: leave_game:123:456
    parts = data.split(":")
    if len(parts) != 3:
        await query.answer("Ошибка в данных", show_alert=True)
        return
    
    try:
        game_id = int(parts[1])
        user_id = int(parts[2])
    except ValueError:
        await query.answer("Ошибка: неверный ID", show_alert=True)
        return
    
    with db_session() as session:
        db_user = session.query(User).filter(User.telegram_id == user.id).first()
        if not db_user or db_user.id != user_id:
            await query.answer("Ошибка: неверный пользователь", show_alert=True)
            return
        
        game_player = session.query(GamePlayer).filter(
            GamePlayer.game_id == game_id,
            GamePlayer.user_id == user_id
        ).first()
        
        if not game_player:
            await query.answer("Ошибка: игрок не найден", show_alert=True)
            return
        
        if game_player.left_game:
            await query.answer("Вы уже вышли из игры", show_alert=False)
            return
        
        game_player.left_game = True
        game_player.is_spectator = False
        if not game_player.is_eliminated:
            game_player.is_eliminated = True
        
        session.commit()
    
    # Try to remove inline keyboard to prevent further answers
    try:
        await query.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    
    from bot.keyboards import MainMenuKeyboard
    await query.message.reply_text(
        "👋 Вы вышли из игры.\n\n"
        "Вы больше не будете получать уведомления об этой игре.",
        reply_markup=MainMenuKeyboard.get_keyboard()
    )
    logger.info(f"Player {user_id} left game {game_id} via leave button")


async def handle_training_difficulty(update: Update, context, data: str) -> None:
    """Handle training difficulty selection."""
    from database.session import db_session
    from database.queries import UserQueries, GameQueries
    from database.models import GamePlayer
    from tasks.game_tasks import start_game_task
    
    query = update.callback_query
    user = update.effective_user
    
    # Parse difficulty
    try:
        difficulty = data.split(":")[1]
    except IndexError:
        await query.answer("Ошибка: неверный формат данных", show_alert=True)
        return
    
    difficulty_names = {
        'novice': 'Новичок',
        'amateur': 'Любитель',
        'expert': 'Эксперт'
    }
    difficulty_name = difficulty_names.get(difficulty, difficulty)
    
    try:
        with db_session() as session:
            # Get or create user
            db_user = UserQueries.get_or_create_user(
                session,
                telegram_id=user.id,
                username=user.username,
                full_name=f"{user.first_name} {user.last_name or ''}".strip()
            )
            
            # Create game
            game = GameQueries.create_game(
                session,
                game_type='training',
                creator_id=db_user.id,
                total_rounds=10
            )
            
            # Set bot difficulty for the game (use selected difficulty, not bot's stored difficulty)
            game.bot_difficulty = difficulty
            logger.info(f"Training game {game.id}: set bot_difficulty to '{difficulty}'")
            
            # Add user
            game_player = GamePlayer(
                game_id=game.id,
                user_id=db_user.id,
                is_bot=False,
                join_order=1
            )
            session.add(game_player)
            
            # Add bots (9 bots needed for 10 total players)
            # Use game's bot_difficulty, not bot's stored difficulty
            bots_needed = 9
            bots = UserQueries.get_bots(session, limit=bots_needed)
            
            if len(bots) < bots_needed:
                await query.message.reply_text(
                    f"⚠️ Доступно только {len(bots)} ботов, нужно {bots_needed}.\n"
                    f"Игра будет создана с {len(bots) + 1} игроками."
                )
            
            for i, bot in enumerate(bots, 2):
                # Use game's bot_difficulty, not bot's stored difficulty
                # This ensures all bots in the game have the same difficulty level
                bot_player = GamePlayer(
                    game_id=game.id,
                    user_id=bot.id,
                    is_bot=True,
                    bot_difficulty=difficulty,  # Use selected difficulty, not bot.bot_difficulty
                    join_order=i
                )
                session.add(bot_player)
                logger.debug(f"Training game {game.id}: added bot {bot.id} with difficulty '{difficulty}' as player {i}")
            
            session.commit()
            
            logger.info(f"Created training game {game.id} with {len(bots) + 1} players")
            
            # Start game asynchronously
            start_game_task.delay(game.id)
            
            await query.message.reply_text(
                f"✅ Игра создана!\n\n"
                f"🎮 Игра #{game.id}\n"
                f"🤖 Сложность ботов: {difficulty_name}\n"
                f"👥 Игроков: {len(bots) + 1}\n\n"
                f"Игра начинается..."
            )
            
    except Exception as e:
        logger.error(f"Error creating training game: {e}", exc_info=True)
        await query.message.reply_text(
            "❌ Произошла ошибка при создании игры. Попробуйте позже."
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
    
    # Handle user_shared (friends selection) - must be before TEXT handler
    # This handler catches ALL messages to check for user_shared attribute
    # It must be registered before the TEXT handler to catch user_shared updates first
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, user_shared_handler), group=0)
    
    # Handle text messages (after user_shared check)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler), group=1)
    
    application.add_handler(CallbackQueryHandler(callback_query_handler))
    
    # Start bot
    logger.info("Starting Trivia Bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
