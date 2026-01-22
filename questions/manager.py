"""
Question manager - handles question selection and management.
"""
from typing import List, Optional
from database.session import db_session
from database.models import Question
from database.queries import QuestionQueries, ThemeQueries
import random
import config


class QuestionManager:
    """Manages question selection and retrieval."""
    
    def __init__(self):
        """Initialize question manager."""
        self.config = config.config
    
    def get_question_for_round(
        self,
        game_id: int,
        theme_id: Optional[int] = None,
        difficulty: Optional[str] = None,
        exclude_question_ids: Optional[List[int]] = None
    ) -> Optional[Question]:
        """
        Get a random unused question for a round.
        
        Args:
            game_id: Game ID
            theme_id: Optional theme ID (None = any theme)
            difficulty: Optional difficulty level
            exclude_question_ids: List of question IDs to exclude
        
        Returns:
            Question object or None if not found
        """
        with db_session() as session:
            # Get unused questions
            questions = QuestionQueries.get_unused_questions_for_game(
                session,
                game_id,
                theme_id=theme_id,
                difficulty=difficulty,
                limit=100  # Get more than needed for better randomization
            )
            
            # Filter out excluded questions
            if exclude_question_ids:
                questions = [q for q in questions if q.id not in exclude_question_ids]
            
            if not questions:
                return None
            
            # Random selection
            question = random.choice(questions)
            
            # Mark as used
            QuestionQueries.mark_question_as_used(session, game_id, question.id)
            session.commit()
            
            return question
    
    def get_random_theme(self) -> Optional[int]:
        """Get random theme ID."""
        with db_session() as session:
            themes = ThemeQueries.get_all_themes(session)
            if not themes:
                return None
            theme = random.choice(themes)
            return theme.id
    
    def get_questions_for_round(
        self,
        game_id: int,
        round_theme_id: Optional[int] = None,
        count: int = None
    ) -> List[Question]:
        """
        Get multiple questions for a round.
        
        Args:
            game_id: Game ID
            round_theme_id: Optional theme ID for round
            count: Number of questions to get
        
        Returns:
            List of Question objects
        """
        if count is None:
            count = self.config.QUESTIONS_PER_ROUND
        
        questions = []
        exclude_ids = []
        
        for _ in range(count):
            question = self.get_question_for_round(
                game_id,
                theme_id=round_theme_id,
                exclude_question_ids=exclude_ids
            )
            if question:
                questions.append(question)
                exclude_ids.append(question.id)
            else:
                # Not enough questions available
                break
        
        return questions
