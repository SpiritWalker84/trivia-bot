"""
Retry decorators with exponential backoff.
"""
import time
import logging
from functools import wraps
from typing import Callable, TypeVar, Any
import config

logger = logging.getLogger(__name__)

T = TypeVar('T')


def retry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for retrying function calls with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        exceptions: Tuple of exceptions to catch and retry
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            delay = base_delay
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_attempts:
                        logger.error(
                            f"Function {func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise
                    
                    logger.warning(
                        f"Function {func.__name__} failed (attempt {attempt}/{max_attempts}): {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    time.sleep(min(delay, max_delay))
                    delay *= exponential_base
            
            # Should not reach here, but just in case
            if last_exception:
                raise last_exception
            
            raise RuntimeError(f"Function {func.__name__} failed unexpectedly")
        
        return wrapper
    return decorator


def telegram_retry(func: Callable[..., T]) -> Callable[..., T]:
    """
    Retry decorator specifically for Telegram API calls.
    Uses configuration from config.py.
    """
    from telegram.error import TelegramError, TimedOut, NetworkError, RetryAfter
    
    return retry_with_backoff(
        max_attempts=config.config.TELEGRAM_RETRY_ATTEMPTS,
        base_delay=config.config.TELEGRAM_RETRY_BACKOFF_BASE,
        exceptions=(TelegramError, TimedOut, NetworkError, RetryAfter, ConnectionError)
    )(func)


def database_retry(func: Callable[..., T]) -> Callable[..., T]:
    """
    Retry decorator specifically for database operations.
    Uses configuration from config.py.
    """
    from sqlalchemy.exc import SQLAlchemyError, OperationalError, DisconnectionError
    
    return retry_with_backoff(
        max_attempts=config.config.DATABASE_RETRY_ATTEMPTS,
        base_delay=config.config.DATABASE_RETRY_DELAY,
        exceptions=(SQLAlchemyError, OperationalError, DisconnectionError, ConnectionError)
    )(func)
