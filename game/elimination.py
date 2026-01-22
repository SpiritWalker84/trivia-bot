"""
Elimination logic - determines which player is eliminated after each round.
Includes tie-break mechanics.
"""
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from decimal import Decimal
import config


@dataclass
class PlayerRoundResult:
    """Player's result for a single round."""
    user_id: int
    correct_answers: int
    total_time: Decimal
    answers: List[Dict]  # List of answer dicts with 'is_correct' and 'answer_time'
    
    def __repr__(self):
        return f"<PlayerRoundResult(user_id={self.user_id}, correct={self.correct_answers}, time={self.total_time})>"


class EliminationLogic:
    """Logic for determining eliminated players."""
    
    def __init__(self):
        """Initialize elimination logic."""
        self.config = config.config
    
    def determine_eliminated_player(
        self,
        round_results: List[PlayerRoundResult]
    ) -> Tuple[Optional[int], bool]:
        """
        Determine which player should be eliminated.
        
        Returns:
            Tuple[eliminated_user_id, needs_tie_break]
        """
        if not round_results:
            return None, False
        
        # Step 1: Find candidates for elimination
        # Candidates = players with minimum correct answers
        min_correct = min(r.correct_answers for r in round_results)
        candidates_by_score = [
            r for r in round_results
            if r.correct_answers == min_correct
        ]
        
        if len(candidates_by_score) == 1:
            # Only one candidate - eliminate immediately
            return candidates_by_score[0].user_id, False
        
        # Step 2: Among candidates, find those with maximum total time
        max_time = max(r.total_time for r in candidates_by_score)
        candidates = [
            r for r in candidates_by_score
            if r.total_time == max_time
        ]
        
        if len(candidates) == 1:
            # Only one candidate with max time - eliminate immediately
            return candidates[0].user_id, False
        
        # Step 3: Check for complete equality (same score AND same time)
        # This requires tie-break
        if self._all_have_same_score_and_time(candidates):
            return None, True
        
        # Step 4: If not complete equality, eliminate slowest
        # Should not happen if logic is correct, but fallback
        eliminated = max(candidates, key=lambda r: r.total_time)
        return eliminated.user_id, False
    
    def _all_have_same_score_and_time(
        self,
        candidates: List[PlayerRoundResult]
    ) -> bool:
        """Check if all candidates have exactly same score and time."""
        if len(candidates) <= 1:
            return False
        
        first = candidates[0]
        return all(
            r.correct_answers == first.correct_answers
            and r.total_time == first.total_time
            for r in candidates
        )
    
    def determine_tie_break_eliminated(
        self,
        tie_break_results: List[Dict]
    ) -> int:
        """
        Determine eliminated player in tie-break.
        
        Args:
            tie_break_results: List of dicts with keys:
                - user_id: int
                - is_correct: bool
                - answer_time: Decimal (or None if not answered)
                - time_limit: int
        
        Returns:
            eliminated_user_id
        """
        if not tie_break_results:
            raise ValueError("Tie-break results cannot be empty")
        
        time_limit = tie_break_results[0].get('time_limit', config.config.TIE_BREAK_TIME_LIMIT)
        
        # Separate into correct and wrong
        correct_players = []
        wrong_players = []
        
        for result in tie_break_results:
            user_id = result['user_id']
            is_correct = result.get('is_correct', False)
            answer_time = result.get('answer_time')
            
            # If not answered, treat as wrong with max time
            if answer_time is None:
                answer_time = Decimal(time_limit)
                is_correct = False
            
            if is_correct:
                correct_players.append({
                    'user_id': user_id,
                    'answer_time': Decimal(str(answer_time))
                })
            else:
                wrong_players.append({
                    'user_id': user_id,
                    'answer_time': Decimal(str(answer_time))
                })
        
        # Case A: No one answered correctly
        if not correct_players:
            # Eliminate player with maximum answer_time
            eliminated = max(tie_break_results, key=lambda r: r.get('answer_time', time_limit))
            return eliminated['user_id']
        
        # Case B: Exactly one answered correctly
        if len(correct_players) == 1:
            # That player stays, eliminate slowest among wrong
            if wrong_players:
                eliminated = max(wrong_players, key=lambda r: r['answer_time'])
                return eliminated['user_id']
            # Should not happen, but fallback
            eliminated = max(tie_break_results, key=lambda r: r.get('answer_time', time_limit))
            return eliminated['user_id']
        
        # Case C: Two or more answered correctly
        # Compare only those who answered correctly
        eliminated = max(correct_players, key=lambda r: r['answer_time'])
        return eliminated['user_id']
