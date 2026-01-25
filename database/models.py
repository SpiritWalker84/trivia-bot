"""
SQLAlchemy models for Trivia Bot database.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Integer,
    String,
    Text,
    Numeric,
    DateTime,
    ForeignKey,
    CHAR,
    CheckConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import ARRAY
import pytz


from sqlalchemy.ext.declarative import declarative_base

# Create base class first
Base = declarative_base()


class TimestampMixin:
    """Mixin for timestamp fields."""
    
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(pytz.UTC),
        server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(pytz.UTC),
        onupdate=lambda: datetime.now(pytz.UTC),
        server_default=func.now()
    )


class User(Base, TimestampMixin):
    """User model - stores both real users and bots."""
    __tablename__ = "users"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=True)  # NULL for bots
    username = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)
    is_bot = Column(Boolean, nullable=False, default=False)
    bot_difficulty = Column(String(20), nullable=True)  # 'novice', 'amateur', 'expert'
    rating = Column(Integer, nullable=False, default=0)
    games_played = Column(Integer, nullable=False, default=0)
    games_won = Column(Integer, nullable=False, default=0)
    is_premium = Column(Boolean, nullable=False, default=False)
    
    # Relationships
    created_games = relationship("Game", back_populates="creator", foreign_keys="Game.creator_id")
    game_players = relationship("GamePlayer", back_populates="user")
    answers = relationship("Answer", back_populates="user")
    pool_players = relationship("PoolPlayer", back_populates="user")
    game_votes = relationship("GameVote", back_populates="user")
    
    __table_args__ = (
        Index("idx_users_telegram_id", "telegram_id"),
        Index("idx_users_is_bot", "is_bot"),
        Index("idx_users_rating", "rating"),
    )
    
    def __repr__(self):
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username={self.username}, is_bot={self.is_bot})>"


class Theme(Base):
    """Theme model - question categories."""
    __tablename__ = "themes"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    code = Column(String(50), unique=True, nullable=False)  # 'movies', 'science'
    name = Column(String(100), nullable=False)  # "Кино"
    description = Column(Text, nullable=True)
    
    # Relationships
    questions = relationship("Question", back_populates="theme")
    games = relationship("Game", back_populates="theme")
    rounds = relationship("Round", back_populates="theme")
    
    def __repr__(self):
        return f"<Theme(id={self.id}, code={self.code}, name={self.name})>"


class Question(Base, TimestampMixin):
    """Question model - trivia questions."""
    __tablename__ = "questions"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    theme_id = Column(BigInteger, ForeignKey("themes.id", ondelete="RESTRICT"), nullable=False)
    question_text = Column(Text, nullable=False)
    option_a = Column(Text, nullable=False)
    option_b = Column(Text, nullable=False)
    option_c = Column(Text, nullable=True)
    option_d = Column(Text, nullable=True)
    correct_option = Column(CHAR(1), nullable=False)  # 'A', 'B', 'C', 'D'
    difficulty = Column(String(20), nullable=True)  # 'easy', 'medium', 'hard'
    source_type = Column(String(20), nullable=False)  # 'parsed', 'ai', 'user'
    created_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    is_approved = Column(Boolean, nullable=False, default=True)
    
    # Relationships
    theme = relationship("Theme", back_populates="questions")
    creator = relationship("User", foreign_keys=[created_by])
    round_questions = relationship("RoundQuestion", back_populates="question")
    game_used = relationship("GameUsedQuestion", back_populates="question")
    user_history = relationship("UserQuestionsHistory", back_populates="question")
    
    __table_args__ = (
        CheckConstraint("correct_option IN ('A', 'B', 'C', 'D')", name="check_correct_option"),
        Index("idx_questions_theme", "theme_id"),
        Index("idx_questions_theme_diff", "theme_id", "difficulty"),
        Index("idx_questions_source", "source_type"),
        Index("idx_questions_approved", "is_approved"),
    )
    
    def __repr__(self):
        return f"<Question(id={self.id}, theme_id={self.theme_id}, text={self.question_text[:50]}...)>"


class Game(Base, TimestampMixin):
    """Game model - game session."""
    __tablename__ = "games"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    game_type = Column(String(20), nullable=False)  # 'quick', 'training', 'private'
    creator_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    theme_id = Column(BigInteger, ForeignKey("themes.id"), nullable=True)  # NULL = mixed
    status = Column(String(20), nullable=False)  # 'waiting', 'pre_start', 'in_progress', 'finished', 'cancelled', 'error_pause'
    total_rounds = Column(Integer, nullable=False, default=10)
    is_final_stage = Column(Boolean, nullable=False, default=False)
    current_round = Column(Integer, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    last_error_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    creator = relationship("User", back_populates="created_games", foreign_keys=[creator_id])
    theme = relationship("Theme", back_populates="games")
    players = relationship("GamePlayer", back_populates="game", cascade="all, delete-orphan")
    rounds = relationship("Round", back_populates="game", cascade="all, delete-orphan")
    votes = relationship("GameVote", back_populates="game", cascade="all, delete-orphan")
    used_questions = relationship("GameUsedQuestion", back_populates="game", cascade="all, delete-orphan")
    
    __table_args__ = (
        CheckConstraint("game_type IN ('quick', 'training', 'private')", name="check_game_type"),
        CheckConstraint(
            "status IN ('waiting', 'pre_start', 'in_progress', 'finished', 'cancelled', 'error_pause')",
            name="check_game_status"
        ),
        Index("idx_games_type_status", "game_type", "status"),
        Index("idx_games_status", "status"),
        Index("idx_games_creator", "creator_id"),
    )
    
    def __repr__(self):
        return f"<Game(id={self.id}, type={self.game_type}, status={self.status})>"


class GamePlayer(Base, TimestampMixin):
    """Game player model - participants in a game."""
    __tablename__ = "game_players"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    game_id = Column(BigInteger, ForeignKey("games.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    is_bot = Column(Boolean, nullable=False, default=False)
    bot_difficulty = Column(String(20), nullable=True)
    join_order = Column(Integer, nullable=False)
    total_score = Column(Integer, nullable=False, default=0)
    total_time = Column(Numeric(10, 3), nullable=False, default=0)
    is_eliminated = Column(Boolean, nullable=False, default=False)
    eliminated_round = Column(Integer, nullable=True)
    final_place = Column(Integer, nullable=True)
    is_spectator = Column(Boolean, nullable=True, default=None)  # None = not eliminated, True = spectator, False = left game
    left_game = Column(Boolean, nullable=False, default=False)  # True if player chose to leave
    
    # Relationships
    game = relationship("Game", back_populates="players")
    user = relationship("User", back_populates="game_players")
    answers = relationship("Answer", back_populates="game_player")
    
    __table_args__ = (
        Index("idx_game_players_unique", "game_id", "user_id", unique=True),
        Index("idx_game_players_game", "game_id"),
        Index("idx_game_players_user", "user_id"),
        Index("idx_game_players_active", "game_id", "is_eliminated"),
    )
    
    def __repr__(self):
        return f"<GamePlayer(game_id={self.game_id}, user_id={self.user_id}, score={self.total_score})>"


class Round(Base):
    """Round model - round within a game."""
    __tablename__ = "rounds"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    game_id = Column(BigInteger, ForeignKey("games.id", ondelete="CASCADE"), nullable=False)
    round_number = Column(Integer, nullable=False)
    theme_id = Column(BigInteger, ForeignKey("themes.id"), nullable=True)
    status = Column(String(20), nullable=False)  # 'not_started', 'in_progress', 'finished'
    is_tie_break = Column(Boolean, nullable=False, default=False)
    parent_round_id = Column(BigInteger, ForeignKey("rounds.id"), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    game = relationship("Game", back_populates="rounds")
    theme = relationship("Theme", back_populates="rounds")
    parent_round = relationship("Round", remote_side=[id], foreign_keys=[parent_round_id])
    tie_break_rounds = relationship("Round", foreign_keys=[parent_round_id], overlaps="parent_round")
    questions = relationship("RoundQuestion", back_populates="round", cascade="all, delete-orphan")
    answers = relationship("Answer", back_populates="round")
    
    __table_args__ = (
        CheckConstraint(
            "status IN ('not_started', 'in_progress', 'finished')",
            name="check_round_status"
        ),
        Index("idx_rounds_game_round", "game_id", "round_number", unique=True),
        Index("idx_rounds_game", "game_id"),
        Index("idx_rounds_status", "status"),
    )
    
    def __repr__(self):
        return f"<Round(id={self.id}, game_id={self.game_id}, round_number={self.round_number}, status={self.status})>"


class RoundQuestion(Base):
    """Round question model - question within a round."""
    __tablename__ = "round_questions"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    round_id = Column(BigInteger, ForeignKey("rounds.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(BigInteger, ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False)
    question_number = Column(Integer, nullable=False)
    displayed_at = Column(DateTime(timezone=True), nullable=True)
    time_limit_sec = Column(Integer, nullable=False, default=20)
    
    # Relationships
    round = relationship("Round", back_populates="questions")
    question = relationship("Question", back_populates="round_questions")
    answers = relationship("Answer", back_populates="round_question")
    
    __table_args__ = (
        Index("idx_round_questions_unique", "round_id", "question_number", unique=True),
        Index("idx_round_questions_round", "round_id"),
    )
    
    def __repr__(self):
        return f"<RoundQuestion(id={self.id}, round_id={self.round_id}, question_number={self.question_number})>"


class Answer(Base):
    """Answer model - player's answer to a question."""
    __tablename__ = "answers"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    game_id = Column(BigInteger, ForeignKey("games.id", ondelete="CASCADE"), nullable=False)
    round_id = Column(BigInteger, ForeignKey("rounds.id", ondelete="CASCADE"), nullable=False)
    round_question_id = Column(BigInteger, ForeignKey("round_questions.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    game_player_id = Column(BigInteger, ForeignKey("game_players.id"), nullable=True)
    selected_option = Column(CHAR(1), nullable=True)  # 'A', 'B', 'C', 'D', NULL if not answered
    is_correct = Column(Boolean, nullable=True)
    answer_time = Column(Numeric(10, 3), nullable=True)  # seconds from displayed_at
    answered_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    game = relationship("Game")
    round = relationship("Round", back_populates="answers")
    round_question = relationship("RoundQuestion", back_populates="answers")
    user = relationship("User", back_populates="answers")
    game_player = relationship("GamePlayer", back_populates="answers")
    
    __table_args__ = (
        Index("idx_answers_unique", "round_question_id", "user_id", unique=True),
        Index("idx_answers_game_round_user", "game_id", "round_id", "user_id"),
        Index("idx_answers_time", "round_question_id", "answer_time"),
    )
    
    def __repr__(self):
        return f"<Answer(id={self.id}, user_id={self.user_id}, option={self.selected_option}, correct={self.is_correct})>"


class Pool(Base, TimestampMixin):
    """Pool model - queue for quick games."""
    __tablename__ = "pools"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    pool_type = Column(String(20), nullable=False)  # 'quick_public', etc.
    status = Column(String(20), nullable=False)  # 'waiting', 'forming_game', 'closed'
    last_check_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    players = relationship("PoolPlayer", back_populates="pool", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_pools_status", "status"),
        Index("idx_pools_type_status", "pool_type", "status"),
    )
    
    def __repr__(self):
        return f"<Pool(id={self.id}, type={self.pool_type}, status={self.status})>"


class PoolPlayer(Base):
    """Pool player model - player in a pool."""
    __tablename__ = "pool_players"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    pool_id = Column(BigInteger, ForeignKey("pools.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    joined_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    
    # Relationships
    pool = relationship("Pool", back_populates="players")
    user = relationship("User", back_populates="pool_players")
    
    __table_args__ = (
        Index("idx_pool_players_unique", "pool_id", "user_id", unique=True),
        Index("idx_pool_players_pool", "pool_id"),
    )
    
    def __repr__(self):
        return f"<PoolPlayer(pool_id={self.pool_id}, user_id={self.user_id})>"


class GameVote(Base, TimestampMixin):
    """Game vote model - voting for game start."""
    __tablename__ = "game_votes"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    game_id = Column(BigInteger, ForeignKey("games.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    vote = Column(String(20), nullable=False)  # 'start_now', 'wait_more'
    
    # Relationships
    game = relationship("Game", back_populates="votes")
    user = relationship("User", back_populates="game_votes")
    
    __table_args__ = (
        Index("idx_game_votes_unique", "game_id", "user_id", unique=True),
        Index("idx_game_votes_game", "game_id"),
    )
    
    def __repr__(self):
        return f"<GameVote(game_id={self.game_id}, user_id={self.user_id}, vote={self.vote})>"


class GameUsedQuestion(Base):
    """Game used question model - tracks questions used in a game."""
    __tablename__ = "game_used_questions"
    
    game_id = Column(BigInteger, ForeignKey("games.id", ondelete="CASCADE"), nullable=False, primary_key=True)
    question_id = Column(BigInteger, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, primary_key=True)
    
    # Relationships
    game = relationship("Game", back_populates="used_questions")
    question = relationship("Question", back_populates="game_used")
    
    def __repr__(self):
        return f"<GameUsedQuestion(game_id={self.game_id}, question_id={self.question_id})>"


class UserQuestionsHistory(Base):
    """User questions history - tracks questions shown to users."""
    __tablename__ = "user_questions_history"
    
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, primary_key=True)
    question_id = Column(BigInteger, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, primary_key=True)
    last_used_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    
    # Relationships
    user = relationship("User")
    question = relationship("Question", back_populates="user_history")
    
    def __repr__(self):
        return f"<UserQuestionsHistory(user_id={self.user_id}, question_id={self.question_id})>"
