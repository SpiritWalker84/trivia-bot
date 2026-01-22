"""
Vote dispatcher - processes game voting results.
"""
from typing import Dict, List
from celery import Task
from database.session import db_session
from database.models import Game, GamePlayer, GameVote, Pool
from database.queries import GameQueries, PoolQueries, UserQueries
from tasks.celery_app import celery_app
from utils.logging import get_logger
import config

logger = get_logger(__name__)


@celery_app.task(name="tasks.vote_dispatcher.process_game_vote", bind=True)
def process_game_vote(self: Task, game_id: int) -> None:
    """
    Process game vote after voting period ends.
    
    Args:
        game_id: Game ID
    """
    from datetime import datetime
    import pytz
    from game.engine import GameEngine
    from database.models import PoolPlayer
    
    with db_session() as session:
        # Get game with lock
        game = session.query(Game).filter(Game.id == game_id).with_for_update().first()
        
        if not game:
            logger.warning(f"Game {game_id} not found")
            return
        
        if game.status != 'pre_start':
            logger.info(f"Game {game_id} is not in pre_start status: {game.status}")
            return
        
        # Get players
        players = [
            gp.user_id for gp in game.players
            if not gp.is_bot
        ]
        n_players = len(players)
        
        # Get votes
        votes = session.query(GameVote).filter(GameVote.game_id == game_id).all()
        vote_by_user = {v.user_id: v.vote for v in votes}
        
        # Check if all voted "wait"
        all_wait = True
        for user_id in players:
            vote = vote_by_user.get(user_id)
            if vote is None:
                # No answer = agreement to start
                all_wait = False
                break
            if vote == 'start_now':
                all_wait = False
                break
        
        if all_wait:
            # Branch 1: All voted "wait" - return players to pool
            logger.info(f"Game {game_id}: All voted wait - returning to pool")
            
            # Get or create pool
            pool = PoolQueries.get_or_create_active_pool(session)
            
            # Add players back to pool
            for user_id in players:
                pool_player = PoolPlayer(
                    pool_id=pool.id,
                    user_id=user_id
                )
                session.merge(pool_player)
            
            # Cancel game
            game.status = 'cancelled'
            session.commit()
            
            # TODO: Notify players
            return
        
        # Branch 2: Start with bots
        logger.info(f"Game {game_id}: Starting with bots")
        
        # Calculate bots needed
        n_live = n_players
        n_total = config.config.PLAYERS_PER_GAME
        n_bots_needed = max(0, n_total - n_live)
        
        if n_bots_needed > 0:
            # Get bots
            bots = UserQueries.get_bots(session, limit=n_bots_needed)
            
            # Add bots to game
            current_max_order = max(
                (gp.join_order for gp in game.players),
                default=0
            )
            
            for i, bot in enumerate(bots, 1):
                game_player = GamePlayer(
                    game_id=game.id,
                    user_id=bot.id,
                    is_bot=True,
                    bot_difficulty=bot.bot_difficulty,
                    join_order=current_max_order + i
                )
                session.add(game_player)
        
        # Update game status
        game.status = 'in_progress'
        game.started_at = datetime.now(pytz.UTC)
        session.commit()
        
        # Start game (async task)
        from tasks.game_tasks import start_game_task
        start_game_task.delay(game_id)
        
        logger.info(f"Game {game_id} scheduled to start with {n_live} players and {n_bots_needed} bots")
