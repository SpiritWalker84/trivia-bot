# Инструкция по отладке проверки ответов

## Где находятся логи

1. **Файл логов приложения:**
   ```bash
   ~/trivia-bot/logs/trivia_bot.log
   ```

2. **Логи systemd сервиса:**
   ```bash
   sudo journalctl -u trivia-bot -f
   ```

## Как посмотреть логи

### Вариант 1: Использовать скрипт
```bash
cd ~/trivia-bot
bash scripts/view_logs.sh
# Выберите опцию 7 - "Search for shuffled options / answer checking"
```

### Вариант 2: Вручную
```bash
# Посмотреть последние логи с проверкой ответов
tail -n 200 ~/trivia-bot/logs/trivia_bot.log | grep -i "Answer is\|Using.*correct option\|Shuffl"

# Или посмотреть все логи в реальном времени
tail -f ~/trivia-bot/logs/trivia_bot.log | grep -i "Answer is\|Using.*correct option\|Shuffl"
```

### Вариант 3: Systemd логи
```bash
# Посмотреть логи systemd
sudo journalctl -u trivia-bot -n 200 | grep -i "Answer is\|Using.*correct option\|Shuffl"

# Или в реальном времени
sudo journalctl -u trivia-bot -f | grep -i "Answer is\|Using.*correct option\|Shuffl"
```

## Что искать в логах

При проверке ответа должны быть строки:
```
DEBUG - Shuffling question X: original correct=B, available=['A', 'B', 'C', 'D']
DEBUG - After shuffle: [('C', ...), ('B', ...), ('A', ...), ('D', ...)]
DEBUG - Shuffled mapping: {'A': 'C', 'B': 'B', 'C': 'A', 'D': 'D'}
DEBUG - Correct option after shuffle: B (was B)
DEBUG - Using shuffled correct option: B (original was B)
DEBUG - Shuffled mapping: {'A': 'C', 'B': 'B', 'C': 'A', 'D': 'D'}
DEBUG - Answer check: selected=B, correct=B
INFO - Answer is CORRECT: user selected B, correct was B
```

Или для старых вопросов (без перемешивания):
```
DEBUG - Using original correct option: B (shuffled_options=False, correct_option_shuffled=None)
DEBUG - Answer check: selected=B, correct=B
INFO - Answer is CORRECT: user selected B, correct was B
```

## Возможные проблемы

1. **Варианты не перемешиваются визуально:**
   - Проверьте, что `shuffled_options` не NULL в базе
   - Проверьте логику отображения в `bot/game_notifications.py`

2. **Правильные ответы засчитываются как неправильные:**
   - Проверьте логи - какой `correct_option` используется
   - Проверьте, что `shuffled_options` и `correct_option_shuffled` установлены правильно

3. **Для старых вопросов:**
   - Если `shuffled_options` = NULL, используется оригинальный `correct_option`
   - Это должно работать правильно

## Проверка в базе данных

```sql
-- Проверить перемешивание для конкретного вопроса
SELECT 
    rq.id,
    rq.shuffled_options,
    rq.correct_option_shuffled,
    q.correct_option as original_correct
FROM round_questions rq
JOIN questions q ON q.id = rq.question_id
WHERE rq.id = <round_question_id>;
```

## Включение DEBUG логирования

Если нужно больше логов, измените в `.env`:
```
LOG_LEVEL=DEBUG
```

Затем перезапустите бота:
```bash
sudo systemctl restart trivia-bot
```
