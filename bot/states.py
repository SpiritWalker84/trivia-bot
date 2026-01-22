"""
Bot state management using FSM (Finite State Machine).
"""
from enum import Enum, auto


class GameState(Enum):
    """Game states for players."""
    MENU = auto()
    IN_POOL = auto()
    VOTING = auto()
    IN_GAME = auto()
    WAITING_RESULTS = auto()
    ELIMINATED = auto()
    WINNER = auto()


class AdminState(Enum):
    """Admin states."""
    MENU = auto()
    ADDING_QUESTION = auto()
    VIEWING_GAME = auto()


class PrivateGameState(Enum):
    """Private game creation states."""
    SELECTING_THEME = auto()
    SELECTING_PLAYERS_COUNT = auto()
    SELECTING_BOTS_COUNT = auto()
    WAITING_PLAYERS = auto()
