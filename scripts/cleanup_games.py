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
            
            # Reset current_round to prevent continuation
            game.current_round = None
            
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
    
    # Clear Redis directly FIRST (this works even if Celery is not running)
    logger.info("Clearing Redis queues directly...")
    try:
        import redis
        from urllib.parse import urlparse
        
        broker_url = config.config.CELERY_BROKER_URL
        logger.info(f"Connecting to Redis: {broker_url}")
        
        # Connect to Redis
        redis_client = redis.from_url(broker_url, decode_responses=False)
        
        # Get all keys related to Celery
        celery_keys = redis_client.keys('celery*')
        if celery_keys:
            logger.info(f"Found {len(celery_keys)} Celery-related keys in Redis")
            # Delete all Celery keys
            deleted = 0
            for key in celery_keys:
                redis_client.delete(key)
                deleted += 1
            logger.info(f"✅ Deleted {deleted} Celery keys from Redis")
        else:
            logger.info("No Celery keys found in Redis")
        
        # Also clear specific queue names that Celery uses
        queue_names = ['celery', 'default']
        for queue_name in queue_names:
            try:
                queue_key = queue_name
                queue_length = redis_client.llen(queue_key)
                if queue_length > 0:
                    redis_client.delete(queue_key)
                    logger.info(f"✅ Cleared queue '{queue_name}' ({queue_length} tasks)")
            except Exception as e:
                logger.debug(f"Could not check/clear queue '{queue_name}': {e}")
        
        # Also try to clear all keys matching common Celery patterns
        patterns = ['celery-task-meta-*', '_kombu.binding.*']
        for pattern in patterns:
            try:
                keys = redis_client.keys(pattern)
                if keys:
                    deleted = redis_client.delete(*keys)
                    logger.info(f"✅ Deleted {deleted} keys matching pattern '{pattern}'")
            except Exception as e:
                logger.debug(f"Could not clear pattern '{pattern}': {e}")
                
    except ImportError:
        logger.warning("Redis library not installed. Install with: pip install redis")
    except Exception as e:
        logger.warning(f"Could not clear Redis directly: {e}")
        logger.info("This is normal if Redis is not accessible or Celery uses a different broker")
    
    # Cancel all Celery tasks (this requires Celery to be running)
    try:
        from tasks.celery_app import celery_app
        
        # Try to purge all Celery queues via Celery API
        logger.info("Purging Celery queues via Celery API...")
        try:
            # Purge all queues
            purged = celery_app.control.purge()
            if purged:
                logger.info(f"Purged {sum(purged.values())} tasks from Celery queues")
                for worker, count in purged.items():
                    if count > 0:
                        logger.info(f"  Worker {worker}: purged {count} tasks")
            else:
                logger.info("No tasks found in Celery queues to purge (via Celery API)")
        except Exception as e:
            logger.warning(f"Failed to purge Celery queues via API: {e}")
            logger.info("This is normal if Celery is not running")
        
        # Get active tasks
        inspect = celery_app.control.inspect()
        
        # Check if Celery workers are available
        active_workers = inspect.active()
        if active_workers is None:
            logger.warning("No Celery workers available or Celery is not running")
            logger.info("Tasks in Redis queues have been purged. Workers will not process old tasks when restarted.")
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
            
            # Also check reserved tasks
            reserved_tasks = inspect.reserved()
            if reserved_tasks:
                logger.info("Found reserved Celery tasks:")
                for worker, tasks in reserved_tasks.items():
                    logger.info(f"  Worker {worker}: {len(tasks)} reserved tasks")
                    for task in tasks:
                        task_id = task.get('id')
                        task_name = task.get('name')
                        if task_id:
                            try:
                                celery_app.control.revoke(task_id, terminate=True)
                                logger.info(f"      Revoked reserved task {task_id} ({task_name})")
                            except Exception as e:
                                logger.warning(f"      Failed to revoke reserved task {task_id}: {e}")
            else:
                logger.info("No reserved Celery tasks found")
            
    except Exception as e:
        logger.error(f"Error canceling Celery tasks: {e}", exc_info=True)
        logger.info("Note: This is normal if Celery is not running. Tasks in Redis have been purged.")
    
    # Also clear Redis directly as a fallback
    try:
        import redis
        from urllib.parse import urlparse
        
        broker_url = config.config.CELERY_BROKER_URL
        parsed = urlparse(broker_url)
        
        # Connect to Redis
        redis_client = redis.from_url(broker_url, decode_responses=False)
        
        # Get all keys related to Celery
        celery_keys = redis_client.keys('celery*')
        if celery_keys:
            logger.info(f"Found {len(celery_keys)} Celery-related keys in Redis")
            # Delete all Celery keys
            for key in celery_keys:
                redis_client.delete(key)
            logger.info("Cleared all Celery keys from Redis")
        else:
            logger.info("No Celery keys found in Redis")
            
        # Also clear the default queue
        try:
            queue_name = celery_app.conf.task_default_queue
            queue_key = f"{queue_name}"
            # Try to get queue length
            queue_length = redis_client.llen(queue_key)
            if queue_length > 0:
                redis_client.delete(queue_key)
                logger.info(f"Cleared queue '{queue_name}' ({queue_length} tasks)")
        except Exception as e:
            logger.debug(f"Could not clear default queue: {e}")
            
    except Exception as e:
        logger.warning(f"Could not clear Redis directly: {e}")
        logger.info("This is normal if Redis is not accessible or Celery uses a different broker")
    
    logger.info("Game cleanup completed!")


if __name__ == "__main__":
    try:
        cleanup_all_games()
        print("✅ Cleanup completed successfully!")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}", exc_info=True)
        print(f"❌ Error during cleanup: {e}")
        sys.exit(1)
