"""
Game engine - core game logic and state management.
"""
from typing import List, Dict, Optional, Any
from datetime import datetime
import pytz
import random
from database.models import Game, GamePlayer, Round, RoundQuestion, Answer, Question, User
from database.session import db_session
from database.queries import RoundQueries, QuestionQueries
from game.elimination import EliminationLogic, PlayerRoundResult
from game.rating import RatingSystem
import config


class GameEngine:
    """Main game engine class."""
    
    def __init__(self):
        """Initialize game engine."""
        self.elimination_logic = EliminationLogic()
        self.rating_system = RatingSystem()
        self.config = config.config
    
    def start_game(self, game_id: int) -> bool:
        """
        Start a game - create first round and questions.
        
        Args:
            game_id: Game ID
        
        Returns:
            True if started successfully, False otherwise
        """
        with db_session() as session:
            game = session.query(Game).filter(Game.id == game_id).first()
            if not game:
                return False
            
            if game.status not in ['waiting', 'pre_start']:
                return False
            
            # Update game status
            game.status = 'in_progress'
            game.current_round = 1
            game.started_at = datetime.now(pytz.UTC)
            session.flush()
            
            # Create first round
            round_obj = self._create_round(session, game_id, 1, game.theme_id)
            if not round_obj:
                return False
            
            session.commit()
            return True
    
    def _shuffle_question_options(self, question: Question) -> tuple[Dict[str, str], str]:
        """
        Shuffle answer options for a question.
        
        Args:
            question: Question object with options A, B, C, D
            
        Returns:
            Tuple of (shuffled_mapping, correct_option_shuffled):
            - shuffled_mapping: Dict mapping new positions to original positions
                               e.g., {"A": "C", "B": "A", "C": "B", "D": "D"}
                               This means: new position A shows original option C
            - correct_option_shuffled: The correct option letter after shuffling
        """
        from utils.logging import get_logger
        logger = get_logger(__name__)
        
        # Collect available options with their original positions
        original_options = []
        available_letters = []
        
        if question.option_a:
            original_options.append(('A', question.option_a))
            available_letters.append('A')
        if question.option_b:
            original_options.append(('B', question.option_b))
            available_letters.append('B')
        if question.option_c:
            original_options.append(('C', question.option_c))
            available_letters.append('C')
        if question.option_d:
            original_options.append(('D', question.option_d))
            available_letters.append('D')
        
        # Store original correct option
        correct_original = question.correct_option.upper()
        logger.debug(f"Shuffling question {question.id}: original correct={correct_original}, available={available_letters}")
        
        # Shuffle the list of options
        shuffled_options = original_options.copy()
        random.shuffle(shuffled_options)
        
        logger.debug(f"After shuffle: {[(l, t[:20]) for l, t in shuffled_options]}")
        
        # Create mapping: new_position -> original_position
        # This tells us which original option text to show at each new position
        shuffled_mapping = {}
        for i, (original_letter, _) in enumerate(shuffled_options):
            new_letter = available_letters[i]
            shuffled_mapping[new_letter] = original_letter
        
        logger.debug(f"Shuffled mapping: {shuffled_mapping}")
        
        # Find where the correct option ended up
        # Find which new position contains the correct original option
        correct_option_shuffled = next(
            (new_letter for new_letter, orig_letter in shuffled_mapping.items() if orig_letter == correct_original),
            correct_original
        )
        
        logger.debug(f"Correct option after shuffle: {correct_option_shuffled} (was {correct_original})")
        
        return shuffled_mapping, correct_option_shuffled
    
    def _create_round(
        self,
        session,
        game_id: int,
        round_number: int,
        theme_id: Optional[int] = None
    ) -> Optional[Round]:
        """Create a new round with questions."""
        from utils.logging import get_logger
        logger = get_logger(__name__)
        
        # Create round
        round_obj = RoundQueries.create_round(
            session, game_id, round_number, theme_id
        )
        if not round_obj:
            logger.error(f"Failed to create round object for game {game_id}, round {round_number}")
            return None
        
        logger.info(f"Round object created: game_id={game_id}, round_number={round_number}, round_id={round_obj.id}")
        
        # Select questions for this round
        questions = QuestionQueries.get_unused_questions_for_game(
            session, game_id, theme_id, limit=self.config.QUESTIONS_PER_ROUND
        )
        
        logger.info(f"Found {len(questions)} unused questions for game {game_id}, need {self.config.QUESTIONS_PER_ROUND}")
        
        if len(questions) == 0:
            # No questions available - cannot create round
            logger.error(f"No questions available for round {round_number} in game {game_id}")
            return None
        
        if len(questions) < self.config.QUESTIONS_PER_ROUND:
            # Not enough questions - use what we have and warn
            logger.warning(
                f"Not enough questions for round {round_number} in game {game_id}: "
                f"found {len(questions)}, need {self.config.QUESTIONS_PER_ROUND}. "
                f"Using {len(questions)} questions instead."
            )
        
        # Create round questions (use available questions, even if less than needed)
        questions_to_use = questions[:min(len(questions), self.config.QUESTIONS_PER_ROUND)]
        for i, question in enumerate(questions_to_use, 1):
            # Shuffle answer options for this question
            shuffled_mapping, correct_option_shuffled = self._shuffle_question_options(question)
            
            round_question = RoundQuestion(
                round_id=round_obj.id,
                question_id=question.id,
                question_number=i,
                time_limit_sec=self.config.QUESTION_TIME_LIMIT,
                shuffled_options=shuffled_mapping,
                correct_option_shuffled=correct_option_shuffled
            )
            session.add(round_question)
            
            # Mark question as used
            QuestionQueries.mark_question_as_used(session, game_id, question.id)
        
        session.flush()
        return round_obj
    
    def process_answer_and_check_early_victory(
        self,
        game_id: int,
        round_id: int,
        round_question_id: int,
        user_id: int,
        selected_option: str,
        is_correct: bool,
        answer_time: float
    ) -> Dict[str, Any]:
        """
        Process player's answer and check for early victory in final round.
        
        This method should be called after each answer in the final round
        to check if early victory is possible.
        
        Args:
            game_id: Game ID
            round_id: Round ID
            round_question_id: Round question ID
            user_id: User ID who answered
            selected_option: Selected option ('A', 'B', 'C', 'D')
            is_correct: Whether answer is correct
            answer_time: Time taken to answer in seconds
        
        Returns:
            Dict with:
                - 'early_victory': bool - whether early victory occurred
                - 'winner_user_id': Optional[int] - winner if early victory
                - 'game_finished': bool - whether game should be finished
        """
        from database.models import Answer as AnswerModel
        from decimal import Decimal
        
        with db_session() as session:
            # Convert answer_time to Decimal for database compatibility
            answer_time_decimal = Decimal(str(answer_time))
            
            # Save answer
            answer = AnswerModel(
                game_id=game_id,
                round_id=round_id,
                round_question_id=round_question_id,
                user_id=user_id,
                selected_option=selected_option,
                is_correct=is_correct,
                answer_time=answer_time_decimal,
                answered_at=datetime.now(pytz.UTC)
            )
            session.add(answer)
            
            # Update game player stats
            game_player = session.query(GamePlayer).filter(
                GamePlayer.game_id == game_id,
                GamePlayer.user_id == user_id
            ).first()
            
            if game_player:
                if is_correct:
                    game_player.total_score += 1
                game_player.total_time += answer_time_decimal
            
            session.flush()
            
            # Check for early victory (only in final round)
            winner_user_id = self.check_early_victory(game_id, round_id)
            
            if winner_user_id:
                # Early victory! Finish game immediately
                session.commit()
                self.finish_game(game_id, early_victory=True, winner_user_id=winner_user_id)
                
                return {
                    'early_victory': True,
                    'winner_user_id': winner_user_id,
                    'game_finished': True
                }
            
            session.commit()
            
            return {
                'early_victory': False,
                'winner_user_id': None,
                'game_finished': False
            }
    
    def finish_round(self, game_id: int, round_number: int) -> Optional[int]:
        """
        Finish a round and determine eliminated player.
        
        Args:
            game_id: Game ID
            round_number: Round number
        
        Returns:
            Eliminated user_id or None if no elimination or tie-break needed
        """
        with db_session() as session:
            game = session.query(Game).filter(Game.id == game_id).first()
            if not game:
                return None
            
            round_obj = session.query(Round).filter(
                Round.game_id == game_id,
                Round.round_number == round_number
            ).first()
            
            if not round_obj:
                return None
            
            # Get all alive players
            alive_players = [
                gp for gp in game.players
                if not gp.is_eliminated
            ]
            
            # Special case: if only 2 players and this is final round, check for early victory first
            if len(alive_players) == 2 and round_number == self.config.ROUNDS_PER_GAME:
                winner_user_id = self.check_early_victory(game_id, round_obj.id)
                if winner_user_id:
                    # Early victory occurred - finish game
                    self.finish_game(game_id, early_victory=True, winner_user_id=winner_user_id)
                    return None  # No elimination, game finished
            
            # Collect round results
            round_results = []
            for game_player in alive_players:
                # Get player's answers for this round
                answers = session.query(Answer).filter(
                    Answer.game_id == game_id,
                    Answer.round_id == round_obj.id,
                    Answer.user_id == game_player.user_id
                ).all()
                
                correct_count = sum(1 for a in answers if a.is_correct)
                total_time = sum(
                    float(a.answer_time or 0) for a in answers
                )
                
                round_results.append(PlayerRoundResult(
                    user_id=game_player.user_id,
                    correct_answers=correct_count,
                    total_time=total_time,
                    answers=[
                        {
                            'is_correct': a.is_correct,
                            'answer_time': a.answer_time
                        }
                        for a in answers
                    ]
                ))
            
            # Determine eliminated player
            eliminated_user_id, needs_tie_break = self.elimination_logic.determine_eliminated_player(
                round_results
            )
            
            if needs_tie_break:
                # Return special value to trigger tie-break
                return -1
            
            # Mark player as eliminated
            if eliminated_user_id:
                eliminated_player = next(
                    (gp for gp in alive_players if gp.user_id == eliminated_user_id),
                    None
                )
                if eliminated_player:
                    eliminated_player.is_eliminated = True
                    eliminated_player.eliminated_round = round_number
            
            # Update round status
            round_obj.status = 'finished'
            round_obj.finished_at = datetime.now(pytz.UTC)
            
            # Check if this was the final round (2 players remaining)
            if len(alive_players) == 2 and round_number == self.config.ROUNDS_PER_GAME:
                game.is_final_stage = True
            
            session.commit()
            return eliminated_user_id
    
    def check_early_victory(
        self,
        game_id: int,
        round_id: int
    ) -> Optional[int]:
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
            Winner user_id if early victory, None otherwise
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
                    'correct_answers': correct_count
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
                return leader['user_id']
            
            return None
    
    def finish_game(self, game_id: int, early_victory: bool = False, winner_user_id: Optional[int] = None) -> bool:
        """
        Finish a game - calculate final places and update ratings.
        
        Args:
            game_id: Game ID
            early_victory: Whether game finished with early victory
            winner_user_id: User ID of winner (if early victory)
        
        Returns:
            True if finished successfully
        """
        with db_session() as session:
            game = session.query(Game).filter(Game.id == game_id).first()
            if not game:
                return False
            
            # Get all players sorted by score and time
            players = sorted(
                [gp for gp in game.players if not gp.is_eliminated],
                key=lambda p: (-p.total_score, p.total_time)
            )
            
            # Assign final places
            if early_victory and winner_user_id:
                # Early victory - winner is first, other is second
                for game_player in players:
                    if game_player.user_id == winner_user_id:
                        game_player.final_place = 1
                    else:
                        game_player.final_place = 2
            else:
                # Normal finish
                for place, game_player in enumerate(players, 1):
                    game_player.final_place = place
            
            # Update ratings
            rating_changes = self.rating_system.update_ratings_after_game(
                game.players,
                is_training=(game.game_type == 'training')
            )
            
            # Apply rating changes
            for user_id, delta in rating_changes.items():
                user = session.query(User).filter(User.id == user_id).first()
                if user:
                    user.rating += delta
                    user.games_played += 1
                    if delta > 0:  # Winner bonus
                        user.games_won += 1
            
            # Update game status
            game.status = 'finished'
            game.finished_at = datetime.now(pytz.UTC)
            
            # Mark final stage if it was final round
            if game.current_round == self.config.ROUNDS_PER_GAME:
                game.is_final_stage = True
            
            session.commit()
            return True
