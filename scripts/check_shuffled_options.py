#!/usr/bin/env python3
"""
Script to check shuffled options in database.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.session import db_session
from database.models import RoundQuestion, Question, Round, Game
from utils.logging import setup_logging

setup_logging()

def check_latest_game():
    """Check shuffled options for the latest game."""
    with db_session() as session:
        # Get latest game
        latest_game = session.query(Game).order_by(Game.id.desc()).first()
        
        if not latest_game:
            print("No games found in database")
            return
        
        print(f"Latest game ID: {latest_game.id}")
        print(f"Game type: {latest_game.game_type}")
        print(f"Status: {latest_game.status}")
        print(f"Created at: {latest_game.created_at}")
        print("=" * 80)
        
        # Get rounds for this game
        rounds = session.query(Round).filter(
            Round.game_id == latest_game.id
        ).order_by(Round.round_number).all()
        
        if not rounds:
            print("No rounds found for this game")
            return
        
        for round_obj in rounds:
            print(f"\nRound {round_obj.round_number} (ID: {round_obj.id}):")
            print("-" * 80)
            
            # Get round questions
            round_questions = session.query(RoundQuestion).filter(
                RoundQuestion.round_id == round_obj.id
            ).order_by(RoundQuestion.question_number).all()
            
            for rq in round_questions:
                question = session.query(Question).filter(
                    Question.id == rq.question_id
                ).first()
                
                print(f"\n  Question {rq.question_number} (RoundQuestion ID: {rq.id}):")
                print(f"    Question ID: {question.id if question else 'NOT FOUND'}")
                print(f"    Original correct option: {question.correct_option if question else 'N/A'}")
                print(f"    Shuffled options: {rq.shuffled_options}")
                print(f"    Correct option shuffled: {rq.correct_option_shuffled}")
                
                if rq.shuffled_options:
                    print(f"    ✓ Has shuffled options")
                    if rq.correct_option_shuffled:
                        print(f"    ✓ Has shuffled correct option: {rq.correct_option_shuffled}")
                    else:
                        print(f"    ⚠ WARNING: Has shuffled_options but NO correct_option_shuffled!")
                else:
                    print(f"    ✗ No shuffled options (using original order)")
                
                # Show original options
                if question:
                    print(f"    Original options:")
                    if question.option_a:
                        print(f"      A) {question.option_a[:50]}")
                    if question.option_b:
                        print(f"      B) {question.option_b[:50]}")
                    if question.option_c:
                        print(f"      C) {question.option_c[:50]}")
                    if question.option_d:
                        print(f"      D) {question.option_d[:50]}")
                    
                    # Show shuffled options if available
                    if rq.shuffled_options:
                        print(f"    Shuffled options (new_pos -> original_pos):")
                        for new_pos in ['A', 'B', 'C', 'D']:
                            if new_pos in rq.shuffled_options:
                                orig_pos = rq.shuffled_options[new_pos]
                                orig_text = None
                                if orig_pos == 'A':
                                    orig_text = question.option_a
                                elif orig_pos == 'B':
                                    orig_text = question.option_b
                                elif orig_pos == 'C':
                                    orig_text = question.option_c
                                elif orig_pos == 'D':
                                    orig_text = question.option_d
                                
                                if orig_text:
                                    marker = " ← CORRECT" if rq.correct_option_shuffled == new_pos else ""
                                    print(f"      {new_pos}) {orig_text[:50]} (was {orig_pos}){marker}")


def check_specific_round_question(round_question_id: int):
    """Check specific round question."""
    with db_session() as session:
        rq = session.query(RoundQuestion).filter(
            RoundQuestion.id == round_question_id
        ).first()
        
        if not rq:
            print(f"RoundQuestion {round_question_id} not found")
            return
        
        question = session.query(Question).filter(
            Question.id == rq.question_id
        ).first()
        
        print(f"RoundQuestion ID: {rq.id}")
        print(f"Round ID: {rq.round_id}")
        print(f"Question Number: {rq.question_number}")
        print(f"Question ID: {question.id if question else 'NOT FOUND'}")
        print(f"Original correct option: {question.correct_option if question else 'N/A'}")
        print(f"Shuffled options: {rq.shuffled_options}")
        print(f"Correct option shuffled: {rq.correct_option_shuffled}")
        
        if question:
            print(f"\nOriginal options:")
            if question.option_a:
                print(f"  A) {question.option_a}")
            if question.option_b:
                print(f"  B) {question.option_b}")
            if question.option_c:
                print(f"  C) {question.option_c}")
            if question.option_d:
                print(f"  D) {question.option_d}")
            
            if rq.shuffled_options:
                print(f"\nShuffled display (what user sees):")
                for new_pos in ['A', 'B', 'C', 'D']:
                    if new_pos in rq.shuffled_options:
                        orig_pos = rq.shuffled_options[new_pos]
                        orig_text = None
                        if orig_pos == 'A':
                            orig_text = question.option_a
                        elif orig_pos == 'B':
                            orig_text = question.option_b
                        elif orig_pos == 'C':
                            orig_text = question.option_c
                        elif orig_pos == 'D':
                            orig_text = question.option_d
                        
                        if orig_text:
                            marker = " ← CORRECT" if rq.correct_option_shuffled == new_pos else ""
                            print(f"  {new_pos}) {orig_text} (was originally {orig_pos}){marker}")


def check_question_by_number(question_number: int):
    """Check question by number in latest game."""
    with db_session() as session:
        # Get latest game
        latest_game = session.query(Game).order_by(Game.id.desc()).first()
        
        if not latest_game:
            print("No games found in database")
            return
        
        # Get rounds for this game
        rounds = session.query(Round).filter(
            Round.game_id == latest_game.id
        ).order_by(Round.round_number).all()
        
        if not rounds:
            print("No rounds found for latest game")
            return
        
        # Find question in first round (assuming question_number is 1-10)
        for round_obj in rounds:
            rq = session.query(RoundQuestion).filter(
                RoundQuestion.round_id == round_obj.id,
                RoundQuestion.question_number == question_number
            ).first()
            
            if rq:
                print(f"Found question {question_number} in Round {round_obj.round_number}")
                print("=" * 80)
                check_specific_round_question(rq.id)
                return
        
        print(f"Question {question_number} not found in latest game")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        
        # Check if it's a question number (1-10) or round_question_id
        if arg.isdigit():
            num = int(arg)
            if num <= 10:
                # Probably a question number
                check_question_by_number(num)
            else:
                # Probably a round_question_id
                check_specific_round_question(num)
        else:
            print("Invalid argument. Must be a number (question number 1-10 or round_question_id)")
            sys.exit(1)
    else:
        # Check latest game
        check_latest_game()
