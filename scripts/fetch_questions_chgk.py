#!/usr/bin/env python3
"""
Скрипт для загрузки вопросов с db.chgk.info и импорта в базу данных.
Адаптирован под структуру базы данных trivia-bot.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import json
import random
import time
from pathlib import Path
from typing import List, Dict, Optional
from database.session import db_session
from database.models import Question, Theme
from utils.logging import get_logger, setup_logging
import config

setup_logging()
logger = get_logger(__name__)

# Маппинг тем ЧГК на темы в базе данных
# Ключ - ID темы в ЧГК, значение - (код темы, название темы)
CHGK_THEME_MAPPING = {
    1: ("history", "История"),
    2: ("literature", "Литература"),
    4: ("geography", "География"),
    5: ("cinema", "Кино"),
    6: ("music", "Музыка"),
    7: ("sport", "Спорт"),
    8: ("science", "Наука"),
    9: ("medicine", "Медицина"),
    10: ("languages", "Языки"),
    11: ("math", "Математика"),
    12: ("animals", "Животные"),
    13: ("food", "Еда"),
    14: ("mythology", "Мифология"),
    15: ("inventions", "Изобретения"),
    16: ("politics", "Политика")
}

# Дистракторы для генерации неправильных вариантов ответа
DISTRACTORS = {
    "history": ["1917", "1941", "1812", "1991", "1066", "1789"],
    "literature": ["Пушкин", "Толстой", "Достоевский", "Гоголь", "Чехов", "Тургенев"],
    "geography": ["Москва", "Санкт-Петербург", "Казань", "Екатеринбург", "Новосибирск", "Краснодар"],
    "cinema": ["Балабанов", "Михалков", "Бондарчук", "Лунгин", "Звягинцев", "Сокуров"],
    "music": ["Чайковский", "Рахманинов", "Прокофьев", "Шостакович", "Мусоргский", "Римский-Корсаков"],
    "sport": ["Месси", "Роналду", "Неймар", "Мбаппе", "Халанд", "Бензема"],
    "science": ["Ньютон", "Эйнштейн", "Галилей", "Кюри", "Дарвин", "Пастер"],
    "medicine": ["Сердце", "Печень", "Мозг", "Лёгкие", "Почки", "Желудок"],
    "languages": ["английский", "французский", "немецкий", "испанский", "итальянский", "китайский"],
    "math": ["3.14", "2.71", "1.61", "6.28", "1.41", "2.23"],
    "animals": ["лев", "тигр", "медведь", "волк", "лиса", "заяц"],
    "food": ["борщ", "пельмени", "шашлык", "блины", "окрошка", "щи"],
    "mythology": ["Зевс", "Один", "Ра", "Анубис", "Тор", "Аполлон"],
    "inventions": ["Эдисон", "Тесла", "Белл", "Форд", "Рентген", "Пастер"],
    "politics": ["Путин", "Байден", "Си", "Макрон", "Меркель", "Трамп"]
}


def get_or_create_theme(session, theme_code: str, theme_name: str) -> Optional[int]:
    """Получить или создать тему по коду."""
    theme = session.query(Theme).filter(Theme.code == theme_code).first()
    if theme:
        return theme.id
    
    # Создаем тему, если её нет
    theme = Theme(
        code=theme_code,
        name=theme_name,
        description=f"Вопросы по теме: {theme_name}"
    )
    session.add(theme)
    session.flush()
    logger.info(f"Создана новая тема: {theme_name} (код: {theme_code})")
    return theme.id


def fetch_questions_from_chgk(theme_id: int, count_per_theme: int = 100, max_pages: int = 20) -> List[Dict]:
    """
    Скачивает вопросы по теме с db.chgk.info.
    
    Args:
        theme_id: ID темы в ЧГК
        count_per_theme: Количество вопросов для загрузки
        max_pages: Максимальное количество страниц для проверки
        
    Returns:
        Список вопросов в формате базы данных
    """
    questions = []
    page = 0
    url_base = "https://db.chgk.info/api/v3/questions"
    
    logger.info(f"Начинаю загрузку вопросов для темы ЧГК ID {theme_id}...")
    
    while len(questions) < count_per_theme and page < max_pages:
        params = {
            '_format': 'json',
            'themeId': theme_id,
            'limit': 50,
            'page': page
        }
        
        try:
            response = requests.get(url_base, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            items = data.get('hydra:member', [])
            if not items:
                logger.info(f"Больше нет вопросов на странице {page}")
                break
                
            logger.info(f"Получено {len(items)} вопросов со страницы {page}")
            
            for item in items:
                q_text = item.get('question', '').replace('\n', ' ').strip()
                answer = item.get('answer', '').strip()
                
                # Фильтруем слишком короткие вопросы и ответы
                if len(q_text) < 20 or len(answer) < 2:
                    continue
                
                # Ограничиваем длину вопроса
                if len(q_text) > 500:
                    q_text = q_text[:497] + "..."
                
                # Ограничиваем длину ответа
                if len(answer) > 200:
                    answer = answer[:197] + "..."
                
                # Генерируем варианты ответа
                theme_info = CHGK_THEME_MAPPING.get(theme_id)
                if not theme_info:
                    continue
                theme_code, theme_name = theme_info
                distractors = DISTRACTORS.get(theme_code, ["нет", "да", "возможно", "неизвестно"])
                
                # Создаем список вариантов
                options = [answer]
                
                # Добавляем дистракторы, избегая дубликатов
                used_distractors = set()
                while len(options) < 4 and len(used_distractors) < len(distractors):
                    distractor = random.choice(distractors)
                    if distractor not in used_distractors and distractor.lower() != answer.lower():
                        options.append(distractor)
                        used_distractors.add(distractor)
                
                # Если не хватило дистракторов, добавляем общие
                while len(options) < 4:
                    general = random.choice(["нет", "да", "неизвестно", "возможно"])
                    if general not in options:
                        options.append(general)
                
                # Перемешиваем варианты
                random.shuffle(options)
                correct_idx = options.index(answer)
                correct_option = chr(65 + correct_idx)  # 'A', 'B', 'C', 'D'
                
                question = {
                    "question_text": q_text,
                    "option_a": options[0][:200],  # Ограничиваем длину
                    "option_b": options[1][:200],
                    "option_c": options[2][:200] if len(options) > 2 else "Нет данных",
                    "option_d": options[3][:200] if len(options) > 3 else "Нет данных",
                    "correct_option": correct_option,
                    "difficulty": "medium",
                    "theme_code": theme_code
                }
                questions.append(question)
                
                if len(questions) >= count_per_theme:
                    break
            
            page += 1
            time.sleep(1)  # Пауза между запросами, чтобы не перегружать API
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при запросе к API для темы {theme_id}, страница {page}: {e}")
            break
        except Exception as e:
            logger.error(f"Неожиданная ошибка для темы {theme_id}, страница {page}: {e}", exc_info=True)
            break
    
    logger.info(f"Загружено {len(questions)} вопросов для темы ЧГК ID {theme_id}")
    return questions[:count_per_theme]


def import_questions_to_db(questions: List[Dict], chgk_theme_id: int) -> int:
    """
    Импортирует вопросы в базу данных.
    
    Args:
        questions: Список вопросов
        theme_code: Код темы в базе данных
        
    Returns:
        Количество успешно импортированных вопросов
    """
    imported = 0
    
    with db_session() as session:
        # Получаем или создаем тему
        theme_info = CHGK_THEME_MAPPING.get(theme_id if isinstance(theme_code, int) else None)
        if theme_info:
            theme_code_db, theme_name = theme_info
        else:
            theme_code_db = theme_code
            theme_name = theme_code.capitalize()
        
        theme_id = get_or_create_theme(session, theme_code_db, theme_name)
        if not theme_id:
            logger.error(f"Не удалось получить или создать тему '{theme_code_db}'")
            return 0
        
        for q_data in questions:
            try:
                # Проверяем, нет ли уже такого вопроса
                existing = session.query(Question).filter(
                    Question.question_text == q_data['question_text'],
                    Question.theme_id == theme_id
                ).first()
                
                if existing:
                    logger.debug(f"Вопрос уже существует: {q_data['question_text'][:50]}...")
                    continue
                
                # Создаем новый вопрос
                question = Question(
                    theme_id=theme_id,
                    question_text=q_data['question_text'],
                    option_a=q_data['option_a'],
                    option_b=q_data['option_b'],
                    option_c=q_data.get('option_c', 'Нет данных'),
                    option_d=q_data.get('option_d', 'Нет данных'),
                    correct_option=q_data['correct_option'],
                    difficulty=q_data.get('difficulty', 'medium'),
                    source_type='parsed',
                    is_approved=True
                )
                
                session.add(question)
                imported += 1
                
            except Exception as e:
                logger.error(f"Ошибка при импорте вопроса: {e}", exc_info=True)
                continue
        
        try:
            session.commit()
            logger.info(f"Успешно импортировано {imported} вопросов для темы '{theme_code}'")
        except Exception as e:
            logger.error(f"Ошибка при коммите: {e}", exc_info=True)
            session.rollback()
            return 0
    
    return imported


def main():
    """Основная функция."""
    logger.info("Начинаю загрузку вопросов с db.chgk.info...")
    
    total_imported = 0
    
    # Загружаем вопросы по каждой теме
    for chgk_theme_id, (theme_code, theme_name) in CHGK_THEME_MAPPING.items():
        logger.info(f"\n{'='*60}")
        logger.info(f"Обработка темы: {theme_name} ({theme_code}, ЧГК ID: {chgk_theme_id})")
        logger.info(f"{'='*60}")
        
        # Загружаем вопросы
        questions = fetch_questions_from_chgk(chgk_theme_id, count_per_theme=100)
        
        if not questions:
            logger.warning(f"Не удалось загрузить вопросы для темы {theme_name}")
            continue
        
        # Импортируем в базу данных
        imported = import_questions_to_db(questions, chgk_theme_id)
        total_imported += imported
        
        logger.info(f"Импортировано {imported} из {len(questions)} загруженных вопросов для темы {theme_name}")
        
        # Пауза между темами
        time.sleep(2)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"🎉 ГОТОВО! Всего импортировано вопросов: {total_imported}")
    logger.info(f"{'='*60}")


if __name__ == "__main__":
    try:
        main()
        print("✅ Импорт завершен успешно!")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        print(f"❌ Ошибка при импорте: {e}")
        sys.exit(1)
