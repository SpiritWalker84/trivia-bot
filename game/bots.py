"""
Bot AI - intelligent bot behavior for trivia answers.
"""
from enum import Enum
from typing import Optional, Dict, List
from decimal import Decimal
import random
import config


class BotDifficulty(Enum):
    """Bot difficulty levels."""
    NOVICE = "novice"
    AMATEUR = "amateur"
    EXPERT = "expert"


class BotAI:
    """Bot AI for answering trivia questions."""
    
    def __init__(self, difficulty: BotDifficulty):
        """Initialize bot AI with difficulty level."""
        self.difficulty = difficulty
        self.config = config.config
        self._accuracy = self._get_accuracy_for_difficulty()
    
    def _get_accuracy_for_difficulty(self) -> float:
        """Get accuracy percentage for bot difficulty."""
        if self.difficulty == BotDifficulty.NOVICE:
            return self.config.BOT_NOVICE_ACCURACY
        elif self.difficulty == BotDifficulty.AMATEUR:
            return self.config.BOT_AMATEUR_ACCURACY
        else:  # EXPERT
            return self.config.BOT_EXPERT_ACCURACY
    
    @property
    def accuracy(self) -> float:
        """Get current accuracy value (for external access)."""
        return self._accuracy
    
    def generate_answer(
        self,
        question_id: int,
        correct_option: str,
        options: List[str]
    ) -> Dict[str, any]:
        """
        Generate bot's answer to a question.
        
        Args:
            question_id: Question ID
            correct_option: Correct option letter ('A', 'B', 'C', 'D')
            options: List of answer options
        
        Returns:
            Dict with 'selected_option' and 'delay_seconds'
        """
        # Random delay between min and max response time
        delay = random.randint(
            self.config.BOT_MIN_RESPONSE_DELAY,
            self.config.BOT_MAX_RESPONSE_DELAY
        )
        
        # Determine if bot answers correctly based on accuracy
        will_answer_correctly = random.random() < self._accuracy
        
        if will_answer_correctly:
            selected_option = correct_option
        else:
            # Choose random wrong option
            wrong_options = [opt for opt in ['A', 'B', 'C', 'D'] if opt != correct_option and opt in options]
            selected_option = random.choice(wrong_options) if wrong_options else correct_option
        
        return {
            'selected_option': selected_option,
            'is_correct': will_answer_correctly,
            'delay_seconds': delay
        }
    
    def should_answer_correctly(self) -> bool:
        """Check if bot should answer correctly based on accuracy."""
        return random.random() < self._accuracy
