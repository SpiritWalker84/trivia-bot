"""
Private game handlers and logic.
"""
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from database.session import db_session
from database.queries import UserQueries, GameQueries
from database.models import Game, GamePlayer
from utils.logging import get_logger
from tasks.game_tasks import start_game_task

logger = get_logger(__name__)


async def create_private_game(update: Update, context) -> None:
    """Create private game when user clicks button."""
    user = update.effective_user
    user_id = user.id
    
    with db_session() as session:
        # Get or create user
        db_user = UserQueries.get_or_create_user(
            session,
            telegram_id=user_id,
            username=user.username,
            full_name=f"{user.first_name} {user.last_name or ''}".strip()
        )
        
        # Check if user already has a waiting private game
        existing_game = session.query(Game).filter(
            Game.game_type == 'private',
            Game.creator_id == db_user.id,
            Game.status == 'waiting'
        ).first()
        
        if existing_game:
            # Check how many players already joined
            players_count = session.query(GamePlayer).filter(
                GamePlayer.game_id == existing_game.id
            ).count()
            
            # Get bot username from context if available
            bot_username = "your_bot"  # Default
            if context and hasattr(context, 'bot') and context.bot:
                bot_username = context.bot.username or "your_bot"
            
            invite_link = f"https://t.me/{bot_username}?start=private_{existing_game.id}"
            
            await update.message.reply_text(
                f"👥 У вас уже есть приватная игра!\n\n"
                f"Игроков: {players_count}/10\n\n"
                f"Поделитесь ссылкой с друзьями:\n"
                f"`{invite_link}`\n\n"
                f"Или попросите их ввести:\n"
                f"`/start private_{existing_game.id}`",
                parse_mode='Markdown'
            )
            return
        
        # Create new private game
        game = GameQueries.create_game(
            session,
            game_type='private',
            creator_id=db_user.id,
            total_rounds=10
        )
        
        # Add creator as first player
        game_player = GamePlayer(
            game_id=game.id,
            user_id=db_user.id,
            is_bot=False,
            join_order=1
        )
        session.add(game_player)
        session.commit()
        
        logger.info(f"Created private game {game.id} by user {user_id}")
    
    # Ask for bot difficulty - use a custom keyboard that routes to private game handler
    keyboard = [
        [
            InlineKeyboardButton("Новичок", callback_data="private:difficulty:novice"),
            InlineKeyboardButton("Любитель", callback_data="private:difficulty:amateur"),
            InlineKeyboardButton("Эксперт", callback_data="private:difficulty:expert")
        ]
    ]
    
    await update.message.reply_text(
        "👥 Приватная игра создана!\n\n"
        "🤖 Выберите сложность ботов для заполнения оставшихся мест:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_private_game_difficulty(update: Update, context, difficulty: str) -> None:
    """Handle bot difficulty selection for private game."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    with db_session() as session:
        db_user = UserQueries.get_user_by_telegram_id(session, user_id)
        if not db_user:
            await query.edit_message_text("Ошибка: пользователь не найден")
            return
        
        # Find waiting private game created by this user
        game = session.query(Game).filter(
            Game.game_type == 'private',
            Game.creator_id == db_user.id,
            Game.status == 'waiting'
        ).first()
        
        if not game:
            await query.edit_message_text("Ошибка: игра не найдена")
            return
        
        # Store bot difficulty
        game.bot_difficulty = difficulty
        session.commit()
        
        # Get current players count
        players_count = session.query(GamePlayer).filter(
            GamePlayer.game_id == game.id
        ).count()
        
        difficulty_map = {
            'novice': 'Новичок',
            'amateur': 'Любитель',
            'expert': 'Эксперт'
        }
        difficulty_name = difficulty_map.get(difficulty, difficulty)
        
        # Get bot username from context if available
        bot_username = "your_bot"  # Default
        if context and hasattr(context, 'bot') and context.bot:
            bot_username = context.bot.username or "your_bot"
        
        invite_link = f"https://t.me/{bot_username}?start=private_{game.id}"
        
        text = (
            f"✅ Сложность ботов: {difficulty_name}\n\n"
            f"👥 Игроков: {players_count}/10\n\n"
            f"📤 Пригласите друзей:\n"
            f"1. Отправьте им ссылку:\n"
            f"`{invite_link}`\n\n"
            f"2. Или попросите их ввести команду:\n"
            f"`/start private_{game.id}`\n\n"
            f"Оставшиеся места будут заполнены ботами."
        )
        
        keyboard = [
            [
                InlineKeyboardButton(
                    "▶️ Начать игру",
                    callback_data=f"private:start:{game.id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "❌ Отменить игру",
                    callback_data=f"private:cancel:{game.id}"
                )
            ]
        ]
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )


async def handle_private_game_invite(update: Update, context, game_id: int) -> None:
    """Handle friend joining private game via invite link."""
    user = update.effective_user
    user_id = user.id
    
    with db_session() as session:
        # Get or create user
        db_user = UserQueries.get_or_create_user(
            session,
            telegram_id=user_id,
            username=user.username,
            full_name=f"{user.first_name} {user.last_name or ''}".strip()
        )
        
        # Get game
        game = GameQueries.get_game_by_id(session, game_id)
        if not game:
            await update.message.reply_text("❌ Игра не найдена")
            return
        
        if game.game_type != 'private':
            await update.message.reply_text("❌ Это не приватная игра")
            return
        
        if game.status != 'waiting':
            await update.message.reply_text("❌ Игра уже началась или отменена")
            return
        
        # Check if user is already in game
        existing_player = session.query(GamePlayer).filter(
            GamePlayer.game_id == game_id,
            GamePlayer.user_id == db_user.id
        ).first()
        
        if existing_player:
            await update.message.reply_text("✅ Вы уже в этой игре!")
            return
        
        # Check if game is full
        players_count = session.query(GamePlayer).filter(
            GamePlayer.game_id == game_id
        ).count()
        
        if players_count >= 10:
            await update.message.reply_text("❌ Игра уже заполнена (10/10)")
            return
        
        # Add player
        game_player = GamePlayer(
            game_id=game_id,
            user_id=db_user.id,
            is_bot=False,
            join_order=players_count + 1
        )
        session.add(game_player)
        session.commit()
        
        logger.info(f"User {user_id} joined private game {game_id}")
        
        await update.message.reply_text(
            f"✅ Вы присоединились к приватной игре!\n\n"
            f"Игроков: {players_count + 1}/10\n\n"
            f"Ожидайте начала игры..."
        )


async def handle_private_game_start(update: Update, context, game_id: int) -> None:
    """Handle start private game button."""
    query = update.callback_query
    user_id = update.effective_user.id
    
    with db_session() as session:
        db_user = UserQueries.get_user_by_telegram_id(session, user_id)
        if not db_user:
            await query.answer("Ошибка: пользователь не найден", show_alert=True)
            return
        
        game = GameQueries.get_game_by_id(session, game_id)
        if not game:
            await query.answer("Ошибка: игра не найдена", show_alert=True)
            return
        
        if game.creator_id != db_user.id:
            await query.answer("Только создатель игры может её начать", show_alert=True)
            return
        
        if game.status != 'waiting':
            await query.answer("Игра уже началась", show_alert=True)
            return
        
        # Get current players
        players = GameQueries.get_game_players(session, game_id)
        players_count = len(players)
        
        # Fill remaining slots with bots
        bots_needed = 10 - players_count
        if bots_needed > 0:
            bot_difficulty = game.bot_difficulty or 'novice'  # Default to novice
            bots = UserQueries.get_bots(session, difficulty=bot_difficulty, limit=bots_needed)
            
            if len(bots) < bots_needed:
                logger.warning(f"Only {len(bots)} bots available, need {bots_needed}")
            
            for i, bot in enumerate(bots[:bots_needed], players_count + 1):
                bot_player = GamePlayer(
                    game_id=game_id,
                    user_id=bot.id,
                    is_bot=True,
                    bot_difficulty=bot.bot_difficulty,
                    join_order=i
                )
                session.add(bot_player)
        
        # Update game status
        game.status = 'pre_start'
        session.commit()
        
        logger.info(f"Private game {game_id} starting with {10} players")
    
    await query.answer("Игра начинается!")
    await query.edit_message_text("▶️ Игра начинается...")
    
    # Start game
    start_game_task.delay(game_id)


async def handle_private_game_cancel(update: Update, context, game_id: int) -> None:
    """Handle cancel private game button."""
    query = update.callback_query
    user_id = update.effective_user.id
    
    with db_session() as session:
        db_user = UserQueries.get_user_by_telegram_id(session, user_id)
        if not db_user:
            await query.answer("Ошибка: пользователь не найден", show_alert=True)
            return
        
        game = GameQueries.get_game_by_id(session, game_id)
        if not game:
            await query.answer("Ошибка: игра не найдена", show_alert=True)
            return
        
        if game.creator_id != db_user.id:
            await query.answer("Только создатель игры может её отменить", show_alert=True)
            return
        
        if game.status != 'waiting':
            await query.answer("Игра уже началась", show_alert=True)
            return
        
        # Cancel game
        game.status = 'cancelled'
        session.commit()
        
        logger.info(f"Private game {game_id} cancelled by user {user_id}")
    
    await query.answer("Игра отменена")
    await query.edit_message_text("❌ Игра отменена")


async def handle_private_game_callback(update: Update, context, data: str) -> None:
    """Route private game callbacks to appropriate handlers."""
    # Parse callback data: private:action:param
    parts = data.split(":", 2)
    if len(parts) < 3:
        logger.warning(f"Invalid private game callback data: {data}")
        return
    
    action = parts[1]
    param = parts[2]
    
    if action == "difficulty":
        # Handle difficulty selection
        await handle_private_game_difficulty(update, context, param)
    elif action == "start":
        # Handle start game
        try:
            game_id = int(param)
            await handle_private_game_start(update, context, game_id)
        except ValueError:
            logger.error(f"Invalid game_id in callback: {param}")
    elif action == "cancel":
        # Handle cancel game
        try:
            game_id = int(param)
            await handle_private_game_cancel(update, context, game_id)
        except ValueError:
            logger.error(f"Invalid game_id in callback: {param}")
    else:
        logger.warning(f"Unknown private game action: {action}")
