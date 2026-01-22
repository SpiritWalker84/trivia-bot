"""
Database session management.
"""
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
import config


class DatabaseSession:
    """Database session manager class."""
    
    def __init__(self, database_url: str):
        """Initialize database engine and session factory."""
        self.engine = create_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=config.config.DATABASE_POOL_SIZE,
            max_overflow=config.config.DATABASE_MAX_OVERFLOW,
            pool_pre_ping=True,  # Verify connections before using
            echo=config.config.DEBUG,  # Log SQL queries in debug mode
        )
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Get database session context manager."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def create_tables(self):
        """Create all database tables."""
        from database.models import Base
        # Create tables from all models
        Base.metadata.create_all(bind=self.engine)
    
    def drop_tables(self):
        """Drop all database tables."""
        from database.models import Base
        # Drop tables from all models
        Base.metadata.drop_all(bind=self.engine)


# Global database session instance
_db_session: DatabaseSession | None = None


def get_db_session() -> DatabaseSession:
    """Get or create global database session instance."""
    global _db_session
    if _db_session is None:
        config.config.validate()
        _db_session = DatabaseSession(config.config.DATABASE_URL)
    return _db_session


@contextmanager
def db_session() -> Generator[Session, None, None]:
    """Context manager for database session."""
    db = get_db_session()
    with db.get_session() as session:
        yield session
