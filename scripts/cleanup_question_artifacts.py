#!/usr/bin/env python3
"""
Скрипт для очистки базы данных от артефактов в вопросах:
1. Удаляет из вариантов ответов текст вида "ChatGPT & DeepSeek [дата]"
2. Убирает номера перед вопросами (например, "75. Какое животное...")
3. Находит вопросы с одинаковым текстом, но разным порядком вариантов ответов (--find-duplicates)
4. Удаляет дубликаты вопросов (--remove-duplicates)

Использование:
  python scripts/cleanup_question_artifacts.py                      # Очистка артефактов
  python scripts/cleanup_question_artifacts.py --dry-run           # Проверка без сохранения
  python scripts/cleanup_question_artifacts.py --find-duplicates     # Поиск дубликатов
  python scripts/cleanup_question_artifacts.py --remove-duplicates # Удаление дубликатов
"""
import sys
import os
import re
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.session import db_session
from database.models import Question, RoundQuestion
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


def normalize_options(options: dict) -> set:
    """
    Нормализует варианты ответов для сравнения (убирает пробелы, приводит к нижнему регистру).
    
    Args:
        options: Словарь с вариантами ответов {'a': '...', 'b': '...', 'c': '...', 'd': '...'}
        
    Returns:
        Множество нормализованных вариантов ответов
    """
    normalized = set()
    for key in ['a', 'b', 'c', 'd']:
        value = options.get(key, '').strip().lower()
        if value and value != 'нет данных':
            normalized.add(value)
    return normalized


def find_duplicate_questions_by_text(session) -> dict:
    """
    Находит вопросы с одинаковым текстом, но разным порядком вариантов ответов.
    
    Args:
        session: SQLAlchemy session
        
    Returns:
        Словарь с информацией о дубликатах: {question_id: [list of duplicate_ids]}
    """
    from collections import defaultdict
    
    # Группируем вопросы по тексту вопроса и теме
    questions_by_text = defaultdict(list)
    
    all_questions = session.query(Question).filter(Question.is_approved == True).all()
    
    for question in all_questions:
        # Нормализуем текст вопроса для группировки
        normalized_text = (question.question_text or '').strip().lower()
        if normalized_text:
            key = (normalized_text, question.theme_id)
            questions_by_text[key].append(question)
    
    # Находим дубликаты (группы с более чем одним вопросом)
    duplicates = {}
    
    for (text, theme_id), questions in questions_by_text.items():
        if len(questions) > 1:
            # Для каждой группы проверяем, имеют ли вопросы одинаковые варианты ответов
            for i, q1 in enumerate(questions):
                options1 = normalize_options({
                    'a': q1.option_a or '',
                    'b': q1.option_b or '',
                    'c': q1.option_c or '',
                    'd': q1.option_d or ''
                })
                
                # Ищем дубликаты среди остальных вопросов в группе
                duplicate_ids = []
                for j, q2 in enumerate(questions):
                    if i != j:  # Не сравниваем вопрос с самим собой
                        options2 = normalize_options({
                            'a': q2.option_a or '',
                            'b': q2.option_b or '',
                            'c': q2.option_c or '',
                            'd': q2.option_d or ''
                        })
                        
                        # Если варианты ответов одинаковые (независимо от порядка)
                        if options1 == options2:
                            duplicate_ids.append(q2.id)
                
                if duplicate_ids:
                    # Сохраняем только если еще не добавлено
                    if q1.id not in duplicates:
                        duplicates[q1.id] = duplicate_ids
    
    return duplicates


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


def remove_duplicates(dry_run: bool = False) -> dict:
    """
    Удаляет дубликаты вопросов (помечает как неодобренные вместо физического удаления).
    Оставляет самый старый вопрос в каждой группе дубликатов.
    
    Args:
        dry_run: Если True, только показывает что будет удалено, не сохраняет
        
    Returns:
        Словарь со статистикой удаления дубликатов
    """
    
    stats = {
        "total_checked": 0,
        "duplicate_groups": 0,
        "duplicates_marked": 0,
        "duplicates_skipped": 0,  # Пропущено из-за использования в играх
        "errors": 0
    }
    
    with db_session() as session:
        # Получаем все вопросы
        questions = session.query(Question).filter(Question.is_approved == True).all()
        stats["total_checked"] = len(questions)
        
        logger.info(f"Проверяю {stats['total_checked']} вопросов на дубликаты для удаления...")
        
        # Находим дубликаты
        duplicates = find_duplicate_questions_by_text(session)
        
        # Обрабатываем найденные дубликаты
        processed_ids = set()
        
        for question_id, duplicate_ids in duplicates.items():
            if question_id in processed_ids:
                continue
            
            # Получаем основной вопрос (самый старый по ID)
            main_question = session.query(Question).filter(Question.id == question_id).first()
            if not main_question:
                continue
            
            # Получаем все дубликаты (включая основной)
            all_duplicate_ids = [question_id] + duplicate_ids
            all_duplicates = session.query(Question).filter(Question.id.in_(all_duplicate_ids)).all()
            
            # Сортируем по ID (самый старый первый)
            all_duplicates.sort(key=lambda q: q.id)
            
            # Первый вопрос - оставляем, остальные - помечаем как неодобренные
            keep_question = all_duplicates[0]
            duplicates_to_mark = all_duplicates[1:]
            
            # Помечаем все ID как обработанные
            processed_ids.update(all_duplicate_ids)
            
            stats["duplicate_groups"] += 1
            
            for dup_question in duplicates_to_mark:
                # Проверяем, используется ли вопрос в играх (RoundQuestion)
                used_in_rounds = session.query(RoundQuestion).filter(
                    RoundQuestion.question_id == dup_question.id
                ).first()
                
                if used_in_rounds:
                    # Вопрос используется в играх - пропускаем удаление
                    stats["duplicates_skipped"] += 1
                    logger.warning(
                        f"Вопрос ID {dup_question.id} используется в играх, пропускаю удаление. "
                        f"Оставляю вопрос ID {keep_question.id} как основной."
                    )
                else:
                    # Помечаем как неодобренный вместо физического удаления
                    stats["duplicates_marked"] += 1
                    
                    if not dry_run:
                        dup_question.is_approved = False
                        logger.info(
                            f"Помечен как неодобренный вопрос ID {dup_question.id} "
                            f"(дубликат вопроса ID {keep_question.id})"
                        )
                    else:
                        logger.info(
                            f"[DRY RUN] Будет помечен как неодобренный вопрос ID {dup_question.id} "
                            f"(дубликат вопроса ID {keep_question.id})"
                        )
            
            # Коммитим каждые 50 групп для оптимизации
            if not dry_run and stats["duplicates_marked"] > 0 and stats["duplicates_marked"] % 50 == 0:
                session.commit()
                logger.info(f"Помечено {stats['duplicates_marked']} дубликатов...")
        
        # Финальный коммит
        if not dry_run and stats["duplicates_marked"] > 0:
            session.commit()
            logger.info(f"Все изменения сохранены в базу данных")
    
    return stats


def find_and_report_duplicates(dry_run: bool = False) -> dict:
    """
    Находит и сообщает о дубликатах вопросов с одинаковым текстом, но разным порядком вариантов.
    
    Args:
        dry_run: Если True, только показывает что будет найдено
        
    Returns:
        Словарь со статистикой поиска дубликатов
    """
    stats = {
        "total_checked": 0,
        "duplicate_groups": 0,
        "duplicate_questions": 0,
        "duplicate_details": []
    }
    
    with db_session() as session:
        # Получаем все вопросы
        questions = session.query(Question).filter(Question.is_approved == True).all()
        stats["total_checked"] = len(questions)
        
        logger.info(f"Проверяю {stats['total_checked']} вопросов на дубликаты...")
        
        # Находим дубликаты
        duplicates = find_duplicate_questions_by_text(session)
        
        # Обрабатываем найденные дубликаты
        processed_ids = set()
        
        for question_id, duplicate_ids in duplicates.items():
            if question_id in processed_ids:
                continue
            
            # Получаем основной вопрос
            main_question = session.query(Question).filter(Question.id == question_id).first()
            if not main_question:
                continue
            
            # Получаем все дубликаты (включая основной)
            all_duplicate_ids = [question_id] + duplicate_ids
            all_duplicates = session.query(Question).filter(Question.id.in_(all_duplicate_ids)).all()
            
            # Помечаем все ID как обработанные
            processed_ids.update(all_duplicate_ids)
            
            stats["duplicate_groups"] += 1
            stats["duplicate_questions"] += len(all_duplicates) - 1  # -1 потому что один основной
            
            # Сохраняем детали для отчета
            group_info = {
                "main_id": question_id,
                "duplicate_ids": duplicate_ids,
                "question_text": main_question.question_text[:100] + "..." if len(main_question.question_text) > 100 else main_question.question_text,
                "theme_id": main_question.theme_id,
                "all_ids": all_duplicate_ids
            }
            stats["duplicate_details"].append(group_info)
            
            logger.info(
                f"Найдена группа дубликатов:\n"
                f"  Основной вопрос ID: {question_id}\n"
                f"  Дубликаты: {duplicate_ids}\n"
                f"  Текст: {group_info['question_text']}\n"
                f"  Тема ID: {main_question.theme_id}"
            )
    
    return stats


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
    parser.add_argument(
        '--find-duplicates',
        action='store_true',
        help='Найти вопросы с одинаковым текстом, но разным порядком вариантов ответов'
    )
    parser.add_argument(
        '--remove-duplicates',
        action='store_true',
        help='Удалить дубликаты (пометить как неодобренные). Оставляет самый старый вопрос в группе.'
    )
    
    args = parser.parse_args()
    
    if args.find_duplicates:
        # Режим поиска дубликатов
        print("="*60)
        print("ПОИСК ДУБЛИКАТОВ ВОПРОСОВ")
        print("="*60)
        print("Ищу вопросы с одинаковым текстом, но разным порядком вариантов ответов...")
        print()
        
        try:
            stats = find_and_report_duplicates(dry_run=args.dry_run)
            
            print()
            print("="*60)
            print("РЕЗУЛЬТАТЫ ПОИСКА ДУБЛИКАТОВ")
            print("="*60)
            print(f"Всего проверено вопросов: {stats['total_checked']}")
            print(f"Найдено групп дубликатов: {stats['duplicate_groups']}")
            print(f"Найдено дубликатов: {stats['duplicate_questions']}")
            print("="*60)
            
            if stats['duplicate_details']:
                print("\nДетали найденных дубликатов:")
                for i, group in enumerate(stats['duplicate_details'], 1):
                    print(f"\n{i}. Группа дубликатов:")
                    print(f"   Основной вопрос ID: {group['main_id']}")
                    print(f"   Дубликаты ID: {group['duplicate_ids']}")
                    print(f"   Текст: {group['question_text']}")
                    print(f"   Тема ID: {group['theme_id']}")
                    print(f"   Всего вопросов в группе: {len(group['all_ids'])}")
                
                print("\n[INFO] Для удаления дубликатов используйте:")
                print("python scripts/cleanup_question_artifacts.py --remove-duplicates")
            else:
                print("\n[INFO] Дубликаты не найдены!")
            
        except Exception as e:
            logger.error(f"Критическая ошибка при поиске дубликатов: {e}", exc_info=True)
            print(f"\n[ERROR] Ошибка при поиске дубликатов: {e}")
            sys.exit(1)
    elif args.remove_duplicates:
        # Режим удаления дубликатов
        print("="*60)
        print("УДАЛЕНИЕ ДУБЛИКАТОВ ВОПРОСОВ")
        print("="*60)
        if args.dry_run:
            print("[РЕЖИМ ПРОВЕРКИ] Изменения не будут сохранены")
        print("Помечаю дубликаты как неодобренные (is_approved=False)")
        print("Оставляю самый старый вопрос в каждой группе дубликатов")
        print()
        
        try:
            stats = remove_duplicates(dry_run=args.dry_run)
            
            print()
            print("="*60)
            print("РЕЗУЛЬТАТЫ УДАЛЕНИЯ ДУБЛИКАТОВ")
            print("="*60)
            print(f"Всего проверено вопросов: {stats['total_checked']}")
            print(f"Найдено групп дубликатов: {stats['duplicate_groups']}")
            print(f"Помечено как неодобренные: {stats['duplicates_marked']}")
            print(f"Пропущено (используются в играх): {stats['duplicates_skipped']}")
            print(f"Ошибок: {stats['errors']}")
            print("="*60)
            
            if args.dry_run:
                print("\n[INFO] Это был режим проверки. Для применения изменений запустите:")
                print("python scripts/cleanup_question_artifacts.py --remove-duplicates")
            elif stats["duplicates_marked"] > 0:
                print(f"\n[OK] Удаление дубликатов завершено успешно!")
                print(f"Помечено {stats['duplicates_marked']} дубликатов как неодобренные.")
            else:
                print(f"\n[INFO] Дубликаты не найдены или все используются в играх")
            
        except Exception as e:
            logger.error(f"Критическая ошибка при удалении дубликатов: {e}", exc_info=True)
            print(f"\n[ERROR] Ошибка при удалении дубликатов: {e}")
            sys.exit(1)
    else:
        # Режим очистки артефактов
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
