# Источники вопросов для викторины

## Рекомендуемые источники на GitHub

### 1. Open Trivia Database
- **Репозиторий**: https://github.com/opentdb/opentdb
- **Описание**: Открытая база данных вопросов викторины
- **Формат**: API, но можно экспортировать в JSON
- **Количество**: Тысячи вопросов на разных языках
- **Использование**: Можно использовать API или экспортировать данные

### 2. Trivia Questions Datasets
Поиск на GitHub:
- `trivia questions dataset json`
- `quiz questions database`
- `question bank json`
- `trivia questions russian` (для русскоязычных вопросов)

### 3. Kaggle Datasets
- **Сайт**: https://www.kaggle.com/datasets
- **Поиск**: "trivia questions", "quiz questions"
- **Формат**: CSV, JSON
- **Количество**: Множество датасетов с тысячами вопросов

### 4. Создание собственного скрипта импорта

Можно создать скрипт для импорта вопросов из различных источников:

```python
# scripts/import_questions.py
# Пример скрипта для импорта вопросов из JSON файла
```

## Формат вопросов для импорта

Вопросы должны быть в формате:
```json
{
  "question_text": "Текст вопроса",
  "option_a": "Вариант A",
  "option_b": "Вариант B",
  "option_c": "Вариант C",
  "option_d": "Вариант D",
  "correct_option": "A",
  "difficulty": "medium",
  "theme_id": 1
}
```

## Полезные ссылки

1. **Open Trivia Database API**: https://opentdb.com/
2. **GitHub Search**: https://github.com/search?q=trivia+questions+dataset
3. **Kaggle**: https://www.kaggle.com/datasets?search=trivia

## Примечания

- Большинство датасетов на английском языке
- Для русскоязычных вопросов может потребоваться ручной перевод или поиск русскоязычных датасетов
- Рекомендуется проверять качество вопросов перед импортом
- Можно комбинировать несколько источников для достижения нужного количества
