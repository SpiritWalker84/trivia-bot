"""
Rating system - calculates rating changes based on game results.
"""
from typing import Dict, List
from database.models import Game, GamePlayer
import config


class RatingSystem:
    """Rating calculation system."""
    
    def __init__(self):
        """Initialize rating system."""
        self.config = config.config
    
    def calculate_rating_delta(
        self,
        place: int,
        total_players: int,
        is_training: bool = False
    ) -> int:
        """
        Calculate rating delta based on final place.
        
        Args:
            place: Final place (1 = winner)
            total_players: Total number of players in game
            is_training: Whether this is a training game
        
        Returns:
            Rating change (can be negative)
        """
        # Training games don't affect rating
        if is_training:
            return 0
        
        # Apply rating rules based on place
        if place == 1:
            return self.config.RATING_WINNER_BONUS
        elif place == 2:
            return self.config.RATING_SECOND_BONUS
        elif place == 3:
            return self.config.RATING_THIRD_BONUS
        elif place in (4, 5):
            return self.config.RATING_4_5_BONUS
        elif place in (6, 7, 8):
            return self.config.RATING_6_8_BONUS
        else:
            return self.config.RATING_9_10_PENALTY
    
    def update_ratings_after_game(
        self,
        game_players: List[GamePlayer],
        is_training: bool = False
    ) -> Dict[int, int]:
        """
        Calculate rating changes for all players in a finished game.
        
        Args:
            game_players: List of GamePlayer objects with final_place set
            is_training: Whether this is a training game
        
        Returns:
            Dict mapping user_id to rating_delta
        """
        total_players = len([gp for gp in game_players if not gp.is_bot])
        rating_changes = {}
        
        for game_player in game_players:
            # Only update rating for real players, not bots
            if game_player.is_bot:
                continue
            
            if game_player.final_place is None:
                continue
            
            delta = self.calculate_rating_delta(
                game_player.final_place,
                total_players,
                is_training
            )
            
            rating_changes[game_player.user_id] = delta
        
        return rating_changes
