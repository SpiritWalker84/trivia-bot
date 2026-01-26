# Инструкция по деплою

## Автоматический деплой

Для автоматического обновления кода, применения миграций и перезапуска сервисов используйте скрипт `deploy.sh`:

```bash
cd /path/to/trivia-bot
chmod +x scripts/deploy.sh
bash scripts/deploy.sh
```

Скрипт автоматически выполнит:

1. ✅ **Создание резервной копии** текущего состояния
2. ✅ **Обновление кода** из git (если доступен)
3. ✅ **Активация виртуального окружения**
4. ✅ **Установка/обновление зависимостей** из requirements.txt
5. ✅ **Применение миграций базы данных** из `database/migrations/`
6. ✅ **Обновление `tasks/bot_answers.py`** для поддержки перемешанных вариантов (если нужно)
7. ✅ **Перезапуск сервисов** (systemd или вручную)

## Что делает скрипт

### Обновление кода
- Выполняет `git pull origin main` (если доступен git)
- Если git недоступен или не настроен, продолжает работу с текущим кодом

### Миграции базы данных
- Автоматически находит все файлы миграций в `database/migrations/`
- Применяет их по порядку
- Если миграция уже применена, пропускает её

### Обновление bot_answers.py
- Проверяет, обновлен ли файл для поддержки `shuffled_options`
- Если нет, автоматически обновляет его через скрипт `fix_bot_answers.py`
- Сохраняет резервную копию перед изменением

### Перезапуск сервисов
- Если используются systemd сервисы, перезапускает их автоматически
- Если systemd не используется, выводит инструкции для ручного перезапуска

## Ручной деплой (если скрипт не работает)

Если по какой-то причине скрипт не работает, выполните шаги вручную:

```bash
# 1. Обновить код
git pull origin main

# 2. Активировать виртуальное окружение
source venv/bin/activate

# 3. Обновить зависимости
pip install --upgrade pip
pip install -r requirements.txt

# 4. Применить миграции
python database/migrations/003_add_shuffled_options_to_round_questions.py

# 5. Обновить bot_answers.py (если нужно)
python scripts/fix_bot_answers.py

# 6. Перезапустить сервисы
sudo systemctl restart trivia-bot
sudo systemctl restart trivia-bot-celery-worker
sudo systemctl restart trivia-bot-celery-beat
```

## Проверка после деплоя

После деплоя проверьте:

1. **Статус сервисов:**
   ```bash
   sudo systemctl status trivia-bot
   sudo systemctl status trivia-bot-celery-worker
   sudo systemctl status trivia-bot-celery-beat
   ```

2. **Логи:**
   ```bash
   sudo journalctl -u trivia-bot -f
   sudo journalctl -u trivia-bot-celery-worker -f
   ```

3. **Тест бота:**
   - Отправьте команду `/start` боту
   - Создайте тестовую игру
   - Проверьте, что варианты ответов перемешиваются

## Откат изменений

Если что-то пошло не так, резервные копии сохраняются в:
```
backups/YYYYMMDD_HHMMSS/
```

Можно восстановить файлы из резервной копии:
```bash
cp backups/YYYYMMDD_HHMMSS/bot_answers.py tasks/bot_answers.py
```
