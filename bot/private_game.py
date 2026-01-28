"""
Private game handlers and logic.
"""
from typing import Optional, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from database.session import db_session
from database.queries import UserQueries, GameQueries
from database.models import Game, GamePlayer
from utils.logging import get_logger
from tasks.game_tasks import start_game_task
import config

logger = get_logger(__name__)


async def create_private_game(update: Update, context) -> None:
    """Create private game when user clicks button - request friends selection."""
    user = update.effective_user
    user_id = user.id
    
    # Clear any previous selection state
    context.user_data.pop('selected_friends', None)
    
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
            # Cancel existing game
            existing_game.status = 'cancelled'
            session.commit()
    
    # Request users selection using KeyboardButton.request_user
    from telegram import ReplyKeyboardMarkup, KeyboardButton
    try:
        from telegram import KeyboardButtonRequestUser
    except ImportError:
        logger.warning("KeyboardButtonRequestUser not available")
        KeyboardButtonRequestUser = None
    
    # Note: request_user allows selecting one user at a time
    # We'll need to handle multiple selections differently
    if KeyboardButtonRequestUser:
        keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton(
                "👥 Выбрать друга",
                request_user=KeyboardButtonRequestUser(request_id=1)
            )]],
            one_time_keyboard=True,
            resize_keyboard=True
        )
    else:
        # Fallback - just show button without request_user
        keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton("👥 Выбрать друга")]],
            one_time_keyboard=True,
            resize_keyboard=True
        )
    
    await update.message.reply_text(
        "👥 Создание приватной игры\n\n"
        "📱 Нажмите кнопку ниже, чтобы выбрать друзей из контактов.\n"
        "Можно выбрать до 9 друзей (по одному). Оставшиеся места заполнятся ботами.",
        reply_markup=keyboard
    )


async def handle_private_game_create_with_friends(update: Update, context) -> None:
    """Create game with selected friends."""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    user_id = user.id
    
    # Get selected friends from context
    selected_friend_ids = context.user_data.get('selected_friends', [])
    
    if not selected_friend_ids:
        await query.edit_message_text("❌ Не выбрано ни одного друга.")
        return
    
    # Limit to 9 friends (creator is 10th)
    selected_friend_ids = selected_friend_ids[:9]
    
    with db_session() as session:
        # Get or create creator user
        db_creator = UserQueries.get_or_create_user(
            session,
            telegram_id=user_id,
            username=user.username,
            full_name=f"{user.first_name} {user.last_name or ''}".strip()
        )
        
        # Create new private game
        game = GameQueries.create_game(
            session,
            game_type='private',
            creator_id=db_creator.id,
            total_rounds=config.config.ROUNDS_PER_GAME
        )
        
        # Add creator as first player (auto-confirmed)
        creator_player = GamePlayer(
            game_id=game.id,
            user_id=db_creator.id,
            is_bot=False,
            join_order=1,
            is_confirmed=True
        )
        session.add(creator_player)
        
        # Add selected friends by their telegram IDs
        join_order = 2
        added_count = 0
        for friend_telegram_id in selected_friend_ids:
            # Get or create user in database by telegram_id
            db_user = UserQueries.get_or_create_user(
                session,
                telegram_id=friend_telegram_id,
                username=None,  # Will be updated if user exists
                full_name=None
            )
            
            # Check if already added (shouldn't happen, but just in case)
            existing = session.query(GamePlayer).filter(
                GamePlayer.game_id == game.id,
                GamePlayer.user_id == db_user.id
            ).first()
            
            if not existing:
                friend_player = GamePlayer(
                    game_id=game.id,
                    user_id=db_user.id,
                    is_bot=False,
                    join_order=join_order,
                    is_confirmed=False
                )
                session.add(friend_player)
                added_count += 1
                join_order += 1
        
        session.commit()
        
        # Save game.id before leaving the session context
        game_id = game.id
        
        logger.info(f"Created private game {game_id} by user {user_id} with {added_count} friends")
    
    # Clear selected friends from context
    context.user_data.pop('selected_friends', None)
    
    # Send invite requests to selected friends (accept/decline required)
    try:
        creator_name = user.first_name or user.username or "Друг"
        invite_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Принять", callback_data=f"private:invite_accept:{game_id}"),
                InlineKeyboardButton("❌ Отказаться", callback_data=f"private:invite_decline:{game_id}")
            ]
        ])
        for friend_telegram_id in selected_friend_ids:
            try:
                await context.bot.send_message(
                    chat_id=friend_telegram_id,
                    text=(
                        f"👋 {creator_name} приглашает вас в приватную игру!\n\n"
                        f"Нажмите «Принять», чтобы подтвердить участие."
                    ),
                    reply_markup=invite_keyboard
                )
            except Exception as e:
                logger.error(f"Failed to send private game invite to {friend_telegram_id}: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Failed to send private game invites for game {game_id}: {e}", exc_info=True)

    # Ask for bot difficulty (use game_id instead of game.id to avoid detached instance error)
    keyboard = [
        [
            InlineKeyboardButton("Новичок", callback_data=f"private:difficulty:{game_id}:novice"),
            InlineKeyboardButton("Любитель", callback_data=f"private:difficulty:{game_id}:amateur"),
            InlineKeyboardButton("Эксперт", callback_data=f"private:difficulty:{game_id}:expert")
        ]
    ]
    
    await query.edit_message_text(
        f"✅ Игра создана!\n\n"
        f"👥 Добавлено друзей: {added_count}\n"
        f"✅ Для старта требуется подтверждение от всех приглашённых\n\n"
        f"🤖 Выберите сложность ботов для заполнения оставшихся мест:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_private_game_users_selected(update: Update, context, user_shared) -> None:
    """Handle when user selects a friend from contacts."""
    user = update.effective_user
    user_id = user.id
    
    # Get selected user - request_user returns a single UserShared object
    # Extract user information
    logger.info(f"Processing user_shared: {user_shared}, type: {type(user_shared)}")
    
    # Log all attributes for debugging
    if hasattr(user_shared, '__dict__'):
        logger.info(f"user_shared.__dict__: {user_shared.__dict__}")
    if hasattr(user_shared, '__slots__'):
        logger.info(f"user_shared.__slots__: {user_shared.__slots__}")
    
    # Try to get all possible attributes
    attrs_to_check = ['user_id', 'id', 'user', 'telegram_id', 'request_id']
    for attr in attrs_to_check:
        if hasattr(user_shared, attr):
            value = getattr(user_shared, attr)
            logger.info(f"user_shared.{attr} = {value} (type: {type(value)})")
    
    selected_user_id = None
    if hasattr(user_shared, 'user_id'):
        selected_user_id = user_shared.user_id
        logger.info(f"Found user_id via user_shared.user_id: {selected_user_id}")
    elif hasattr(user_shared, 'id'):
        selected_user_id = user_shared.id
        logger.info(f"Found user_id via user_shared.id: {selected_user_id}")
    elif isinstance(user_shared, dict):
        selected_user_id = user_shared.get('user_id') or user_shared.get('id')
        logger.info(f"Found user_id from dict: {selected_user_id}")
    else:
        # Try to get user_id from any attribute
        for attr in ['user_id', 'id', 'user', 'telegram_id']:
            if hasattr(user_shared, attr):
                value = getattr(user_shared, attr)
                if isinstance(value, int):
                    selected_user_id = value
                    logger.info(f"Found user_id via {attr} (int): {selected_user_id}")
                    break
                elif hasattr(value, 'id'):
                    selected_user_id = value.id
                    logger.info(f"Found user_id via {attr}.id: {selected_user_id}")
                    break
    
    logger.info(f"Final extracted selected_user_id: {selected_user_id}")
    
    if not selected_user_id:
        logger.error(f"Could not extract user_id from user_shared: {user_shared}")
        await update.message.reply_text("❌ Ошибка при получении данных друга. Попробуйте снова.")
        return
    
    # Store selected user in context for accumulation
    if 'selected_friends' not in context.user_data:
        context.user_data['selected_friends'] = []
    
    # Check if user already selected
    if selected_user_id in context.user_data['selected_friends']:
        await update.message.reply_text("❌ Этот друг уже выбран.")
        return
    
    # Add to selected friends
    context.user_data['selected_friends'].append(selected_user_id)
    
    # Get user info from Telegram API if available
    selected_user = None
    if hasattr(user_shared, 'first_name'):
        selected_user = user_shared
    elif hasattr(user_shared, 'user'):
        selected_user = user_shared.user
    
    selected_count = len(context.user_data['selected_friends'])
    
    # Show current selection
    friends_text = f"✅ Выбрано друзей: {selected_count}/9\n\n"
    friends_text += f"Друг добавлен! (ID: {selected_user_id})\n\n"
    friends_text += "Продолжайте выбирать друзей или нажмите 'Готово' для создания игры."
    
    # Create keyboard with "Done" button
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
    try:
        from telegram import KeyboardButtonRequestUser
    except ImportError:
        # Fallback if KeyboardButtonRequestUser doesn't exist
        logger.warning("KeyboardButtonRequestUser not available, using alternative")
        KeyboardButtonRequestUser = None
    
    # Use ReplyKeyboardMarkup for request_user button
    if KeyboardButtonRequestUser:
        reply_keyboard = ReplyKeyboardMarkup(
            [
                [KeyboardButton(
                    "👥 Добавить ещё друга",
                    request_user=KeyboardButtonRequestUser(request_id=1)
                )]
            ],
            one_time_keyboard=True,
            resize_keyboard=True
        )
    else:
        # Fallback if KeyboardButtonRequestUser is not available
        reply_keyboard = ReplyKeyboardMarkup(
            [
                [KeyboardButton("👥 Добавить ещё друга")]
            ],
            one_time_keyboard=True,
            resize_keyboard=True
        )
    
    # Inline buttons for actions
    inline_keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ Готово, создать игру",
                callback_data="private:create_with_friends"
            )
        ],
        [
            InlineKeyboardButton(
                "❌ Отменить",
                callback_data="private:cancel_selection"
            )
        ]
    ])
    
    await update.message.reply_text(
        friends_text,
        reply_markup=reply_keyboard
    )
    
    # Send inline buttons separately
    await update.message.reply_text(
        "Или используйте кнопки ниже:",
        reply_markup=inline_keyboard
    )
    
    # Note: invite messages are sent after game creation with accept/decline buttons.
        


async def handle_private_game_difficulty(update: Update, context, game_id: int, difficulty: str) -> None:
    """Handle bot difficulty selection for private game."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    with db_session() as session:
        db_user = UserQueries.get_user_by_telegram_id(session, user_id)
        if not db_user:
            await query.edit_message_text("Ошибка: пользователь не найден")
            return
        
        # Get game
        game = GameQueries.get_game_by_id(session, game_id)
        if not game:
            await query.edit_message_text("Ошибка: игра не найдена")
            return
        
        if game.creator_id != db_user.id:
            await query.answer("Только создатель игры может выбрать сложность", show_alert=True)
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
        
        # Calculate bots needed
        bots_needed = 10 - players_count
        
        text = (
            f"✅ Сложность ботов: {difficulty_name}\n\n"
            f"👥 Игроков: {players_count}/10\n"
            f"🤖 Ботов будет добавлено: {bots_needed}\n\n"
            f"Готовы начать игру?"
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
            reply_markup=InlineKeyboardMarkup(keyboard)
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
            if not existing_player.is_confirmed:
                existing_player.is_confirmed = True
                session.commit()
                await update.message.reply_text("✅ Вы подтвердили участие в игре!")
            else:
                await update.message.reply_text("✅ Вы уже в этой игре!")
            return
        
        # Check if game is full
        players_count = session.query(GamePlayer).filter(
            GamePlayer.game_id == game_id
        ).count()
        
        if players_count >= 10:
            await update.message.reply_text("❌ Игра уже заполнена (10/10)")
            return
        
        # Add player (confirmed by joining via invite link)
        game_player = GamePlayer(
            game_id=game_id,
            user_id=db_user.id,
            is_bot=False,
            join_order=players_count + 1,
            is_confirmed=True
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
        
        # Ensure all invited players confirmed
        pending_count = session.query(GamePlayer).filter(
            GamePlayer.game_id == game_id,
            GamePlayer.is_bot == False,
            GamePlayer.is_confirmed == False
        ).count()
        if pending_count > 0:
            await query.answer(
                f"Ожидаем подтверждения от {pending_count} игрок(ов)",
                show_alert=True
            )
            return

        # Get current players
        players = GameQueries.get_game_players(session, game_id)
        players_count = len(players)
        logger.info(f"Private game {game_id}: current players count = {players_count}")
        
        # Fill remaining slots with bots
        bots_needed = 10 - players_count
        logger.info(f"Private game {game_id}: bots needed = {bots_needed}")
        
        if bots_needed > 0:
            bot_difficulty = game.bot_difficulty or 'novice'  # Default to novice
            logger.info(f"Private game {game_id}: requesting {bots_needed} bots with difficulty '{bot_difficulty}'")
            
            bots = UserQueries.get_bots(session, difficulty=bot_difficulty, limit=bots_needed)
            logger.info(f"Private game {game_id}: found {len(bots)} bots in database")
            
            if len(bots) < bots_needed:
                logger.warning(f"Private game {game_id}: Only {len(bots)} bots available, need {bots_needed}. Trying to get bots without difficulty filter...")
                # Try to get bots without difficulty filter if not enough with specific difficulty
                all_bots = UserQueries.get_bots(session, difficulty=None, limit=bots_needed)
                logger.info(f"Private game {game_id}: found {len(all_bots)} bots total (without difficulty filter)")
                # Use all available bots, prioritizing those with matching difficulty
                bots = bots + [b for b in all_bots if b not in bots][:bots_needed - len(bots)]
                logger.info(f"Private game {game_id}: using {len(bots)} bots total")
            
            added_bots_count = 0
            for i, bot in enumerate(bots[:bots_needed], players_count + 1):
                # Use game's bot_difficulty, not bot's stored difficulty
                # This ensures all bots in the game have the same difficulty level
                bot_player = GamePlayer(
                    game_id=game_id,
                    user_id=bot.id,
                    is_bot=True,
                    bot_difficulty=bot_difficulty,  # Use game's difficulty setting
                    join_order=i
                )
                session.add(bot_player)
                added_bots_count += 1
                logger.info(f"Private game {game_id}: added bot {bot.id} with game difficulty '{bot_difficulty}' as player {i}")
            
            logger.info(f"Private game {game_id}: added {added_bots_count} bots, total players now: {players_count + added_bots_count}")
        else:
            logger.info(f"Private game {game_id}: no bots needed, already has {players_count} players")
        
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


async def handle_private_game_invite_response(update: Update, context, game_id: int, accepted: bool) -> None:
    """Handle accept/decline for private game invite."""
    query = update.callback_query
    user = update.effective_user
    user_id = user.id

    with db_session() as session:
        db_user = UserQueries.get_user_by_telegram_id(session, user_id)
        if not db_user:
            await query.answer("Ошибка: пользователь не найден", show_alert=True)
            return

        game = GameQueries.get_game_by_id(session, game_id)
        if not game:
            await query.answer("Ошибка: игра не найдена", show_alert=True)
            return

        if game.game_type != 'private' or game.status != 'waiting':
            await query.answer("Игра уже началась или отменена", show_alert=True)
            return

        game_player = session.query(GamePlayer).filter(
            GamePlayer.game_id == game_id,
            GamePlayer.user_id == db_user.id
        ).first()

        if not game_player:
            await query.answer("Вы не приглашены в эту игру", show_alert=True)
            return

        if accepted:
            game_player.is_confirmed = True
            session.commit()
            await query.answer("Вы подтвердили участие", show_alert=False)
            await query.edit_message_text("✅ Вы подтвердили участие в приватной игре.")
        else:
            # Decline: remove player from game
            session.delete(game_player)
            session.commit()
            await query.answer("Вы отказались", show_alert=False)
            await query.edit_message_text("❌ Вы отказались от участия в приватной игре.")

        # Notify creator
        creator = session.query(User).filter(User.id == game.creator_id).first()
        if creator and creator.telegram_id:
            try:
                status_text = "принял(а)" if accepted else "отказался(ась)"
                await context.bot.send_message(
                    chat_id=creator.telegram_id,
                    text=f"👤 Пользователь {db_user.full_name or db_user.username or db_user.id} {status_text} приглашение в игру #{game_id}."
                )
            except Exception as e:
                logger.error(f"Failed to notify creator about invite response: {e}", exc_info=True)


async def handle_private_game_callback(update: Update, context, data: str) -> None:
    """Route private game callbacks to appropriate handlers."""
    # Parse callback data: private:action:param
    parts = data.split(":", 2)
    if len(parts) < 2:
        logger.warning(f"Invalid private game callback data: {data}")
        return
    
    action = parts[1]
    param = parts[2] if len(parts) > 2 else ""
    
    if action == "create_with_friends":
        # Handle creating game with selected friends
        await handle_private_game_create_with_friends(update, context)
    elif action == "cancel_selection":
        # Handle canceling friend selection
        query = update.callback_query
        await query.answer("Выбор друзей отменён")
        
        # Clear context
        context.user_data.pop('selected_friends', None)
        
        # Restore main menu
        from bot.keyboards import MainMenuKeyboard
        await query.edit_message_text("❌ Выбор друзей отменён")
        await query.message.reply_text(
            "Главное меню:",
            reply_markup=MainMenuKeyboard.get_keyboard()
        )
    elif action == "difficulty":
        # Handle difficulty selection: private:difficulty:game_id:difficulty
        parts = param.split(":", 1)
        if len(parts) == 2:
            try:
                game_id = int(parts[0])
                difficulty = parts[1]
                await handle_private_game_difficulty(update, context, game_id, difficulty)
            except ValueError:
                logger.error(f"Invalid game_id or difficulty in callback: {param}")
        else:
            # Legacy format: private:difficulty:difficulty (without game_id)
            await handle_private_game_difficulty(update, context, 0, param)
    elif action == "invite_accept":
        try:
            game_id = int(param)
            await handle_private_game_invite_response(update, context, game_id, True)
        except ValueError:
            logger.error(f"Invalid game_id in callback: {param}")
    elif action == "invite_decline":
        try:
            game_id = int(param)
            await handle_private_game_invite_response(update, context, game_id, False)
        except ValueError:
            logger.error(f"Invalid game_id in callback: {param}")
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
