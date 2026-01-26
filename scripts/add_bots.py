#!/usr/bin/env python3
"""
Скрипт для добавления ботов в базу данных.
Создает по 9 ботов каждой сложности (novice, amateur, expert).
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.session import db_session
from database.models import User
from utils.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def add_bots():
    """Добавляет ботов в базу данных."""
    # Генерируем имена ботов для каждой сложности
    bot_names = {
        'novice': ['Bot_Novice_1', 'Bot_Novice_2', 'Bot_Novice_3', 'Bot_Novice_4', 
                   'Bot_Novice_5', 'Bot_Novice_6', 'Bot_Novice_7', 'Bot_Novice_8', 'Bot_Novice_9'],
        'amateur': ['Bot_Amateur_1', 'Bot_Amateur_2', 'Bot_Amateur_3', 'Bot_Amateur_4',
                    'Bot_Amateur_5', 'Bot_Amateur_6', 'Bot_Amateur_7', 'Bot_Amateur_8', 'Bot_Amateur_9'],
        'expert': ['Bot_Expert_1', 'Bot_Expert_2', 'Bot_Expert_3', 'Bot_Expert_4',
                   'Bot_Expert_5', 'Bot_Expert_6', 'Bot_Expert_7', 'Bot_Expert_8', 'Bot_Expert_9']
    }
    
    total_created = 0
    total_existing = 0
    
    with db_session() as session:
        for difficulty, names in bot_names.items():
            logger.info(f"Processing {difficulty} bots...")
            created_count = 0
            existing_count = 0
            
            for bot_name in names:
                # Проверяем, существует ли уже такой бот
                existing = session.query(User).filter(
                    User.username == bot_name,
                    User.is_bot == True
                ).first()
                
                if existing:
                    logger.debug(f"Bot {bot_name} already exists (ID: {existing.id})")
                    existing_count += 1
                    continue
                
                # Создаем нового бота
                bot = User(
                    telegram_id=None,
                    username=bot_name,
                    full_name=bot_name,
                    is_bot=True,
                    bot_difficulty=difficulty,
                    rating=0,
                    games_played=0,
                    games_won=0
                )
                session.add(bot)
                created_count += 1
                logger.info(f"Created bot: {bot_name} (difficulty: {difficulty})")
            
            session.commit()
            logger.info(f"{difficulty}: created {created_count}, already existed {existing_count}")
            total_created += created_count
            total_existing += existing_count
    
    logger.info(f"\n{'='*60}")
    logger.info(f"SUMMARY:")
    logger.info(f"  Created: {total_created} bots")
    logger.info(f"  Already existed: {total_existing} bots")
    logger.info(f"  Total: {total_created + total_existing} bots")
    logger.info(f"{'='*60}")
    
    return total_created, total_existing


def main():
    """Основная функция."""
    print("="*60)
    print("ДОБАВЛЕНИЕ БОТОВ В БАЗУ ДАННЫХ")
    print("="*60)
    print("Создаю по 9 ботов каждой сложности:")
    print("  - Novice (новичок): 9 ботов")
    print("  - Amateur (любитель): 9 ботов")
    print("  - Expert (эксперт): 9 ботов")
    print("  Всего: 27 ботов")
    print()
    
    try:
        created, existing = add_bots()
        
        print()
        print("="*60)
        print("РЕЗУЛЬТАТЫ")
        print("="*60)
        print(f"Создано новых ботов: {created}")
        print(f"Уже существовало: {existing}")
        print(f"Всего ботов в базе: {created + existing}")
        print("="*60)
        
        if created > 0:
            print("\n[OK] Боты успешно добавлены!")
        else:
            print("\n[INFO] Все боты уже существуют в базе данных")
        
    except Exception as e:
        logger.error(f"Ошибка при добавлении ботов: {e}", exc_info=True)
        print(f"\n[ERROR] Ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
