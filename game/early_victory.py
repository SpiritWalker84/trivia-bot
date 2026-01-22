"""
Early victory logic - determines if game can end early in final round.
"""
from typing import Optional, Dict, List
from database.session import db_session
from database.models import Game, Round, Answer, RoundQuestion, GamePlayer
import config


class EarlyVictoryChecker:
    """Checks for early victory conditions in final round."""
    
    def __init__(self):
        """Initialize early victory checker."""
        self.config = config.config
    
    def check_early_victory(
        self,
        game_id: int,
        round_id: int
    ) -> Optional[Dict[str, any]]:
        """
        Check if early victory is possible in final round.
        
        Early victory condition:
        - Only in final round (2 players remaining, round 10)
        - After each question, check: S_loser + Q_remaining < S_leader
        - If true, leader wins immediately
        
        Args:
            game_id: Game ID
            round_id: Round ID
        
        Returns:
            Dict with winner info if early victory, None otherwise:
                {
                    'winner_user_id': int,
                    'leader_score': int,
                    'loser_score': int,
                    'questions_remaining': int
                }
        """
        with db_session() as session:
            game = session.query(Game).filter(Game.id == game_id).first()
            if not game:
                return None
            
            round_obj = session.query(Round).filter(Round.id == round_id).first()
            if not round_obj:
                return None
            
            # Check if this is final round (2 players, round 10)
            alive_players = [
                gp for gp in game.players
                if not gp.is_eliminated
            ]
            
            if len(alive_players) != 2:
                # Not final round (not 2 players)
                return None
            
            if round_obj.round_number != self.config.ROUNDS_PER_GAME:
                # Not the last round
                return None
            
            # Get current round results for both finalists
            finalist_results = []
            for game_player in alive_players:
                # Get answers for current round
                answers = session.query(Answer).filter(
                    Answer.game_id == game_id,
                    Answer.round_id == round_id,
                    Answer.user_id == game_player.user_id
                ).all()
                
                correct_count = sum(1 for a in answers if a.is_correct)
                
                finalist_results.append({
                    'user_id': game_player.user_id,
                    'correct_answers': correct_count,
                    'game_player_id': game_player.id
                })
            
            if len(finalist_results) != 2:
                return None
            
            # Determine leader and loser
            if finalist_results[0]['correct_answers'] > finalist_results[1]['correct_answers']:
                leader = finalist_results[0]
                loser = finalist_results[1]
            elif finalist_results[1]['correct_answers'] > finalist_results[0]['correct_answers']:
                leader = finalist_results[1]
                loser = finalist_results[0]
            else:
                # Equal scores - no early victory possible
                return None
            
            # Count remaining questions in round
            total_questions = session.query(RoundQuestion).filter(
                RoundQuestion.round_id == round_id
            ).count()
            
            # Count unique questions answered by both players
            answered_question_ids = set()
            for result in finalist_results:
                answers = session.query(Answer).filter(
                    Answer.round_id == round_id,
                    Answer.user_id == result['user_id']
                ).all()
                answered_question_ids.update(a.round_question_id for a in answers)
            
            questions_remaining = total_questions - len(answered_question_ids)
            
            # Check early victory condition: S_loser + Q_remaining < S_leader
            s_loser = loser['correct_answers']
            s_leader = leader['correct_answers']
            q_remaining = questions_remaining
            
            if s_loser + q_remaining < s_leader:
                # Early victory! Leader wins
                return {
                    'winner_user_id': leader['user_id'],
                    'leader_score': s_leader,
                    'loser_score': s_loser,
                    'questions_remaining': q_remaining,
                    'loser_user_id': loser['user_id']
                }
            
            return None
