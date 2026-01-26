# Руководство по просмотру логов

## Где находятся логи

1. **Основной лог бота**: `logs/trivia_bot.log`
2. **Лог Celery worker**: `logs/celery_worker.log` (если настроен)
3. **Лог Celery beat**: `logs/celery_beat.log` (если настроен)

## Быстрый просмотр через скрипт

```bash
cd ~/trivia-bot
./scripts/view_logs.sh
```

Выберите опцию **8** для поиска ошибок последовательности вопросов.

## Ручной просмотр логов

### 1. Просмотр последних записей

```bash
# Последние 100 строк
tail -n 100 logs/trivia_bot.log

# Последние 500 строк
tail -n 500 logs/trivia_bot.log

# Живой просмотр (обновляется в реальном времени)
tail -f logs/trivia_bot.log
```

### 2. Поиск ошибок последовательности вопросов

```bash
# Поиск SEQUENCE ERROR
grep -i "SEQUENCE ERROR" logs/trivia_bot.log | tail -n 50

# Поиск пропущенных вопросов
grep -i "was already displayed\|skipping.*question\|Question.*was already sent" logs/trivia_bot.log | tail -n 50

# Поиск всех вызовов send_next_question
grep -i "send_next_question\|Scheduling next question" logs/trivia_bot.log | tail -n 100

# Полный контекст вокруг ошибок последовательности
grep -B 10 -A 10 -i "SEQUENCE ERROR\|was already displayed.*Skipping" logs/trivia_bot.log | tail -n 200
```

### 3. Поиск по конкретной игре

```bash
# Замените GAME_ID на ID вашей игры
grep "game_id.*GAME_ID\|Game GAME_ID" logs/trivia_bot.log | tail -n 100

# Пример для игры 123:
grep "game_id.*123\|Game 123" logs/trivia_bot.log | tail -n 100
```

### 4. Поиск по конкретному раунду

```bash
# Замените ROUND_ID на ID раунда
grep "round_id.*ROUND_ID\|Round ROUND_ID" logs/trivia_bot.log | tail -n 100

# Пример для раунда 456:
grep "round_id.*456\|Round 456" logs/trivia_bot.log | tail -n 100
```

### 5. Поиск всех ошибок

```bash
# Все ошибки
grep -i error logs/trivia_bot.log | tail -n 100

# Только критические ошибки
grep -i "ERROR\|CRITICAL" logs/trivia_bot.log | tail -n 100
```

### 6. Поиск по времени

```bash
# Логи за сегодня
grep "$(date +%Y-%m-%d)" logs/trivia_bot.log | tail -n 200

# Логи за конкретную дату (замените YYYY-MM-DD)
grep "YYYY-MM-DD" logs/trivia_bot.log | tail -n 200

# Пример для 26 января 2026:
grep "2026-01-26" logs/trivia_bot.log | tail -n 200
```

## Ключевые слова для поиска проблем с вопросами

### Ошибки последовательности:
- `SEQUENCE ERROR` - критическая ошибка последовательности
- `was already displayed` - вопрос уже был отправлен
- `skipping.*question` - вопрос пропускается
- `Question.*was already sent` - дубликат отправки вопроса

### Отправка вопросов:
- `Scheduling next question` - планирование следующего вопроса
- `send_next_question` - вызов функции отправки следующего вопроса
- `send_question_to_players` - отправка вопроса игрокам
- `Question.*sent to players` - подтверждение отправки

### Проблемы с раундами:
- `Round.*is not in_progress` - раунд не активен
- `Game.*is not in_progress` - игра не активна
- `Round.*not found` - раунд не найден

## Пример полного анализа проблемы

Если вопросы пропускаются во втором раунде:

```bash
# 1. Найти все ошибки последовательности
grep -i "SEQUENCE ERROR\|was already displayed" logs/trivia_bot.log | tail -n 50

# 2. Найти все вызовы send_next_question для второго раунда
grep -i "send_next_question.*round.*2\|Scheduling next question.*round.*2" logs/trivia_bot.log | tail -n 100

# 3. Найти все отправки вопросов для второго раунда
grep -i "Question.*sent.*round.*2\|send_question_to_players.*round" logs/trivia_bot.log | tail -n 100

# 4. Полный контекст вокруг проблемного времени (замените время)
grep -B 20 -A 20 "2026-01-26 18:4[5-7]" logs/trivia_bot.log | grep -i "question\|round\|SEQUENCE\|skipping" | tail -n 200
```

## Просмотр логов Celery

Если Celery worker пишет в отдельный файл:

```bash
# Логи Celery worker
tail -f logs/celery_worker.log

# Поиск ошибок в Celery
grep -i error logs/celery_worker.log | tail -n 50
```

## Сохранение логов для анализа

```bash
# Сохранить последние 1000 строк в файл
tail -n 1000 logs/trivia_bot.log > logs/analysis_$(date +%Y%m%d_%H%M%S).log

# Сохранить все ошибки последовательности
grep -i "SEQUENCE ERROR\|was already displayed" logs/trivia_bot.log > logs/sequence_errors_$(date +%Y%m%d_%H%M%S).log
```
