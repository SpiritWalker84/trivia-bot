# Отладка приватных игр - какие логи смотреть

## Быстрый старт

### 1. Очистите логи (чтобы смотреть только свежие):
```bash
bash scripts/clear_logs.sh
```

### 2. Запустите скрипт просмотра логов:
```bash
bash scripts/view_logs.sh
```

## Что смотреть в логах при проблеме с отправкой уведомлений:

### 1. Проверьте, что обработчик вызывается
Выберите опцию **4** (Search for user_shared events) и ищите:
- `Received user_shared update` - должно появиться, когда пользователь выбирает друга
- `Processing user_shared` - обработка выбора
- `Extracted selected_user_id` - извлеченный ID пользователя

### 2. Проверьте отправку уведомлений
Выберите опцию **5** (Search for invitation/notification sending) и ищите:
- `Attempting to send invitation to user X` - попытка отправить
- `Successfully sent invitation notification` - успешная отправка
- `Failed to send notification` - ошибка отправки

### 3. Проверьте ошибки
Выберите опцию **3** (Search for errors) и ищите:
- `Failed to send notification` - ошибки отправки
- `Could not extract user_id` - проблема с извлечением ID
- `Forbidden` или `bot was blocked` - пользователь заблокировал бота

## Типичные проблемы:

### Проблема: "Could not extract user_id from user_shared"
**Решение:** Проверьте структуру объекта `user_shared` в логах. Должны быть строки:
- `user_shared.__dict__: {...}`
- `user_shared.user_id = ...`

### Проблема: "Failed to send notification: Forbidden"
**Причина:** Пользователь не начал диалог с ботом или заблокировал бота
**Решение:** Пользователь должен сначала написать боту `/start`

### Проблема: "Failed to send notification: chat not found"
**Причина:** Неверный `user_id` или пользователь не существует
**Решение:** Проверьте, что `selected_user_id` корректный

### Проблема: Нет логов вообще
**Причина:** Обработчик не вызывается
**Решение:** Проверьте, что в `main.py` правильно зарегистрирован обработчик `MessageHandler` с фильтром `filters.StatusUpdate.USERS_SHARED`

## Полезные команды для ручной проверки:

```bash
# Посмотреть последние 200 строк логов
tail -n 200 logs/trivia_bot.log

# Найти все упоминания user_shared
grep -i "user_shared" logs/trivia_bot.log | tail -n 50

# Найти все попытки отправки уведомлений
grep -i "Attempting to send invitation\|Failed to send notification" logs/trivia_bot.log | tail -n 50

# Найти все ошибки, связанные с приватными играми
grep -i "private.*error\|error.*private" logs/trivia_bot.log | tail -n 50

# Посмотреть логи в реальном времени
tail -f logs/trivia_bot.log
```

## Структура логов при успешной отправке:

```
INFO - Received user_shared update: <UserShared object>, type: <class 'telegram._message.UserShared'>
INFO - Processing user_shared: <UserShared object>, type: <class 'telegram._message.UserShared'>
INFO - user_shared.user_id = 123456789 (type: <class 'int'>)
INFO - Found user_id via user_shared.user_id: 123456789
INFO - Final extracted selected_user_id: 123456789
INFO - Attempting to send invitation to user 123456789 from creator 987654321 (Имя)
INFO - Successfully sent invitation notification to user 123456789. Message ID: 12345
```

## Структура логов при ошибке:

```
INFO - Received user_shared update: ...
INFO - Processing user_shared: ...
ERROR - Failed to send notification to user 123456789: Forbidden: bot was blocked by the user
ERROR - User 123456789 has blocked the bot or not started a conversation
```
