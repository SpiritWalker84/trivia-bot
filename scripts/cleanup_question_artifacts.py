#!/usr/bin/env python3
"""
Скрипт для очистки базы данных от артефактов в вопросах:
1. Удаляет из вариантов ответов текст вида "ChatGPT & DeepSeek [дата]"
2. Убирает номера перед вопросами (например, "75. Какое животное...")
"""
import sys
import os
import re
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.session import db_session
from database.models import Question
from utils.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def clean_telegram_artifact(text: str) -> str:
    """
    Удаляет артефакты копирования из Telegram вида "ChatGPT & DeepSeek [28.01.2026 11:11]"
    и "ChatGPT & DeepSeek ♥️"
    
    Args:
        text: Текст для очистки
        
    Returns:
        Очищенный текст
    """
    if not text:
        return text
    
    # Паттерны для удаления артефактов копирования из Telegram:
    # 1. "ChatGPT & DeepSeek [дата время]" - может быть в любом месте строки
    # 2. "[дата время]" в конце строки (артефакт копирования)
    # 3. "ChatGPT & DeepSeek ♥️" или с другими эмодзи
    # 4. Различные варианты форматирования даты
    
    patterns = [
        # ChatGPT & DeepSeek [28.01.2026 11:11] или ChatGPT&DeepSeek [28.01.2026 11:11]
        r'ChatGPT\s*&\s*DeepSeek\s*\[\d{1,2}\.\d{1,2}\.\d{4}\s+\d{1,2}:\d{2}\]',
        # Просто дата в квадратных скобках в конце строки [28.01.2026 11:11]
        r'\[\d{1,2}\.\d{1,2}\.\d{4}\s+\d{1,2}:\d{2}\]\s*$',
        # Вариант с пробелами вокруг & и разными форматами даты
        r'ChatGPT\s*[&]\s*DeepSeek\s*\[.*?\]',
        # Любой текст в квадратных скобках с датой в конце строки
        r'\s*\[.*?\d{1,2}\.\d{1,2}\.\d{4}.*?\]\s*$',
        # ChatGPT & DeepSeek с эмодзи (♥️, ❤️, и т.д.) - может быть в любом месте
        r'ChatGPT\s*&\s*DeepSeek\s*[♥❤💚💙💜💛🧡🤍🖤🤎\s]*',
        # ChatGPT & DeepSeek в конце строки (без даты, но с эмодзи или без)
        r'\s*ChatGPT\s*&\s*DeepSeek\s*[^\w\s]*\s*$',
        # ChatGPT & DeepSeek в конце строки с любыми символами после
        r'\s*ChatGPT\s*&\s*DeepSeek.*?$',
    ]
    
    cleaned = text
    for pattern in patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    
    # Убираем лишние пробелы в конце и начале
    cleaned = cleaned.strip()
    
    return cleaned


def clean_option_letter_prefix(text: str) -> str:
    """
    Убирает буквы A), B), C), D) или А), Б), В), Г) из начала варианта ответа.
    
    Args:
        text: Текст варианта ответа
        
    Returns:
        Очищенный текст
    """
    if not text:
        return text
    
    # Паттерн для удаления букв A), B), C), D) или А), Б), В), Г) в начале строки
    # Может быть с точкой или скобкой, с пробелом или без после
    # Примеры: "A)", "A. ", "А)", "Б. " и т.д.
    patterns = [
        r'^[A-DА-Г][\.\)]\s*',  # A), A., А), А.
        r'^[A-DА-Г]\s+',  # A , А  (с пробелом)
    ]
    
    cleaned = text
    for pattern in patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    
    # Убираем лишние пробелы в начале
    cleaned = cleaned.lstrip()
    
    return cleaned


def clean_question_number(text: str) -> str:
    """
    Убирает номер перед вопросом (например, "75. Какое животное..." -> "Какое животное...")
    
    Args:
        text: Текст вопроса
        
    Returns:
        Очищенный текст вопроса
    """
    if not text:
        return text
    
    # Паттерн: число с точкой в начале строки (например, "75. ", "1. ", "123. ")
    # Может быть с пробелом или без после точки
    pattern = r'^\d+\.\s*'
    
    cleaned = re.sub(pattern, '', text)
    
    return cleaned


def cleanup_questions(dry_run: bool = False) -> dict:
    """
    Очищает вопросы от артефактов.
    
    Args:
        dry_run: Если True, только показывает что будет изменено, не сохраняет
        
    Returns:
        Словарь со статистикой очистки
    """
    stats = {
        "total_checked": 0,
        "questions_updated": 0,
        "options_cleaned": 0,
        "option_letters_removed": 0,
        "question_numbers_removed": 0,
        "errors": 0
    }
    
    with db_session() as session:
        # Получаем все вопросы
        questions = session.query(Question).all()
        stats["total_checked"] = len(questions)
        
        logger.info(f"Проверяю {stats['total_checked']} вопросов...")
        
        for question in questions:
            try:
                updated = False
                
                # Очищаем варианты ответов от артефактов Telegram
                original_options = {
                    'a': question.option_a,
                    'b': question.option_b,
                    'c': question.option_c,
                    'd': question.option_d
                }
                
                # Сначала очищаем от артефактов Telegram, затем убираем буквы A), B), C), D)
                cleaned_a = clean_telegram_artifact(question.option_a or '')
                cleaned_b = clean_telegram_artifact(question.option_b or '')
                cleaned_c = clean_telegram_artifact(question.option_c or '')
                cleaned_d = clean_telegram_artifact(question.option_d or '')
                
                # Убираем буквы A), B), C), D) из начала вариантов ответов
                cleaned_a = clean_option_letter_prefix(cleaned_a)
                cleaned_b = clean_option_letter_prefix(cleaned_b)
                cleaned_c = clean_option_letter_prefix(cleaned_c)
                cleaned_d = clean_option_letter_prefix(cleaned_d)
                
                # Проверяем, были ли изменения в вариантах ответов
                options_changed = (
                    cleaned_a != original_options['a'] or 
                    cleaned_b != original_options['b'] or 
                    cleaned_c != original_options['c'] or 
                    cleaned_d != original_options['d']
                )
                
                if options_changed:
                    updated = True
                    stats["options_cleaned"] += 1
                    
                    # Проверяем, были ли удалены буквы A), B), C), D) из оригинальных вариантов
                    letters_removed = (
                        clean_option_letter_prefix(original_options['a']) != original_options['a'] or
                        clean_option_letter_prefix(original_options['b']) != original_options['b'] or
                        clean_option_letter_prefix(original_options['c']) != original_options['c'] or
                        clean_option_letter_prefix(original_options['d']) != original_options['d']
                    )
                    if letters_removed:
                        stats["option_letters_removed"] += 1
                    
                    if not dry_run:
                        question.option_a = cleaned_a
                        question.option_b = cleaned_b
                        question.option_c = cleaned_c
                        question.option_d = cleaned_d
                    
                    logger.debug(
                        f"Вопрос ID {question.id}: очищены варианты ответов\n"
                        f"  A: '{original_options['a']}' -> '{cleaned_a}'\n"
                        f"  B: '{original_options['b']}' -> '{cleaned_b}'\n"
                        f"  C: '{original_options['c']}' -> '{cleaned_c}'\n"
                        f"  D: '{original_options['d']}' -> '{cleaned_d}'"
                    )
                
                # Очищаем текст вопроса от номера
                original_text = question.question_text or ''
                cleaned_text = clean_question_number(original_text)
                
                if cleaned_text != original_text:
                    updated = True
                    stats["question_numbers_removed"] += 1
                    
                    if not dry_run:
                        question.question_text = cleaned_text
                    
                    logger.debug(
                        f"Вопрос ID {question.id}: удален номер из текста\n"
                        f"  Было: '{original_text}'\n"
                        f"  Стало: '{cleaned_text}'"
                    )
                
                if updated:
                    stats["questions_updated"] += 1
                    
                    if dry_run:
                        logger.info(f"[DRY RUN] Вопрос ID {question.id} будет обновлен")
                    else:
                        # Коммитим каждые 100 вопросов для оптимизации
                        if stats["questions_updated"] % 100 == 0:
                            session.commit()
                            logger.info(f"Обновлено {stats['questions_updated']} вопросов...")
                
            except Exception as e:
                logger.error(f"Ошибка при обработке вопроса ID {question.id}: {e}", exc_info=True)
                stats["errors"] += 1
                continue
        
        # Финальный коммит
        if not dry_run and stats["questions_updated"] > 0:
            session.commit()
            logger.info(f"Все изменения сохранены в базу данных")
    
    return stats


def main():
    """Основная функция."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Очистка базы данных от артефактов в вопросах"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Показать что будет изменено, но не сохранять изменения'
    )
    
    args = parser.parse_args()
    
    print("="*60)
    print("ОЧИСТКА БАЗЫ ДАННЫХ ОТ АРТЕФАКТОВ")
    print("="*60)
    if args.dry_run:
        print("[РЕЖИМ ПРОВЕРКИ] Изменения не будут сохранены")
    print()
    
    try:
        stats = cleanup_questions(dry_run=args.dry_run)
        
        print()
        print("="*60)
        print("РЕЗУЛЬТАТЫ ОЧИСТКИ")
        print("="*60)
        print(f"Всего проверено вопросов: {stats['total_checked']}")
        print(f"Вопросов обновлено: {stats['questions_updated']}")
        print(f"Вариантов ответов очищено: {stats['options_cleaned']}")
        print(f"Букв A), B), C), D) удалено: {stats['option_letters_removed']}")
        print(f"Номеров удалено из вопросов: {stats['question_numbers_removed']}")
        print(f"Ошибок: {stats['errors']}")
        print("="*60)
        
        if args.dry_run:
            print("\n[INFO] Это был режим проверки. Для применения изменений запустите:")
            print("python scripts/cleanup_question_artifacts.py")
        elif stats["questions_updated"] > 0:
            print(f"\n[OK] Очистка завершена успешно!")
        else:
            print(f"\n[INFO] Артефакты не найдены, база данных чистая")
        
    except Exception as e:
        logger.error(f"Критическая ошибка при очистке: {e}", exc_info=True)
        print(f"\n[ERROR] Ошибка при очистке: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
