# Инструкция по установке и запуску

## Автоматическая установка (Ubuntu/Debian)

### Быстрый старт

1. **Клонируйте репозиторий** (если еще не сделано):
```bash
git clone <repository-url>
cd trivia-bot
```

2. **Запустите скрипт установки**:
```bash
chmod +x setup.sh
./setup.sh
```

Скрипт автоматически:
- ✅ Проверит и установит зависимости (Python, PostgreSQL, Redis)
- ✅ Создаст виртуальное окружение
- ✅ Установит Python зависимости
- ✅ Настроит PostgreSQL (создаст БД и пользователя)
- ✅ Создаст таблицы в БД
- ✅ Создаст файлы для systemd сервисов
- ✅ Создаст скрипты запуска/остановки

3. **Настройте .env файл**:
```bash
nano .env
```

Обязательно укажите:
- `TELEGRAM_BOT_TOKEN` - токен вашего бота от @BotFather
- Проверьте остальные настройки (БД, Redis)

4. **Запустите бота**:

**Вариант A: Простой запуск (для разработки/тестирования)**
```bash
./start.sh
```

**Вариант B: Через systemd (для production)**
```bash
chmod +x install_systemd.sh
./install_systemd.sh
sudo systemctl start trivia-bot trivia-bot-celery-worker trivia-bot-celery-beat
```

## Ручная установка

Если автоматический скрипт не подходит, выполните шаги вручную:

### 1. Установка зависимостей системы

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv postgresql postgresql-contrib redis-server
```

### 2. Создание виртуального окружения

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Настройка PostgreSQL

```bash
sudo -u postgres psql
```

В psql выполните:
```sql
CREATE USER trivia_user WITH PASSWORD 'trivia_password';
CREATE DATABASE trivia_bot OWNER trivia_user;
GRANT ALL PRIVILEGES ON DATABASE trivia_bot TO trivia_user;
\q
```

### 4. Настройка Redis

```bash
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

### 5. Создание .env файла

```bash
cp .env.example .env
nano .env
```

### 6. Создание таблиц БД

```bash
source venv/bin/activate
python3 -c "from database.session import get_db_session; get_db_session().create_tables()"
```

### 7. Запуск

**Запуск бота:**
```bash
source venv/bin/activate
python main.py
```

**Запуск Celery worker (в отдельном терминале):**
```bash
source venv/bin/activate
celery -A tasks.celery_app worker --loglevel=info
```

**Запуск Celery beat (в отдельном терминале):**
```bash
source venv/bin/activate
celery -A tasks.celery_app beat --loglevel=info
```

## Управление через systemd

### Установка сервисов

```bash
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable trivia-bot trivia-bot-celery-worker trivia-bot-celery-beat
```

### Управление сервисами

```bash
# Запуск
sudo systemctl start trivia-bot
sudo systemctl start trivia-bot-celery-worker
sudo systemctl start trivia-bot-celery-beat

# Остановка
sudo systemctl stop trivia-bot
sudo systemctl stop trivia-bot-celery-worker
sudo systemctl stop trivia-bot-celery-beat

# Статус
sudo systemctl status trivia-bot

# Логи
sudo journalctl -u trivia-bot -f
sudo journalctl -u trivia-bot-celery-worker -f
sudo journalctl -u trivia-bot-celery-beat -f
```

## Проверка работы

1. **Проверьте логи:**
```bash
tail -f logs/trivia_bot.log
```

2. **Проверьте базу данных:**
```bash
psql -U trivia_user -d trivia_bot -c "\dt"
```

3. **Проверьте Redis:**
```bash
redis-cli ping
# Должен вернуть: PONG
```

4. **Проверьте Celery:**
```bash
celery -A tasks.celery_app inspect active
```

## Устранение проблем

### Проблема: PostgreSQL не запускается
```bash
sudo systemctl status postgresql
sudo systemctl start postgresql
```

### Проблема: Redis не запускается
```bash
sudo systemctl status redis-server
sudo systemctl start redis-server
```

### Проблема: Ошибка подключения к БД
- Проверьте DATABASE_URL в .env
- Убедитесь, что PostgreSQL запущен
- Проверьте права пользователя БД

### Проблема: Бот не отвечает
- Проверьте TELEGRAM_BOT_TOKEN в .env
- Проверьте логи: `tail -f logs/trivia_bot.log`
- Убедитесь, что все сервисы запущены

## Остановка всех сервисов

```bash
./stop.sh
```

Или через systemd:
```bash
sudo systemctl stop trivia-bot trivia-bot-celery-worker trivia-bot-celery-beat
```
