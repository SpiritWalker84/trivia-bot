#!/usr/bin/env python
"""
Script to add test data to database.
Creates themes, questions, and bots for testing.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.session import db_session
from database.models import Theme, Question, User
from utils.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def create_themes(session):
    """Create test themes."""
    themes_data = [
        {'code': 'movies', 'name': 'Кино', 'description': 'Вопросы о кино и фильмах'},
        {'code': 'science', 'name': 'Наука', 'description': 'Вопросы о науке'},
        {'code': 'sport', 'name': 'Спорт', 'description': 'Вопросы о спорте'},
        {'code': 'geography', 'name': 'География', 'description': 'Вопросы о географии'},
        {'code': 'history', 'name': 'История', 'description': 'Вопросы об истории'},
    ]
    
    created = 0
    for theme_data in themes_data:
        existing = session.query(Theme).filter(Theme.code == theme_data['code']).first()
        if not existing:
            theme = Theme(**theme_data)
            session.add(theme)
            created += 1
            logger.info(f"Created theme: {theme_data['name']}")
        else:
            logger.info(f"Theme already exists: {theme_data['name']}")
    
    session.commit()
    return created


def create_questions(session):
    """Create test questions."""
    questions_data = [
        # Кино
        {
            'theme_code': 'movies',
            'question_text': 'Какой актер сыграл Тони Старка в киновселенной Marvel?',
            'option_a': 'Крис Эванс',
            'option_b': 'Роберт Дауни-младший',
            'option_c': 'Крис Хемсворт',
            'option_d': 'Марк Руффало',
            'correct_option': 'B',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'movies',
            'question_text': 'В каком году вышел фильм "Титаник"?',
            'option_a': '1995',
            'option_b': '1997',
            'option_c': '1999',
            'option_d': '2001',
            'correct_option': 'B',
            'difficulty': 'easy'
        },
        {
            'theme_code': 'movies',
            'question_text': 'Кто режиссер фильма "Криминальное чтиво"?',
            'option_a': 'Мартин Скорсезе',
            'option_b': 'Квентин Тарантино',
            'option_c': 'Кристофер Нолан',
            'option_d': 'Стивен Спилберг',
            'correct_option': 'B',
            'difficulty': 'medium'
        },
        # Наука
        {
            'theme_code': 'science',
            'question_text': 'Какая планета ближе всего к Солнцу?',
            'option_a': 'Венера',
            'option_b': 'Меркурий',
            'option_c': 'Земля',
            'option_d': 'Марс',
            'correct_option': 'B',
            'difficulty': 'easy'
        },
        {
            'theme_code': 'science',
            'question_text': 'Сколько хромосом у человека?',
            'option_a': '42',
            'option_b': '44',
            'option_c': '46',
            'option_d': '48',
            'correct_option': 'C',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'science',
            'question_text': 'Какая скорость света в вакууме?',
            'option_a': '300 000 км/с',
            'option_b': '299 792 458 м/с',
            'option_c': '150 000 км/с',
            'option_d': '450 000 км/с',
            'correct_option': 'B',
            'difficulty': 'hard'
        },
        # Спорт
        {
            'theme_code': 'sport',
            'question_text': 'В каком году проходила Олимпиада в Москве?',
            'option_a': '1976',
            'option_b': '1980',
            'option_c': '1984',
            'option_d': '1988',
            'correct_option': 'B',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'sport',
            'question_text': 'Сколько игроков в футбольной команде на поле?',
            'option_a': '10',
            'option_b': '11',
            'option_c': '12',
            'option_d': '9',
            'correct_option': 'B',
            'difficulty': 'easy'
        },
        # География
        {
            'theme_code': 'geography',
            'question_text': 'Какая самая большая страна по площади?',
            'option_a': 'Канада',
            'option_b': 'Китай',
            'option_c': 'Россия',
            'option_d': 'США',
            'correct_option': 'C',
            'difficulty': 'easy'
        },
        {
            'theme_code': 'geography',
            'question_text': 'Какая самая длинная река в мире?',
            'option_a': 'Амазонка',
            'option_b': 'Нил',
            'option_c': 'Янцзы',
            'option_d': 'Миссисипи',
            'correct_option': 'A',
            'difficulty': 'medium'
        },
        # История
        {
            'theme_code': 'history',
            'question_text': 'В каком году началась Вторая мировая война?',
            'option_a': '1937',
            'option_b': '1939',
            'option_c': '1941',
            'option_d': '1943',
            'correct_option': 'B',
            'difficulty': 'medium'
        },
    ]
    
    created = 0
    for q_data in questions_data:
        theme = session.query(Theme).filter(Theme.code == q_data['theme_code']).first()
        if not theme:
            logger.warning(f"Theme {q_data['theme_code']} not found, skipping question")
            continue
        
        # Check if question already exists
        existing = session.query(Question).filter(
            Question.question_text == q_data['question_text']
        ).first()
        
        if not existing:
            question = Question(
                theme_id=theme.id,
                question_text=q_data['question_text'],
                option_a=q_data['option_a'],
                option_b=q_data['option_b'],
                option_c=q_data.get('option_c'),
                option_d=q_data.get('option_d'),
                correct_option=q_data['correct_option'],
                difficulty=q_data.get('difficulty', 'medium'),
                source_type='test',
                is_approved=True
            )
            session.add(question)
            created += 1
            logger.info(f"Created question: {q_data['question_text'][:50]}...")
    
    session.commit()
    return created


def create_bots(session):
    """Create test bots."""
    bots_data = [
        {'username': 'Bot_Alpha', 'bot_difficulty': 'novice'},
        {'username': 'Bot_Beta', 'bot_difficulty': 'novice'},
        {'username': 'Bot_Gamma', 'bot_difficulty': 'amateur'},
        {'username': 'Bot_Delta', 'bot_difficulty': 'amateur'},
        {'username': 'Bot_Epsilon', 'bot_difficulty': 'amateur'},
        {'username': 'Bot_Zeta', 'bot_difficulty': 'expert'},
        {'username': 'Bot_Eta', 'bot_difficulty': 'expert'},
        {'username': 'Bot_Theta', 'bot_difficulty': 'expert'},
        {'username': 'Bot_Iota', 'bot_difficulty': 'expert'},
        {'username': 'Bot_Kappa', 'bot_difficulty': 'expert'},
    ]
    
    created = 0
    for bot_data in bots_data:
        existing = session.query(User).filter(
            User.username == bot_data['username'],
            User.is_bot == True
        ).first()
        
        if not existing:
            bot = User(
                telegram_id=None,
                username=bot_data['username'],
                full_name=bot_data['username'],
                is_bot=True,
                bot_difficulty=bot_data['bot_difficulty']
            )
            session.add(bot)
            created += 1
            logger.info(f"Created bot: {bot_data['username']} ({bot_data['bot_difficulty']})")
        else:
            logger.info(f"Bot already exists: {bot_data['username']}")
    
    session.commit()
    return created


def main():
    """Main function."""
    logger.info("Starting test data creation...")
    
    with db_session() as session:
        themes_count = create_themes(session)
        questions_count = create_questions(session)
        bots_count = create_bots(session)
    
    logger.info("=" * 50)
    logger.info("Test data creation completed!")
    logger.info(f"Themes created: {themes_count}")
    logger.info(f"Questions created: {questions_count}")
    logger.info(f"Bots created: {bots_count}")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
