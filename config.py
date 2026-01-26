"""
Configuration module for Trivia Bot.
Loads settings from environment variables.
"""
import os
from typing import List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration class."""
    
    # Telegram Bot Configuration
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_ADMIN_IDS: List[int] = [
        int(admin_id.strip())
        for admin_id in os.getenv("TELEGRAM_ADMIN_IDS", "").split(",")
        if admin_id.strip().isdigit()
    ]
    
    # Database Configuration
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://user:password@localhost:5432/trivia_bot"
    )
    DATABASE_POOL_SIZE: int = int(os.getenv("DATABASE_POOL_SIZE", "10"))
    DATABASE_MAX_OVERFLOW: int = int(os.getenv("DATABASE_MAX_OVERFLOW", "20"))
    
    # Redis Configuration
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_CACHE_TTL: int = int(os.getenv("REDIS_CACHE_TTL", "300"))
    
    # Celery Configuration
    CELERY_BROKER_URL: str = os.getenv(
        "CELERY_BROKER_URL",
        "redis://localhost:6379/1"
    )
    CELERY_RESULT_BACKEND: str = os.getenv(
        "CELERY_RESULT_BACKEND",
        "redis://localhost:6379/2"
    )
    
    # Application Settings
    MAX_ACTIVE_GAMES: int = int(os.getenv("MAX_ACTIVE_GAMES", "500"))
    MAX_QUESTIONS_IN_DB: int = int(os.getenv("MAX_QUESTIONS_IN_DB", "50000"))
    POOL_CHECK_INTERVAL: int = int(os.getenv("POOL_CHECK_INTERVAL", "300"))  # 5 minutes
    VOTE_DURATION: int = int(os.getenv("VOTE_DURATION", "45"))  # seconds
    QUESTION_TIME_LIMIT: int = int(os.getenv("QUESTION_TIME_LIMIT", "10"))  # seconds
    TIE_BREAK_TIME_LIMIT: int = int(os.getenv("TIE_BREAK_TIME_LIMIT", "20"))  # seconds
    PAUSE_BETWEEN_ROUNDS_SEC: int = int(os.getenv("PAUSE_BETWEEN_ROUNDS_SEC", "60"))  # seconds
    
    # Game Settings
    ROUNDS_PER_GAME: int = int(os.getenv("ROUNDS_PER_GAME", "9"))
    QUESTIONS_PER_ROUND: int = int(os.getenv("QUESTIONS_PER_ROUND", "10"))
    PLAYERS_PER_GAME: int = int(os.getenv("PLAYERS_PER_GAME", "10"))
    MIN_PLAYERS_FOR_QUICK_START: int = int(os.getenv("MIN_PLAYERS_FOR_QUICK_START", "10"))
    MIN_PLAYERS_FOR_VOTE: int = int(os.getenv("MIN_PLAYERS_FOR_VOTE", "3"))
    
    # Bot Settings
    BOT_MIN_RESPONSE_DELAY: int = int(os.getenv("BOT_MIN_RESPONSE_DELAY", "3"))
    BOT_MAX_RESPONSE_DELAY: int = int(os.getenv("BOT_MAX_RESPONSE_DELAY", "15"))
    # Bot accuracy: probability of answering correctly (0.0 to 1.0)
    # NOVICE: 55% - новички отвечают правильно 4-6 из 10 вопросов
    # AMATEUR: 68% - любители отвечают правильно 6-8 из 10 вопросов
    # EXPERT: 80% - эксперты отвечают правильно 7-9 из 10 вопросов
    BOT_NOVICE_ACCURACY: float = float(os.getenv("BOT_NOVICE_ACCURACY", "0.55"))
    BOT_AMATEUR_ACCURACY: float = float(os.getenv("BOT_AMATEUR_ACCURACY", "0.68"))
    BOT_EXPERT_ACCURACY: float = float(os.getenv("BOT_EXPERT_ACCURACY", "0.80"))
    
    # Rating System
    RATING_WINNER_BONUS: int = int(os.getenv("RATING_WINNER_BONUS", "20"))
    RATING_SECOND_BONUS: int = int(os.getenv("RATING_SECOND_BONUS", "12"))
    RATING_THIRD_BONUS: int = int(os.getenv("RATING_THIRD_BONUS", "8"))
    RATING_4_5_BONUS: int = int(os.getenv("RATING_4_5_BONUS", "4"))
    RATING_6_8_BONUS: int = int(os.getenv("RATING_6_8_BONUS", "0"))
    RATING_9_10_PENALTY: int = int(os.getenv("RATING_9_10_PENALTY", "-4"))
    
    # Retry Settings
    TELEGRAM_RETRY_ATTEMPTS: int = int(os.getenv("TELEGRAM_RETRY_ATTEMPTS", "5"))
    TELEGRAM_RETRY_BACKOFF_BASE: float = float(os.getenv("TELEGRAM_RETRY_BACKOFF_BASE", "1.0"))
    DATABASE_RETRY_ATTEMPTS: int = int(os.getenv("DATABASE_RETRY_ATTEMPTS", "3"))
    DATABASE_RETRY_DELAY: float = float(os.getenv("DATABASE_RETRY_DELAY", "1.0"))
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "logs/trivia_bot.log")
    LOG_FORMAT: str = os.getenv(
        "LOG_FORMAT",
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = ENVIRONMENT.lower() == "development"
    
    # Cache TTLs (in seconds)
    CACHE_USER_PROFILE_TTL: int = int(os.getenv("CACHE_USER_PROFILE_TTL", "600"))
    CACHE_RATING_TOP100_TTL: int = int(os.getenv("CACHE_RATING_TOP100_TTL", "600"))
    CACHE_THEMES_TTL: int = int(os.getenv("CACHE_THEMES_TTL", "86400"))
    CACHE_BOT_SETTINGS_TTL: int = int(os.getenv("CACHE_BOT_SETTINGS_TTL", "86400"))
    
    @classmethod
    def validate(cls) -> bool:
        """Validate critical configuration values."""
        if not cls.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        if not cls.DATABASE_URL:
            raise ValueError("DATABASE_URL is required")
        return True


# Create global config instance
config = Config()
