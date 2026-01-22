"""
Custom exception classes for Trivia Bot.
"""
from typing import Optional


class TriviaBotError(Exception):
    """Base exception for Trivia Bot."""
    
    def __init__(self, message: str, details: Optional[dict] = None):
        """
        Initialize error.
        
        Args:
            message: Error message
            details: Optional additional details
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}
    
    def __repr__(self):
        return f"{self.__class__.__name__}(message={self.message!r}, details={self.details})"


class GameError(TriviaBotError):
    """Exception raised for game-related errors."""
    pass


class DatabaseError(TriviaBotError):
    """Exception raised for database-related errors."""
    pass


class TelegramAPIError(TriviaBotError):
    """Exception raised for Telegram API errors."""
    pass


class ValidationError(TriviaBotError):
    """Exception raised for validation errors."""
    pass


class ConfigurationError(TriviaBotError):
    """Exception raised for configuration errors."""
    pass
