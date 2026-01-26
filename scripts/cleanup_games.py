#!/usr/bin/env python3
"""
Script to cleanup all active games and cancel all Celery tasks.
Use this to reset the game state when there are stuck games or tasks.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.session import db_session
from database.models import Game, Round, RoundQuestion, Answer, GamePlayer
from utils.logging import get_logger, setup_logging
import config

setup_logging()
logger = get_logger(__name__)


def cleanup_all_games():
    """Cleanup all active games and cancel all related tasks."""
    logger.info("Starting game cleanup...")
    
    with db_session() as session:
        # Get all active games
        active_games = session.query(Game).filter(
            Game.status.in_(['in_progress', 'pre_start', 'waiting'])
        ).all()
        
        logger.info(f"Found {len(active_games)} active games to cleanup")
        
        for game in active_games:
            logger.info(f"Cleaning up game {game.id} (status: {game.status})")
            
            # Update game status to cancelled
            game.status = 'cancelled'
            
            # Get all rounds for this game
            rounds = session.query(Round).filter(Round.game_id == game.id).all()
            logger.info(f"  Found {len(rounds)} rounds for game {game.id}")
            
            for round_obj in rounds:
                # Update round status to finished
                if round_obj.status != 'finished':
                    round_obj.status = 'finished'
                    if not round_obj.finished_at:
                        from datetime import datetime
                        import pytz
                        round_obj.finished_at = datetime.now(pytz.UTC)
        
        session.commit()
        logger.info(f"Updated {len(active_games)} games to cancelled status")
    
    # Cancel all Celery tasks
    try:
        from tasks.celery_app import celery_app
        
        # Get active tasks
        inspect = celery_app.control.inspect()
        
        # Check if Celery workers are available
        active_workers = inspect.active()
        if active_workers is None:
            logger.warning("No Celery workers available or Celery is not running")
            logger.info("To cancel tasks, make sure Celery worker is running")
        else:
            # Get active tasks
            active_tasks = inspect.active()
            
            if active_tasks:
                logger.info("Found active Celery tasks:")
                for worker, tasks in active_tasks.items():
                    logger.info(f"  Worker {worker}: {len(tasks)} tasks")
                    for task in tasks:
                        task_id = task.get('id')
                        task_name = task.get('name')
                        logger.info(f"    - {task_name} (id: {task_id})")
                        
                        # Try to revoke the task
                        try:
                            celery_app.control.revoke(task_id, terminate=True)
                            logger.info(f"      Revoked task {task_id}")
                        except Exception as e:
                            logger.warning(f"      Failed to revoke task {task_id}: {e}")
            else:
                logger.info("No active Celery tasks found")
            
            # Also revoke scheduled tasks
            scheduled_tasks = inspect.scheduled()
            if scheduled_tasks:
                logger.info("Found scheduled Celery tasks:")
                for worker, tasks in scheduled_tasks.items():
                    logger.info(f"  Worker {worker}: {len(tasks)} scheduled tasks")
                    for task in tasks:
                        task_id = task.get('request', {}).get('id')
                        task_name = task.get('request', {}).get('task')
                        if task_id:
                            try:
                                celery_app.control.revoke(task_id, terminate=True)
                                logger.info(f"      Revoked scheduled task {task_id} ({task_name})")
                            except Exception as e:
                                logger.warning(f"      Failed to revoke scheduled task {task_id}: {e}")
            else:
                logger.info("No scheduled Celery tasks found")
            
    except Exception as e:
        logger.error(f"Error canceling Celery tasks: {e}", exc_info=True)
        logger.info("Note: This is normal if Celery is not running. Tasks will be cleaned up when Celery restarts.")
    
    logger.info("Game cleanup completed!")


if __name__ == "__main__":
    try:
        cleanup_all_games()
        print("✅ Cleanup completed successfully!")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}", exc_info=True)
        print(f"❌ Error during cleanup: {e}")
        sys.exit(1)
