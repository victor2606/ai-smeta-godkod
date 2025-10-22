# Сводка по Docker инфраструктуре

Этот документ содержит краткую сводку всех изменений для публикации Docker образа в публичный registry БЕЗ базы данных.

---

## ✅ Что было сделано

### 1. Создан production Dockerfile (`Dockerfile`)

**Ключевые особенности:**
- ❌ НЕ копирует `data/` директорию в образ
- ✅ Создаёт только структуру директорий
- ✅ Multi-stage build для минимального размера
- ✅ Non-root пользователь (безопасность)
- ✅ Health check встроен

**Что НЕ включено в образ:**
- `data/processed/estimates.db` (база данных)
- `data/raw/*.xlsx` (Excel файлы)
- `data/logs/` (логи)
- `data/cache/` (кэш)
- Любые бэкапы БД

### 2. Обновлён .dockerignore

Добавлены критические исключения:
```
data/processed/estimates.db
data/processed/estimates_backup_*.db
data/raw/*.xlsx
data/cache/
```

Гарантирует, что БД **никогда** не попадёт в Docker образ.

### 3. Создан production docker-compose.yml

**Особенности:**
- Использует образ из registry: `ghcr.io/victor2606/construction-estimator-mcp:latest`
- БД монтируется как read-only volume: `:ro`
- Порты: 8002 (MCP), 8003 (health)
- Health check включён

### 4. GitHub Actions workflow (`.github/workflows/docker-publish.yml`)

**Автоматизация:**
- Сборка при push в `main`
- Публикация при создании тега `v*.*.*`
- Проверка, что БД НЕ в образе
- Multi-platform build (amd64 + arm64)
- Автоматическое создание GitHub Release

**Триггеры:**
```bash
# Push в main → билдит latest
git push origin main

# Создание тега → билдит версию + latest
git tag v1.0.0
git push origin v1.0.0
```

### 5. Build скрипт (`build.sh`)

Локальная сборка с проверками:
```bash
./build.sh              # Простая сборка
./build.sh --test       # С проверкой что БД не в образе
./build.sh --multi      # Multi-platform
./build.sh --push       # Публикация в registry
```

### 6. Документация

Созданные файлы:
- `DEPLOYMENT_GUIDE.md` - Полное руководство для пользователей
- `DOCKER_BUILD_PUBLISH.md` - Инструкции по сборке и публикации
- `FIRST_TIME_SETUP.md` - Пошаговая инструкция для новых пользователей
- `README_DOCKER.md` - Краткий обзор
- `DOCKER_SUMMARY.md` - Этот файл

---

## 🚀 Как публиковать в registry

### Вариант 1: Автоматически через GitHub Actions (рекомендуется)

```bash
# 1. Закоммитить изменения
git add .
git commit -m "feat: add new feature"
git push origin main

# 2. Создать тег версии
git tag v1.0.0
git push origin v1.0.0

# 3. GitHub Actions автоматически:
#    - Соберёт образ
#    - Проверит что БД не включена
#    - Опубликует в ghcr.io/victor2606/construction-estimator-mcp
#    - Создаст GitHub Release
```

### Вариант 2: Ручная публикация

```bash
# 1. Логин в GitHub Container Registry
echo $GITHUB_TOKEN | docker login ghcr.io -u victor2606 --password-stdin

# 2. Сборка и публикация
./build.sh --multi --push

# Готово!
```

---

## 📦 Что получает пользователь

### 1. Docker образ (публичный)

```bash
docker pull ghcr.io/victor2606/construction-estimator-mcp:latest
```

**Размер:** ~150-200 MB (БЕЗ базы данных)

**Содержимое:**
- Python 3.10
- FastMCP сервер
- 5 инструментов (natural_search, quick_calculate, etc.)
- Структура директорий для монтирования БД

### 2. Файл базы данных (ОТДЕЛЬНО, приватно!)

**Файл:** `estimates.db`
**Размер:** ~150 MB
**Как передать:**
- ❌ НЕ через GitHub
- ❌ НЕ через публичные каналы
- ✅ Зашифрованный архив
- ✅ Приватное облако
- ✅ Прямая передача

### 3. Документация

Предоставить пользователю:
- `docker-compose.yml`
- `FIRST_TIME_SETUP.md`
- `DEPLOYMENT_GUIDE.md`

---

## 🔒 Безопасность

### ✅ Что безопасно

1. **Публикация образа в ghcr.io** - БД не включена
2. **Открытый исходный код** - не содержит конфиденциальных данных
3. **GitHub Actions** - проверяет отсутствие БД перед публикацией

### ⚠️ Что нужно защищать

1. **estimates.db** - НИКОГДА не коммитить в Git
2. **Excel файлы** - источник данных, приватный
3. **Бэкапы БД** - хранить в безопасном месте

### 🛡️ Меры защиты в коде

```dockerfile
# Dockerfile НЕ копирует data/
# COPY data/ ./data/  ← Эта строка УДАЛЕНА

# Вместо этого создаёт только структуру
RUN mkdir -p /app/data/processed /app/data/logs
```

```
# .dockerignore исключает БД
data/processed/estimates.db
data/raw/*.xlsx
```

```yaml
# GitHub Actions проверяет
- name: Verify image does NOT contain database
  run: |
    if docker run --rm test:latest [ -f /app/data/processed/estimates.db ]; then
      echo "ERROR: Database in image!"
      exit 1
    fi
```

---

## 📋 Checklist перед первой публикацией

Перед тем как запустить `git push`:

- [ ] `.dockerignore` содержит паттерны исключения БД
- [ ] `Dockerfile` НЕ копирует `data/` директорию
- [ ] Локальная сборка успешна: `./build.sh --test`
- [ ] Образ проверен на отсутствие БД
- [ ] `docker-compose.yml` настроен с volume mounts
- [ ] Документация актуальна
- [ ] GitHub Actions workflow добавлен в `.github/workflows/`
- [ ] Настроен GitHub Container Registry (Packages)

**Тест перед публикацией:**
```bash
# Соберите локально
./build.sh --test

# Проверьте размер
docker images | grep construction-estimator-mcp
# Должно быть ~150-200 MB (НЕ 300+ MB)

# Проверьте что БД не в образе
docker run --rm ghcr.io/victor2606/construction-estimator-mcp:latest \
  sh -c "ls -la /app/data/processed/"
# НЕ должно быть estimates.db
```

---

## 🔄 Workflow для обновлений

### Обновление кода (без изменения БД)

```bash
# 1. Внести изменения
vim src/search/cost_calculator.py

# 2. Коммит
git add .
git commit -m "fix: improve cost calculation accuracy"
git push origin main

# 3. GitHub Actions автоматически опубликует latest

# Пользователи обновятся:
docker-compose pull
docker-compose up -d
```

### Обновление с новой версией БД

```bash
# 1. Обновить код + схему БД
# 2. Создать новую БД
python -m src.etl.excel_to_sqlite

# 3. Передать новую БД пользователям ОТДЕЛЬНО
# 4. Создать новую версию образа
git tag v2.0.0
git push origin v2.0.0

# 5. Инструкция для пользователей:
#    - Остановить контейнер
#    - Заменить estimates.db
#    - Обновить образ
#    - Запустить
```

---

## 📊 Мониторинг публикации

### Проверка что образ опубликован

```bash
# Список версий в registry
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/users/victor2606/packages/container/construction-estimator-mcp/versions

# Или через web UI:
# https://github.com/victor2606?tab=packages
```

### GitHub Actions

Логи сборки:
```
https://github.com/victor2606/n8npiplines-bim/actions
```

Проверить что:
- ✅ Build успешен
- ✅ Tests прошли (БД не обнаружена)
- ✅ Image published
- ✅ GitHub Release создан (для тегов)

---

## 🐛 Типичные проблемы и решения

### Проблема: БД случайно попала в образ

**Причина:** `.dockerignore` не работает или неправильный

**Решение:**
```bash
# 1. Проверить .dockerignore
cat .dockerignore | grep estimates.db

# 2. Удалить опубликованный образ из registry
# (через GitHub Packages UI)

# 3. Пересобрать и проверить
./build.sh --test

# 4. Опубликовать заново
```

### Проблема: GitHub Actions не может опубликовать

**Причина:** Нет прав на packages:write

**Решение:**
```bash
# В настройках репозитория:
# Settings → Actions → General → Workflow permissions
# Выбрать: "Read and write permissions"
```

### Проблема: Пользователь не может запустить контейнер

**Причина:** Не понял что нужна БД

**Решение:**
- Дать чёткую инструкцию: `FIRST_TIME_SETUP.md`
- Добавить в README большое предупреждение
- В docker-compose.yml добавить комментарии

---

## 📚 Структура документации

```
n8npiplines-bim/
├── Dockerfile                          # Production Dockerfile (БЕЗ БД)
├── docker-compose.yml                  # Production compose (с volume mounts)
├── build.sh                            # Скрипт сборки
├── .dockerignore                       # Исключения (БД, Excel)
├── .github/workflows/docker-publish.yml # GitHub Actions
│
├── DOCKER_SUMMARY.md                   # Этот файл - сводка
├── FIRST_TIME_SETUP.md                 # Для новых пользователей
├── DEPLOYMENT_GUIDE.md                 # Полное руководство
├── DOCKER_BUILD_PUBLISH.md             # Для разработчиков
├── README_DOCKER.md                    # Краткий обзор
│
└── data/                               # НЕ включено в образ!
    ├── processed/
    │   └── estimates.db                # Передаётся ОТДЕЛЬНО
    └── raw/
        └── *.xlsx                      # НЕ публикуется
```

---

## 🎯 Следующие шаги

### Сейчас (перед первой публикацией):

1. **Проверить все файлы:**
   ```bash
   ls -la Dockerfile docker-compose.yml .dockerignore build.sh
   ls -la .github/workflows/docker-publish.yml
   ```

2. **Локальный тест:**
   ```bash
   ./build.sh --test
   ```

3. **Первая публикация:**
   ```bash
   git add .
   git commit -m "feat: production-ready Docker setup without database"
   git tag v1.0.0
   git push origin main
   git push origin v1.0.0
   ```

4. **Проверить публикацию:**
   - GitHub Actions успешен
   - Образ появился в Packages
   - Release создан

### После публикации:

5. **Протестировать с чистой машины:**
   ```bash
   # На другом компьютере или в новой директории
   docker pull ghcr.io/victor2606/construction-estimator-mcp:latest
   # Следовать FIRST_TIME_SETUP.md
   ```

6. **Передать пользователям:**
   - Ссылку на образ
   - Файл `estimates.db` (безопасно!)
   - Документацию (`FIRST_TIME_SETUP.md`)

---

## 📞 Контакты для поддержки

**Для пользователей:**
- Вопросы по развертыванию: см. `DEPLOYMENT_GUIDE.md`
- Проблемы с Docker: GitHub Issues

**Для разработчиков:**
- Сборка и публикация: см. `DOCKER_BUILD_PUBLISH.md`
- CI/CD: `.github/workflows/docker-publish.yml`

---

## ✨ Итого

**Готово к продакшену:**
- ✅ Docker образ БЕЗ базы данных
- ✅ Автоматическая публикация в ghcr.io
- ✅ Полная документация для пользователей
- ✅ Безопасность: БД передаётся отдельно
- ✅ Простота обновлений
- ✅ Multi-platform поддержка (amd64, arm64)

**Можно публиковать!** 🚀
