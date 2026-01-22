# Скрипты для тестирования

## Доступные скрипты

### `create_tables.py`
Создает все таблицы в базе данных.

```bash
python scripts/create_tables.py
```

### `add_test_data.py`
Добавляет тестовые данные:
- 5 тем (Кино, Наука, Спорт, География, История)
- 12+ тестовых вопросов
- 10 ботов (разных уровней сложности)

```bash
python scripts/add_test_data.py
```

### `check_status.py`
Проверяет текущий статус системы:
- Количество пользователей, ботов
- Количество вопросов, тем
- Активные игры
- Активные пулы

```bash
python scripts/check_status.py
```

### `create_test_game.py`
Создает тестовую игру с ботами для быстрого тестирования.

```bash
# Создать тренировочную игру
python scripts/create_test_game.py --telegram-id YOUR_TELEGRAM_ID

# Создать игру с 5 игроками (1 реальный + 4 бота)
python scripts/create_test_game.py --telegram-id YOUR_TELEGRAM_ID --players 5
```

### `test_quick_game.py`
Вручную запускает проверку пула (для тестирования быстрой игры).

```bash
python scripts/test_quick_game.py
```

## Порядок использования

1. **Первая настройка:**
   ```bash
   python scripts/create_tables.py
   python scripts/add_test_data.py
   ```

2. **Проверка статуса:**
   ```bash
   python scripts/check_status.py
   ```

3. **Создание тестовой игры:**
   ```bash
   python scripts/create_test_game.py --telegram-id YOUR_ID
   ```

4. **Тестирование быстрой игры:**
   ```bash
   # Добавьте игроков через бота, затем:
   python scripts/test_quick_game.py
   ```
