"""
Database module for Trivia Bot.
Contains models, database session management, and queries.
"""
from database.session import get_db_session, DatabaseSession
from database.models import (
    User,
    Theme,
    Question,
    Game,
    GamePlayer,
    Round,
    RoundQuestion,
    Answer,
    Pool,
    PoolPlayer,
    GameVote,
    GameUsedQuestion,
    UserQuestionsHistory
)

__all__ = [
    "get_db_session",
    "DatabaseSession",
    "User",
    "Theme",
    "Question",
    "Game",
    "GamePlayer",
    "Round",
    "RoundQuestion",
    "Answer",
    "Pool",
    "PoolPlayer",
    "GameVote",
    "GameUsedQuestion",
    "UserQuestionsHistory",
]
