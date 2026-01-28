#!/usr/bin/env python3
"""
Скрипт для парсинга вопросов из ODT файла и подготовки их к импорту в базу данных.
"""
import sys
import os
import zipfile
import xml.etree.ElementTree as ET
import json
import re
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def extract_text_from_odt(odt_path: str) -> str:
    """
    Извлекает весь текст из ODT файла.
    
    Args:
        odt_path: Путь к ODT файлу
        
    Returns:
        Текст документа
    """
    with zipfile.ZipFile(odt_path, 'r') as z:
        content_xml = z.read('content.xml')
    
    # Парсим XML
    root = ET.fromstring(content_xml)
    
    # Находим все текстовые элементы
    # ODT использует пространство имен text для текстовых элементов
    namespaces = {
        'office': 'urn:oasis:names:tc:opendocument:xmlns:office:1.0',
        'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0',
        'table': 'urn:oasis:names:tc:opendocument:xmlns:table:1.0'
    }
    
    # Извлекаем весь текст
    text_parts = []
    for elem in root.iter():
        if elem.text and elem.text.strip():
            text_parts.append(elem.text.strip())
        if elem.tail and elem.tail.strip():
            text_parts.append(elem.tail.strip())
    
    return '\n'.join(text_parts)


def parse_questions_from_text(text: str) -> tuple[list, int]:
    """
    Парсит вопросы из текста.
    Ожидаемый формат:
    - Вопрос на отдельной строке
    - Варианты ответов (A, B, C, D) на следующих строках
    - Правильный ответ помечен как-то (например, * или ✅)
    
    Args:
        text: Текст документа
        
    Returns:
        Tuple of (список словарей с вопросами, количество пропущенных вопросов без правильного ответа)
    """
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    questions = []
    skipped_count = 0
    current_question = None
    current_options = []
    current_correct = None
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Пытаемся определить правильный ответ из строки "Правильный ответ: X"
        # Это должна быть отдельная строка после вариантов ответов
        # Используем более простое регулярное выражение для работы с кириллицей
        correct_match = re.search(r'ответ\s*[:\s]*([A-DА-Г])', line, re.IGNORECASE)
        if correct_match and not re.match(r'^([A-DА-Г])[\.\)]', line, re.IGNORECASE):
            # Это отдельная строка с правильным ответом
            correct_letter = correct_match.group(1).upper()
            # Конвертируем русские буквы в английские
            correct_mapping = {'А': 'A', 'Б': 'B', 'В': 'C', 'Г': 'D'}
            current_correct = correct_mapping.get(correct_letter, correct_letter)
            i += 1
            continue
        
        # Пытаемся определить начало вопроса
        # Вопрос обычно содержит знак вопроса или начинается с числа
        if '?' in line or (line and (line[0].isdigit() or line.startswith('Вопрос'))):
            # Сохраняем предыдущий вопрос, если есть
            # Исключаем вопросы без указанного правильного ответа
            if current_question and current_options and current_correct:
                questions.append({
                    'question_text': current_question,
                    'options': current_options,
                    'correct_option': current_correct
                })
            elif current_question and current_options and not current_correct:
                # Вопрос без правильного ответа - пропускаем
                skipped_count += 1
                print(f"  [ПРОПУЩЕН] Вопрос без правильного ответа: {current_question[:80]}...")
            
            # Начинаем новый вопрос
            current_question = line
            current_options = []
            current_correct = None
            i += 1
            continue
        
        # Пытаемся определить варианты ответов
        # Варианты обычно начинаются с A), B), C), D) или A., B., C., D.
        option_match = re.match(r'^([A-DА-Г])[\.\)]\s*(.+)$', line, re.IGNORECASE)
        if option_match:
            option_letter = option_match.group(1).upper()
            option_text = option_match.group(2).strip()
            
            # Убираем маркер правильного ответа (*, ✅, и т.д.)
            if '*' in option_text or '✅' in option_text or '✓' in option_text:
                option_text = re.sub(r'[*✅✓]', '', option_text).strip()
                # Конвертируем русские буквы в английские
                correct_mapping = {'А': 'A', 'Б': 'B', 'В': 'C', 'Г': 'D'}
                mapped_letter = correct_mapping.get(option_letter, option_letter)
                current_correct = mapped_letter
            
            current_options.append((option_letter, option_text))
            
            # После добавления варианта, проверяем следующую строку на наличие правильного ответа
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                correct_match = re.search(r'ответ\s*[:\s]*([A-DА-Г])', next_line, re.IGNORECASE)
                if correct_match:
                    correct_letter = correct_match.group(1).upper()
                    correct_mapping = {'А': 'A', 'Б': 'B', 'В': 'C', 'Г': 'D'}
                    current_correct = correct_mapping.get(correct_letter, correct_letter)
                    i += 2  # Пропускаем текущую строку и строку с правильным ответом
                    continue
            
            i += 1
            continue
        
        # Если это не вариант ответа, возможно это продолжение вопроса
        if current_question and not current_options:
            current_question += ' ' + line
        elif current_question and current_options:
            # Возможно это продолжение последнего варианта
            if current_options:
                last_letter, last_text = current_options[-1]
                current_options[-1] = (last_letter, last_text + ' ' + line)
        
        i += 1
    
    # Сохраняем последний вопрос
    # Исключаем вопросы без указанного правильного ответа
    if current_question and current_options and current_correct:
        questions.append({
            'question_text': current_question,
            'options': current_options,
            'correct_option': current_correct
        })
    elif current_question and current_options and not current_correct:
        # Вопрос без правильного ответа - пропускаем
        skipped_count += 1
        print(f"  [ПРОПУЩЕН] Последний вопрос без правильного ответа: {current_question[:80]}...")
    
    return questions, skipped_count


def convert_to_import_format(questions: list, theme_code: str = "general", theme_name: str = "Общие") -> list:
    """
    Конвертирует вопросы в формат для импорта.
    
    Args:
        questions: Список вопросов из парсера
        theme_code: Код темы
        theme_name: Название темы
        
    Returns:
        Список вопросов в формате для импорта
    """
    import_format = []
    
    for q in questions:
        options = dict(q['options'])
        
        # Убеждаемся, что есть все 4 варианта
        option_a = options.get('A', options.get('А', 'Нет данных'))
        option_b = options.get('B', options.get('Б', 'Нет данных'))
        option_c = options.get('C', options.get('В', 'Нет данных'))
        option_d = options.get('D', options.get('Г', 'Нет данных'))
        
        # Конвертируем русские буквы в английские для correct_option
        correct_mapping = {'А': 'A', 'Б': 'B', 'В': 'C', 'Г': 'D'}
        correct_option = q['correct_option']
        if correct_option in correct_mapping:
            correct_option = correct_mapping[correct_option]
        
        import_format.append({
            'theme_code': theme_code,
            'theme_name': theme_name,
            'question_text': q['question_text'],
            'option_a': option_a,
            'option_b': option_b,
            'option_c': option_c,
            'option_d': option_d,
            'correct_option': correct_option.upper(),
            'difficulty': 'medium',
            'source_type': 'manual'
        })
    
    return import_format


def main():
    """Основная функция."""
    if len(sys.argv) < 2:
        print("Использование: python scripts/parse_odt_questions.py <путь_к_odt_файлу> [theme_code] [theme_name]")
        print("Пример: python scripts/parse_odt_questions.py Quest.odt general 'Общие вопросы'")
        sys.exit(1)
    
    odt_path = sys.argv[1]
    theme_code = sys.argv[2] if len(sys.argv) > 2 else "general"
    theme_name = sys.argv[3] if len(sys.argv) > 3 else "Общие"
    
    if not Path(odt_path).exists():
        print(f"[ERROR] Файл не найден: {odt_path}")
        sys.exit(1)
    
    print(f"Парсинг файла: {odt_path}")
    print(f"Тема: {theme_name} ({theme_code})")
    print()
    
    try:
        # Извлекаем текст из ODT
        print("Извлечение текста из ODT...")
        text = extract_text_from_odt(odt_path)
        print(f"Извлечено {len(text)} символов текста")
        
        # Парсим вопросы
        print("Парсинг вопросов...")
        questions, skipped_count = parse_questions_from_text(text)
        print(f"Найдено {len(questions)} вопросов с правильными ответами")
        if skipped_count > 0:
            print(f"Пропущено {skipped_count} вопросов без указанного правильного ответа")
        
        if not questions:
            print("\n[WARNING] Вопросы не найдены!")
            print("Возможно, формат файла отличается от ожидаемого.")
            print("\nПервые 500 символов текста:")
            print(text[:500])
            sys.exit(1)
        
        # Конвертируем в формат для импорта
        print("Конвертация в формат для импорта...")
        import_format = convert_to_import_format(questions, theme_code, theme_name)
        
        # Сохраняем в JSON
        output_file = Path("questions_from_odt.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(import_format, f, ensure_ascii=False, indent=2)
        
        print(f"\n[OK] Обработано {len(import_format)} вопросов")
        if skipped_count > 0:
            print(f"[INFO] Пропущено {skipped_count} вопросов без правильного ответа")
        print(f"[FILE] Сохранено в файл: {output_file}")
        print(f"\nПримеры вопросов:")
        for i, q in enumerate(import_format[:3], 1):
            try:
                # Безопасный вывод с обработкой Unicode
                q_text = q['question_text'][:80].encode('utf-8', errors='replace').decode('utf-8')
                opt_a = q['option_a'][:50].encode('utf-8', errors='replace').decode('utf-8')
                opt_b = q['option_b'][:50].encode('utf-8', errors='replace').decode('utf-8')
                print(f"\n{i}. {q_text}...")
                print(f"   A) {opt_a}...")
                print(f"   B) {opt_b}...")
                print(f"   Правильный ответ: {q['correct_option']}")
            except Exception as e:
                # Если все равно ошибка, просто пропускаем примеры
                print(f"\n{i}. [Вопрос {i}]")
                print(f"   Правильный ответ: {q['correct_option']}")
        
        print(f"\n[INFO] Для импорта в базу данных выполните:")
        print(f"python scripts/import_questions_from_json.py {output_file}")
        
    except Exception as e:
        print(f"\n[ERROR] Ошибка при обработке файла: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
