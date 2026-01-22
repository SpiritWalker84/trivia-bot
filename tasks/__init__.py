"""
Celery tasks module for Trivia Bot.
Contains background tasks for pool management, voting, and game operations.
"""
from tasks.celery_app import celery_app
from tasks.pool_dispatcher import check_pool, start_game_from_pool, start_voting_from_pool
from tasks.vote_dispatcher import process_game_vote
from tasks.game_tasks import start_game_task, finish_round_task, finish_game_task, start_next_round_task
from tasks.question_sender import send_question_to_players, collect_answers
from tasks.bot_answers import process_bot_answers, send_next_question

__all__ = [
    "celery_app",
    "check_pool",
    "start_game_from_pool",
    "start_voting_from_pool",
    "process_game_vote",
    "start_game_task",
    "finish_round_task",
    "finish_game_task",
    "start_next_round_task",
    "send_question_to_players",
    "collect_answers",
    "process_bot_answers",
    "send_next_question",
]
