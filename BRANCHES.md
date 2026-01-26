# Работа с ветками и версиями

## Стабильная версия

Текущая стабильная версия помечена тегом `v1.1-stable`.

Предыдущая стабильная версия: `v1.0-stable`.

### Переключение на стабильную версию

Если нужно вернуться к стабильной версии:

```bash
# Переключиться на тег (detached HEAD)
git checkout v1.1-stable

# Или создать ветку от стабильной версии
git checkout -b stable-backup v1.1-stable

# Для возврата к предыдущей версии
git checkout v1.0-stable
```

### Создание новой ветки от стабильной версии

```bash
git checkout -b new-feature v1.1-stable
```

## Ветка разработки leaderboard

Ветка `feature/leaderboard` создана для разработки функции показа положения игроков в раунде.

### Работа в ветке feature/leaderboard

```bash
# Переключиться на ветку разработки
git checkout feature/leaderboard

# Внести изменения, закоммитить
git add .
git commit -m "Add leaderboard feature"

# Отправить изменения
git push origin feature/leaderboard
```

### Слияние в main (когда функция готова)

```bash
# Переключиться на main
git checkout main

# Обновить main
git pull origin main

# Слить feature/leaderboard в main
git merge feature/leaderboard

# Отправить изменения
git push origin main
```

### Откат к стабильной версии (если что-то пошло не так)

```bash
# Переключиться на main
git checkout main

# Откатить к стабильной версии
git reset --hard v1.1-stable

# Принудительно обновить удаленную ветку (ОСТОРОЖНО!)
git push origin main --force

# Для отката к предыдущей версии
git reset --hard v1.0-stable
```

### Просмотр всех тегов

```bash
git tag
```

### Просмотр всех веток

```bash
# Локальные ветки
git branch

# Все ветки (включая удаленные)
git branch -a
```

## Рекомендации

1. **Всегда работайте в отдельной ветке** для новых функций
2. **Тестируйте в ветке разработки** перед слиянием в main
3. **Создавайте теги** для важных версий (релизов)
4. **Не используйте `--force`** на main без крайней необходимости
