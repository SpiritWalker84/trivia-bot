"""
Database query helpers - common database operations.
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc, asc, select
import config
from database.models import (
    User,
    Game,
    GamePlayer,
    Pool,
    PoolPlayer,
    Question,
    Theme,
    Round,
    RoundQuestion,
    Answer,
    GameVote,
    GameUsedQuestion,
)


class UserQueries:
    """User-related database queries."""
    
    @staticmethod
    def get_or_create_user(
        session: Session,
        telegram_id: int,
        username: Optional[str] = None,
        full_name: Optional[str] = None
    ) -> User:
        """Get or create user by telegram_id."""
        user = session.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            user = User(
                telegram_id=telegram_id,
                username=username,
                full_name=full_name,
                is_bot=False
            )
            session.add(user)
            session.flush()
        else:
            # Update username and full_name if changed
            if username:
                user.username = username
            if full_name:
                user.full_name = full_name
            session.flush()
        return user
    
    @staticmethod
    def get_user_by_telegram_id(session: Session, telegram_id: int) -> Optional[User]:
        """Get user by telegram_id."""
        return session.query(User).filter(User.telegram_id == telegram_id).first()
    
    @staticmethod
    def get_bots(session: Session, difficulty: Optional[str] = None, limit: int = 10) -> List[User]:
        """Get bots, optionally filtered by difficulty."""
        query = session.query(User).filter(User.is_bot == True)
        if difficulty:
            query = query.filter(User.bot_difficulty == difficulty)
        return query.limit(limit).all()
    
    @staticmethod
    def get_rating_top(session: Session, limit: int = 100) -> List[User]:
        """Get top users by rating."""
        return (
            session.query(User)
            .filter(User.is_bot == False)
            .order_by(desc(User.rating))
            .limit(limit)
            .all()
        )


class GameQueries:
    """Game-related database queries."""
    
    @staticmethod
    def get_active_games_count(session: Session) -> int:
        """Get count of active games."""
        return (
            session.query(func.count(Game.id))
            .filter(Game.status.in_(['pre_start', 'in_progress']))
            .scalar()
        )
    
    @staticmethod
    def get_game_by_id(session: Session, game_id: int) -> Optional[Game]:
        """Get game by ID."""
        return session.query(Game).filter(Game.id == game_id).first()
    
    @staticmethod
    def create_game(
        session: Session,
        game_type: str,
        creator_id: Optional[int] = None,
        theme_id: Optional[int] = None,
        total_rounds: int = config.config.ROUNDS_PER_GAME
    ) -> Game:
        """Create a new game."""
        game = Game(
            game_type=game_type,
            creator_id=creator_id,
            theme_id=theme_id,
            status='waiting',
            total_rounds=total_rounds
        )
        session.add(game)
        session.flush()
        return game
    
    @staticmethod
    def get_game_players(session: Session, game_id: int, alive_only: bool = False) -> List[GamePlayer]:
        """Get game players, optionally only alive ones."""
        query = session.query(GamePlayer).filter(GamePlayer.game_id == game_id)
        if alive_only:
            query = query.filter(GamePlayer.is_eliminated == False)
        return query.order_by(asc(GamePlayer.join_order)).all()


class PoolQueries:
    """Pool-related database queries."""
    
    @staticmethod
    def get_or_create_active_pool(session: Session, pool_type: str = 'quick_public') -> Pool:
        """Get or create active pool."""
        pool = (
            session.query(Pool)
            .filter(
                and_(
                    Pool.pool_type == pool_type,
                    Pool.status == 'waiting'
                )
            )
            .order_by(asc(Pool.created_at))
            .first()
        )
        if not pool:
            pool = Pool(pool_type=pool_type, status='waiting')
            session.add(pool)
            session.flush()
        return pool
    
    @staticmethod
    def get_pool_players(session: Session, pool_id: int) -> List[PoolPlayer]:
        """Get pool players ordered by join time."""
        return (
            session.query(PoolPlayer)
            .filter(PoolPlayer.pool_id == pool_id)
            .order_by(asc(PoolPlayer.joined_at))
            .all()
        )
    
    @staticmethod
    def add_player_to_pool(session: Session, pool_id: int, user_id: int) -> PoolPlayer:
        """Add player to pool."""
        pool_player = PoolPlayer(pool_id=pool_id, user_id=user_id)
        session.add(pool_player)
        session.flush()
        return pool_player


class QuestionQueries:
    """Question-related database queries."""
    
    @staticmethod
    def get_unused_questions_for_game(
        session: Session,
        game_id: int,
        theme_id: Optional[int] = None,
        difficulty: Optional[str] = None,
        limit: int = 10
    ) -> List[Question]:
        """Get questions not yet used in the game."""
        # Get used question IDs - use select() explicitly to avoid warning
        used_ids_subquery = (
            select(GameUsedQuestion.question_id)
            .where(GameUsedQuestion.game_id == game_id)
            .subquery()
        )
        
        # Additional safety: exclude questions already present in any round for this game
        existing_round_ids_subquery = (
            select(RoundQuestion.question_id)
            .select_from(RoundQuestion)
            .join(Round, Round.id == RoundQuestion.round_id)
            .where(Round.game_id == game_id)
            .subquery()
        )
        
        query = session.query(Question).filter(
            and_(
                Question.id.notin_(select(used_ids_subquery.c.question_id)),
                Question.id.notin_(select(existing_round_ids_subquery.c.question_id)),
                Question.is_approved == True
            )
        )
        
        if theme_id:
            query = query.filter(Question.theme_id == theme_id)
        
        if difficulty:
            query = query.filter(Question.difficulty == difficulty)
        
        # Random order
        return query.order_by(func.random()).limit(limit).all()
    
    @staticmethod
    def mark_question_as_used(session: Session, game_id: int, question_id: int):
        """Mark question as used in game."""
        used = GameUsedQuestion(game_id=game_id, question_id=question_id)
        session.merge(used)
        session.flush()


class ThemeQueries:
    """Theme-related database queries."""
    
    @staticmethod
    def get_all_themes(session: Session) -> List[Theme]:
        """Get all themes."""
        return session.query(Theme).all()
    
    @staticmethod
    def get_theme_by_code(session: Session, code: str) -> Optional[Theme]:
        """Get theme by code."""
        return session.query(Theme).filter(Theme.code == code).first()


class RoundQueries:
    """Round-related database queries."""
    
    @staticmethod
    def create_round(
        session: Session,
        game_id: int,
        round_number: int,
        theme_id: Optional[int] = None,
        is_tie_break: bool = False,
        parent_round_id: Optional[int] = None
    ) -> Round:
        """Create a new round."""
        from utils.logging import get_logger
        logger = get_logger(__name__)
        
        try:
            round_obj = Round(
                game_id=game_id,
                round_number=round_number,
                theme_id=theme_id,
                status='not_started',
                is_tie_break=is_tie_break,
                parent_round_id=parent_round_id
            )
            session.add(round_obj)
            session.flush()
            logger.info(f"Round created successfully: game_id={game_id}, round_number={round_number}, round_id={round_obj.id}")
            return round_obj
        except Exception as e:
            logger.error(f"Error creating round for game {game_id}, round {round_number}: {e}", exc_info=True)
            raise
    
    @staticmethod
    def get_round_by_number(session: Session, game_id: int, round_number: int) -> Optional[Round]:
        """Get round by game and round number."""
        return (
            session.query(Round)
            .filter(
                and_(
                    Round.game_id == game_id,
                    Round.round_number == round_number
                )
            )
            .first()
        )
