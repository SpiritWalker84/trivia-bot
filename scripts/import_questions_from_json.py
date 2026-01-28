#!/usr/bin/env python3
"""
Скрипт для импорта вопросов из JSON файла в базу данных.
Использование: python scripts/import_questions_from_json.py [путь_к_json_файлу]
"""
import sys
import os
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.session import db_session
from database.models import Question, Theme
from database.queries import ThemeQueries
from utils.logging import setup_logging, get_logger
import config

setup_logging()
logger = get_logger(__name__)


def get_or_create_theme(session, theme_code: str, theme_name: str) -> int:
    """Получить или создать тему по коду."""
    theme = ThemeQueries.get_theme_by_code(session, theme_code)
    if theme:
        logger.debug(f"Тема '{theme_name}' уже существует (ID: {theme.id})")
        return theme.id
    
    # Создаем тему, если её нет
    theme = Theme(
        code=theme_code,
        name=theme_name,
        description=f"Вопросы по теме: {theme_name}"
    )
    session.add(theme)
    session.flush()
    logger.info(f"Создана новая тема: {theme_name} (код: {theme_code}, ID: {theme.id})")
    return theme.id


def import_questions_from_json(json_file_path: str) -> dict:
    """
    Импортирует вопросы из JSON файла в базу данных.
    
    Args:
        json_file_path: Путь к JSON файлу с вопросами
        
    Returns:
        Словарь со статистикой импорта
    """
    # Читаем JSON файл
    json_path = Path(json_file_path)
    if not json_path.exists():
        raise FileNotFoundError(f"Файл не найден: {json_file_path}")
    
    logger.info(f"Читаю файл: {json_path}")
    with open(json_path, 'r', encoding='utf-8') as f:
        questions_data = json.load(f)
    
    if not isinstance(questions_data, list):
        raise ValueError("JSON файл должен содержать массив вопросов")
    
    logger.info(f"Найдено {len(questions_data)} вопросов в файле")
    
    stats = {
        "total": len(questions_data),
        "imported": 0,
        "skipped": 0,
        "errors": 0,
        "themes_created": 0
    }
    
    with db_session() as session:
        # Группируем вопросы по темам для более эффективной обработки
        themes_map = {}
        for q_data in questions_data:
            theme_code = q_data.get("theme_code")
            if theme_code not in themes_map:
                theme_name = q_data.get("theme_name", theme_code)
                theme_id = get_or_create_theme(session, theme_code, theme_name)
                themes_map[theme_code] = theme_id
                if theme_id:
                    stats["themes_created"] += 1
        
        # Импортируем вопросы
        for idx, q_data in enumerate(questions_data, 1):
            try:
                theme_code = q_data.get("theme_code")
                if not theme_code:
                    logger.warning(f"Вопрос {idx}: отсутствует theme_code, пропускаю")
                    stats["skipped"] += 1
                    continue
                
                theme_id = themes_map.get(theme_code)
                if not theme_id:
                    logger.warning(f"Вопрос {idx}: не найдена тема '{theme_code}', пропускаю")
                    stats["skipped"] += 1
                    continue
                
                # Проверяем, нет ли уже такого вопроса
                # Проверяем по тексту вопроса, правильному ответу и вариантам ответов
                # Это позволяет импортировать вопросы с одинаковым текстом, но разными вариантами ответов
                question_text = q_data.get("question_text", "")
                correct_option = q_data.get("correct_option", "A")
                option_a = q_data.get("option_a", "")
                option_b = q_data.get("option_b", "")
                option_c = q_data.get("option_c", "Нет данных")
                option_d = q_data.get("option_d", "Нет данных")
                
                # Проверяем дубликат по комбинации: текст + правильный ответ + все варианты
                existing = session.query(Question).filter(
                    Question.question_text == question_text,
                    Question.theme_id == theme_id,
                    Question.correct_option == correct_option,
                    Question.option_a == option_a,
                    Question.option_b == option_b,
                    Question.option_c == option_c,
                    Question.option_d == option_d
                ).first()
                
                if existing:
                    logger.debug(f"Вопрос {idx}: уже существует в БД (полный дубликат), пропускаю")
                    stats["skipped"] += 1
                    continue
                
                # Создаем новый вопрос
                question = Question(
                    theme_id=theme_id,
                    question_text=q_data.get("question_text", ""),
                    option_a=q_data.get("option_a", ""),
                    option_b=q_data.get("option_b", ""),
                    option_c=q_data.get("option_c", "Нет данных"),
                    option_d=q_data.get("option_d", "Нет данных"),
                    correct_option=q_data.get("correct_option", "A"),
                    difficulty=q_data.get("difficulty", "medium"),
                    source_type=q_data.get("source_type", "ai"),
                    is_approved=True
                )
                
                session.add(question)
                stats["imported"] += 1
                
                # Коммитим каждые 50 вопросов для оптимизации
                if stats["imported"] % 50 == 0:
                    session.commit()
                    logger.info(f"Импортировано {stats['imported']} вопросов...")
                
            except Exception as e:
                logger.error(f"Ошибка при импорте вопроса {idx}: {e}", exc_info=True)
                stats["errors"] += 1
                session.rollback()
                continue
        
        # Финальный коммит
        session.commit()
    
    return stats


def main():
    """Основная функция."""
    # Определяем путь к JSON файлу
    if len(sys.argv) > 1:
        json_file = sys.argv[1]
    else:
        # По умолчанию ищем questions_data.json в корне проекта
        project_root = Path(__file__).parent.parent
        json_file = project_root / "questions_data.json"
    
    if not Path(json_file).exists():
        print(f"[ERROR] Файл не найден: {json_file}")
        print(f"Использование: python {sys.argv[0]} [путь_к_json_файлу]")
        sys.exit(1)
    
    print("="*60)
    print("ИМПОРТ ВОПРОСОВ В БАЗУ ДАННЫХ")
    print("="*60)
    print(f"Файл: {json_file}")
    print()
    
    try:
        stats = import_questions_from_json(str(json_file))
        
        print()
        print("="*60)
        print("РЕЗУЛЬТАТЫ ИМПОРТА")
        print("="*60)
        print(f"Всего вопросов в файле: {stats['total']}")
        print(f"Успешно импортировано: {stats['imported']}")
        print(f"Пропущено (дубликаты): {stats['skipped']}")
        print(f"Ошибок: {stats['errors']}")
        print(f"Создано тем: {stats['themes_created']}")
        print("="*60)
        
        if stats["imported"] > 0:
            print(f"\n[OK] Импорт завершен успешно!")
        else:
            print(f"\n[WARNING] Не было импортировано ни одного вопроса")
            if stats["skipped"] > 0:
                print(f"Возможно, все вопросы уже есть в базе данных")
        
    except Exception as e:
        logger.error(f"Критическая ошибка при импорте: {e}", exc_info=True)
        print(f"\n[ERROR] Ошибка при импорте: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
