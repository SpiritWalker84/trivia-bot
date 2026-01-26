"""
Celery application configuration.
"""
from celery import Celery
import config


def create_celery_app() -> Celery:
    """Create and configure Celery application."""
    celery_app = Celery(
        "trivia_bot",
        broker=config.config.CELERY_BROKER_URL,
        backend=config.config.CELERY_RESULT_BACKEND,
        include=[
            "tasks.pool_dispatcher",
            "tasks.vote_dispatcher",
            "tasks.game_tasks",
            "tasks.question_sender",
            "tasks.bot_answers",
            "tasks.question_timer",
            "tasks.elimination_auto_leave",
        ]
    )
    
    # Celery configuration
    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_time_limit=30 * 60,  # 30 minutes
        task_soft_time_limit=25 * 60,  # 25 minutes
        worker_prefetch_multiplier=1,
        worker_max_tasks_per_child=50,
        broker_connection_retry_on_startup=True,  # Retry broker connection on startup
    )
    
    return celery_app


# Create global Celery app instance
celery_app = create_celery_app()
