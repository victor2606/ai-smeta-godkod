# Docker Build & Publish - Quick Reference

Краткая инструкция по сборке и публикации Docker образа в публичный registry.

## 🎯 Главное

**База данных и Excel файлы НЕ включаются в образ!**

Пользователи будут монтировать `estimates.db` как volume при запуске контейнера.

---

## 📦 Что включено в образ

✅ **Включено:**
- Python код (`src/`, `mcp_server.py`, `health_server.py`)
- Python зависимости (`requirements.txt`)
- Структура директорий (`data/processed/`, `data/logs/`)

❌ **НЕ включено (исключено в .dockerignore):**
- `data/processed/estimates.db` (основная БД)
- `data/raw/*.xlsx` (исходные Excel файлы)
- `data/logs/*.log` (логи)
- `data/cache/` (кэш)
- Все бэкапы БД

---

## 🚀 Локальная сборка и тестирование

### Шаг 1: Сборка образа

```bash
# Простая сборка
./build.sh

# Сборка с тестами (проверит что БД не попала в образ)
./build.sh --test

# Сборка для нескольких платформ (amd64 + arm64)
./build.sh --multi
```

### Шаг 2: Проверка что БД не в образе

```bash
# Запустить контейнер и проверить
docker run --rm ghcr.io/victor2606/construction-estimator-mcp:latest sh -c "
  if [ -f /app/data/processed/estimates.db ]; then
    echo '❌ ERROR: Database in image!'
    exit 1
  else
    echo '✅ OK: Database NOT in image'
  fi
"
```

### Шаг 3: Тестовый запуск с БД

```bash
# Запустить с монтированной БД
docker run -d \
  --name mcp-test \
  -p 8002:8000 \
  -v $(pwd)/data/processed/estimates.db:/app/data/processed/estimates.db:ro \
  ghcr.io/victor2606/construction-estimator-mcp:latest

# Проверить health
curl http://localhost:8002/health

# Проверить логи
docker logs mcp-test

# Остановить
docker stop mcp-test && docker rm mcp-test
```

---

## 📤 Публикация в GitHub Container Registry

### Вариант 1: GitHub Actions (автоматически)

**Триггеры:**
- Push в `main` → билдит и публикует `latest`
- Push тега `v*.*.*` → билдит и публикует версию
- Pull request → только билдит (не публикует)

```bash
# Опубликовать новую версию
git tag v1.0.0
git push origin v1.0.0

# GitHub Actions автоматически:
# 1. Соберёт образ
# 2. Проверит что БД не включена
# 3. Опубликует в ghcr.io/victor2606/construction-estimator-mcp:v1.0.0
# 4. Создаст GitHub Release
```

### Вариант 2: Ручная публикация

```bash
# 1. Логин в GitHub Container Registry
echo $GITHUB_TOKEN | docker login ghcr.io -u victor2606 --password-stdin

# 2. Сборка и публикация
./build.sh --multi --push

# Или через docker напрямую
docker build -t ghcr.io/victor2606/construction-estimator-mcp:latest .
docker push ghcr.io/victor2606/construction-estimator-mcp:latest
```

### Получение GitHub Token

```bash
# 1. Перейти: https://github.com/settings/tokens
# 2. Создать Personal Access Token (Classic)
# 3. Выбрать scope: write:packages, read:packages
# 4. Сохранить токен

# Использовать:
export GITHUB_TOKEN=ghp_your_token_here
```

---

## 🔍 Верификация после публикации

### Проверка что образ опубликован

```bash
# Список тегов
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/users/victor2606/packages/container/construction-estimator-mcp/versions

# Или через web:
# https://github.com/victor2606?tab=packages
```

### Тест скачивания и запуска

```bash
# На чистой машине (или в другой директории)
mkdir test-deployment && cd test-deployment

# Скачать образ
docker pull ghcr.io/victor2606/construction-estimator-mcp:latest

# Запустить БЕЗ БД (должен упасть с ошибкой)
docker run --rm ghcr.io/victor2606/construction-estimator-mcp:latest
# Ожидаемая ошибка: "Database file not found: /app/data/processed/estimates.db"

# Запустить С БД (должен работать)
docker run -d \
  -p 8002:8000 \
  -v /path/to/estimates.db:/app/data/processed/estimates.db:ro \
  ghcr.io/victor2606/construction-estimator-mcp:latest

# Проверить
curl http://localhost:8002/health
```

---

## 👥 Инструкции для пользователей

### Что дать пользователям:

1. **Docker образ** (публичный):
   ```
   ghcr.io/victor2606/construction-estimator-mcp:latest
   ```

2. **Файл базы данных** (приватно, через безопасный канал):
   ```
   estimates.db (~150MB)
   ```

3. **Документация**:
   - `DEPLOYMENT_GUIDE.md` - полная инструкция по развертыванию
   - `docker-compose.yml` - готовый конфиг для запуска

### Пример инструкции для пользователя:

```markdown
# Быстрый старт

1. Получите файл `estimates.db` от администратора проекта
2. Создайте структуру директорий:
   ```bash
   mkdir -p construction-estimator/data/processed
   cp estimates.db construction-estimator/data/processed/
   cd construction-estimator
   ```

3. Создайте `docker-compose.yml`:
   ```yaml
   version: '3.8'
   services:
     mcp-server:
       image: ghcr.io/victor2606/construction-estimator-mcp:latest
       ports:
         - "8002:8000"
       volumes:
         - ./data/processed/estimates.db:/app/data/processed/estimates.db:ro
   ```

4. Запустите:
   ```bash
   docker-compose up -d
   curl http://localhost:8002/health
   ```
```

---

## 🔐 Безопасность

### Передача базы данных пользователям

❌ **НЕ передавать через:**
- Публичные GitHub репозитории
- Email (незащищённый)
- Общедоступные облачные хранилища
- Telegram/WhatsApp (без шифрования)

✅ **Передавать через:**
- Приватные каналы Slack/Teams
- Зашифрованные архивы (7z с паролем)
- Приватное облако с ограниченным доступом
- Прямая передача через VPN/SSH

### Пример зашифрованной передачи:

```bash
# Упаковать и зашифровать
7z a -p -mhe=on estimates.7z data/processed/estimates.db
# Будет запрошен пароль

# Передать пользователю:
# - estimates.7z (файл)
# - Пароль (через отдельный канал)

# Пользователь распаковывает:
7z x estimates.7z
# Вводит пароль
```

---

## 📊 Размеры образа

```bash
# Проверить размер образа
docker images ghcr.io/victor2606/construction-estimator-mcp

# Ожидаемые размеры:
# БЕЗ базы: ~150-200 MB
# С базой (если бы включили): ~300-350 MB
```

**Преимущество разделения:**
- Образ меньше → быстрее скачивается
- Обновление кода не требует передачи БД заново
- Пользователи могут обновлять БД независимо от кода

---

## 🔄 Обновление образа

### Обновление кода (без изменений БД)

```bash
# 1. Внести изменения в код
# 2. Закоммитить
git add .
git commit -m "feat: add new feature"
git push

# 3. Создать тег версии
git tag v1.1.0
git push origin v1.1.0

# 4. GitHub Actions автоматически:
#    - Соберёт новый образ
#    - Опубликует с тегом v1.1.0 и latest
```

**Пользователи обновятся:**
```bash
docker-compose pull
docker-compose up -d
```

### Обновление структуры БД (breaking change)

Если меняется схема БД:

1. Обновить версию в коде
2. Создать миграционный скрипт
3. Предоставить новую версию БД пользователям
4. Обновить `DEPLOYMENT_GUIDE.md` с инструкциями по миграции

---

## 🐛 Troubleshooting

### Образ слишком большой

```bash
# Проверить размер
docker images ghcr.io/victor2606/construction-estimator-mcp

# Если > 250MB, проверить что попало в образ:
docker run --rm ghcr.io/victor2606/construction-estimator-mcp:latest du -sh /app/*
```

### БД случайно попала в образ

```bash
# Проверить
docker run --rm ghcr.io/victor2606/construction-estimator-mcp:latest ls -lh /app/data/processed/

# Если есть estimates.db:
# 1. Проверить .dockerignore
# 2. Пересобрать образ
# 3. НЕ публиковать этот образ!
```

### GitHub Actions не публикует образ

```bash
# Проверить логи workflow:
# https://github.com/victor2606/n8npiplines-bim/actions

# Возможные причины:
# - Нет прав packages:write
# - Не залогинен в ghcr.io
# - Ошибка сборки
```

---

## 📝 Checklist перед публикацией

- [ ] `.dockerignore` содержит паттерны исключения БД
- [ ] `Dockerfile` НЕ копирует `data/` целиком
- [ ] `./build.sh --test` проходит успешно
- [ ] Образ собирается без ошибок
- [ ] БД НЕ обнаружена в собранном образе
- [ ] `docker-compose.yml` содержит volume mount для БД
- [ ] `DEPLOYMENT_GUIDE.md` актуален
- [ ] GitHub Actions workflow настроен
- [ ] Версия в git tag соответствует релизу

---

## 📚 Дополнительные ресурсы

- [GitHub Container Registry Docs](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [Docker Multi-platform Builds](https://docs.docker.com/build/building/multi-platform/)
- [Best practices for writing Dockerfiles](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)

---

## 💡 Полезные команды

```bash
# Проверить что в образе
docker run --rm ghcr.io/victor2606/construction-estimator-mcp:latest ls -laR /app/data/

# Размер слоёв образа
docker history ghcr.io/victor2606/construction-estimator-mcp:latest

# Информация об образе
docker inspect ghcr.io/victor2606/construction-estimator-mcp:latest

# Удалить все старые версии локально
docker images | grep construction-estimator-mcp | awk '{print $3}' | xargs docker rmi -f

# Логи контейнера в реальном времени
docker logs -f construction-estimator-mcp
```

---

Готово! Теперь вы можете безопасно публиковать образ без базы данных.
