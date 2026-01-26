#!/usr/bin/env python
"""
Script to update bot_answers.py to support shuffled options.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

BOT_ANSWERS_FILE = Path(__file__).parent.parent / "tasks" / "bot_answers.py"

def main():
    """Update bot_answers.py file."""
    print(f"Updating {BOT_ANSWERS_FILE}...")
    
    try:
        with open(BOT_ANSWERS_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if already updated
        if 'shuffled_options' in content:
            print("✓ File already updated with shuffled_options support")
            return 0
        
        # Find and replace the section
        old_text = """            # Generate answer
            options = []
            if question.option_a:
                options.append('A')
            if question.option_b:
                options.append('B')
            if question.option_c:
                options.append('C')
            if question.option_d:
                options.append('D')
            
            bot_answer = bot_ai.generate_answer(
                question.id,
                question.correct_option,
                options
            )"""
        
        new_text = """            # Get available options (after shuffling)
            options = []
            if round_question.shuffled_options:
                # Use shuffled options - all new positions are available
                options = list(round_question.shuffled_options.keys())
                # Use shuffled correct option
                correct_option = round_question.correct_option_shuffled or question.correct_option
            else:
                # Fallback to original options (backward compatibility)
                if question.option_a:
                    options.append('A')
                if question.option_b:
                    options.append('B')
                if question.option_c:
                    options.append('C')
                if question.option_d:
                    options.append('D')
                correct_option = question.correct_option
            
            bot_answer = bot_ai.generate_answer(
                question.id,
                correct_option,
                options
            )"""
        
        if old_text in content:
            new_content = content.replace(old_text, new_text)
            with open(BOT_ANSWERS_FILE, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print("✓ File updated successfully!")
            return 0
        else:
            print("✗ Could not find exact pattern to replace")
            print("  Please update tasks/bot_answers.py manually (lines 81-96)")
            return 1
            
    except Exception as e:
        print(f"✗ Error updating file: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
