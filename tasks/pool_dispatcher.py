"""
Pool dispatcher - manages quick game pool and starts games.
Runs every 5 minutes.
"""
from typing import List, Optional
from datetime import datetime
import pytz
from celery import Task
from database.session import db_session
from database.models import GamePlayer
from database.queries import (
    PoolQueries,
    GameQueries,
    UserQueries,
)
from tasks.celery_app import celery_app
from tasks.vote_dispatcher import process_game_vote
from utils.logging import get_logger
import config

logger = get_logger(__name__)


@celery_app.task(name="tasks.pool_dispatcher.check_pool", bind=True)
def check_pool(self: Task) -> None:
    """
    Check pool and process players.
    Runs every 5 minutes.
    """
    with db_session() as session:
        # Get active pool
        pool = PoolQueries.get_or_create_active_pool(session)
        
        if pool.status != 'waiting':
            logger.debug(f"Pool {pool.id} is not in waiting status: {pool.status}")
            return
        
        # Update last_check_at
        pool.last_check_at = datetime.now(pytz.UTC)
        session.flush()
        
        # Get players
        players = PoolQueries.get_pool_players(session, pool.id)
        n_players = len(players)
        
        logger.info(f"Pool {pool.id}: {n_players} players in queue")
        
        # Branch A: 0 players - do nothing
        if n_players == 0:
            logger.debug(f"Pool {pool.id}: no players, waiting...")
            return
        
        # Branch B: 1-2 players - suggest training
        if n_players in (1, 2):
            logger.info(f"Pool {pool.id}: {n_players} players - suggesting training")
            # TODO: Send training suggestion messages
            return
        
        # Branch C: 10+ players - instant start
        if n_players >= 10:
            logger.info(f"Pool {pool.id}: {n_players} players - starting game immediately")
            player_ids = [p.user_id for p in players[:10]]
            session.commit()
            start_game_from_pool.delay(pool.id, player_ids)
            return
        
        # Branch D: 3-9 players - start voting
        if 3 <= n_players <= 9:
            logger.info(f"Pool {pool.id}: {n_players} players - starting vote")
            player_ids = [p.user_id for p in players]
            session.commit()
            start_voting_from_pool.delay(pool.id, player_ids)


@celery_app.task(name="tasks.pool_dispatcher.start_game_from_pool")
def start_game_from_pool(pool_id: int, player_ids: List[int]) -> None:
    """Start game with selected players from pool."""
    from datetime import datetime
    import pytz
    from game.engine import GameEngine
    from database.models import GamePlayer, PoolPlayer, Pool
    
    with db_session() as session:
        # Check active games limit
        active_count = GameQueries.get_active_games_count(session)
        if active_count >= config.config.MAX_ACTIVE_GAMES:
            logger.warning(f"Max active games reached ({active_count}), cannot start new game")
            # TODO: Notify players
            return
        
        # Create game
        game = GameQueries.create_game(
            session,
            game_type='quick',
            theme_id=None,  # Mixed theme
            total_rounds=config.config.ROUNDS_PER_GAME
        )
        
        # Add players
        for i, user_id in enumerate(player_ids, 1):
            game_player = GamePlayer(
                game_id=game.id,
                user_id=user_id,
                is_bot=False,
                join_order=i
            )
            session.add(game_player)
        
        # Remove players from pool
        pool = session.query(Pool).filter(Pool.id == pool_id).first()
        if pool:
            pool_players = session.query(PoolPlayer).filter(
                PoolPlayer.pool_id == pool_id,
                PoolPlayer.user_id.in_(player_ids)
            ).all()
            for pool_player in pool_players:
                session.delete(pool_player)
        
        game.status = 'in_progress'
        session.commit()
        
        # Start game (async task)
        from tasks.game_tasks import start_game_task
        start_game_task.delay(game.id)
        
        logger.info(f"Game {game.id} scheduled to start with {len(player_ids)} players")


@celery_app.task(name="tasks.pool_dispatcher.start_voting_from_pool")
def start_voting_from_pool(pool_id: int, player_ids: List[int]) -> None:
    """Start voting for game with players from pool."""
    from datetime import datetime, timedelta
    import pytz
    from database.models import GamePlayer, PoolPlayer, Pool
    
    with db_session() as session:
        # Check active games limit
        active_count = GameQueries.get_active_games_count(session)
        if active_count >= config.config.MAX_ACTIVE_GAMES:
            logger.warning(f"Max active games reached ({active_count}), cannot start voting")
            return
        
        # Create game in pre_start status
        game = GameQueries.create_game(
            session,
            game_type='quick',
            theme_id=None,
            total_rounds=config.config.ROUNDS_PER_GAME
        )
        game.status = 'pre_start'
        session.flush()
        
        # Add players
        for i, user_id in enumerate(player_ids, 1):
            game_player = GamePlayer(
                game_id=game.id,
                user_id=user_id,
                is_bot=False,
                join_order=i
            )
            session.add(game_player)
        
        # Remove players from pool
        pool = session.query(Pool).filter(Pool.id == pool_id).first()
        if pool:
            pool_players = session.query(PoolPlayer).filter(
                PoolPlayer.pool_id == pool_id,
                PoolPlayer.user_id.in_(player_ids)
            ).all()
            for pool_player in pool_players:
                session.delete(pool_player)
        
        session.commit()
        
        # Send vote messages to players
        try:
            from telegram import Bot
            from bot.game_notifications import GameNotifications
            import asyncio
            
            bot = Bot(token=config.config.TELEGRAM_BOT_TOKEN)
            notifications = GameNotifications(bot)
            asyncio.run(notifications.send_vote_message(game.id, len(player_ids)))
        except Exception as e:
            logger.error(f"Failed to send vote messages: {e}")
        
        # Schedule vote processing after vote duration
        process_game_vote.apply_async(
            args=[game.id],
            countdown=config.config.VOTE_DURATION
        )
        
        logger.info(f"Voting started for game {game.id} with {len(player_ids)} players")


# Periodic task: run check_pool every 5 minutes
@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Setup periodic tasks."""
    sender.add_periodic_task(
        config.config.POOL_CHECK_INTERVAL,
        check_pool.s(),
        name="Check pool every 5 minutes"
    )
