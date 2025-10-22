# Checklist перед публикацией в Registry

Используйте этот checklist перед первой публикацией Docker образа.

## ☑️ Проверка файлов

- [ ] `Dockerfile` создан и НЕ копирует `data/`
- [ ] `docker-compose.yml` использует образ из registry
- [ ] `.dockerignore` исключает БД и Excel файлы
- [ ] `build.sh` исполняемый (`chmod +x build.sh`)
- [ ] `.github/workflows/docker-publish.yml` создан
- [ ] Документация создана (DEPLOYMENT_GUIDE.md, FIRST_TIME_SETUP.md)

## ☑️ Локальное тестирование

```bash
# Запустите каждую команду и проверьте результат
```

- [ ] Сборка успешна: `./build.sh`
- [ ] Тесты проходят: `./build.sh --test`
- [ ] Образ не содержит БД:
  ```bash
  docker run --rm ghcr.io/victor2606/construction-estimator-mcp:latest \
    ls -la /app/data/processed/ | grep estimates.db
  # Должно быть ПУСТО
  ```
- [ ] Размер образа корректный: ~150-200 MB (не 300+ MB)
  ```bash
  docker images | grep construction-estimator-mcp
  ```

## ☑️ Git и GitHub

- [ ] Все изменения закоммичены:
  ```bash
  git status
  # Должно быть: "nothing to commit, working tree clean"
  ```
- [ ] Remote repository существует:
  ```bash
  git remote -v
  # Должен быть origin → github.com/victor2606/n8npiplines-bim
  ```
- [ ] GitHub Container Registry включён в репозитории:
  - Settings → Packages (должен быть доступ)

## ☑️ Безопасность

- [ ] БД НЕ в Git истории:
  ```bash
  git log --all --full-history -- data/processed/estimates.db
  # Должно быть ПУСТО или только в .gitignore commits
  ```
- [ ] Excel файлы НЕ в Git:
  ```bash
  git log --all --full-history -- data/raw/*.xlsx
  # Должно быть ПУСТО
  ```
- [ ] `.env` файлы (если есть) в `.gitignore`

## ☑️ Первая публикация

```bash
# Выполните команды по порядку
```

- [ ] Создать тег версии:
  ```bash
  git tag v1.0.0
  git tag -l
  ```
- [ ] Push в main:
  ```bash
  git push origin main
  ```
- [ ] Push тега:
  ```bash
  git push origin v1.0.0
  ```

## ☑️ Проверка GitHub Actions

- [ ] Перейти на: https://github.com/victor2606/n8npiplines-bim/actions
- [ ] Workflow "Build and Publish Docker Image" запустился
- [ ] Все шаги выполнены успешно (зелёные галочки)
- [ ] Шаг "Verify image does NOT contain database" прошёл
- [ ] Образ опубликован в Packages

## ☑️ Проверка Registry

- [ ] Образ виден в Packages:
  https://github.com/victor2606?tab=packages
- [ ] Доступны теги: `latest` и `v1.0.0`
- [ ] Образ публичный (можно скачать без авторизации):
  ```bash
  docker logout ghcr.io
  docker pull ghcr.io/victor2606/construction-estimator-mcp:latest
  ```

## ☑️ Release (если создан тег)

- [ ] GitHub Release создан автоматически
- [ ] Release содержит инструкции по использованию
- [ ] В Release указано: "Database NOT included"

## ☑️ Тест с чистой установки

Симулируйте пользователя на новой машине:

```bash
# Создайте новую директорию (не в проекте)
cd ~/Desktop
mkdir test-mcp-deploy && cd test-mcp-deploy
```

- [ ] Скачать образ:
  ```bash
  docker pull ghcr.io/victor2606/construction-estimator-mcp:latest
  ```
- [ ] Получить БД (скопировать откуда-то):
  ```bash
  mkdir -p data/processed
  cp /path/to/estimates.db data/processed/
  ```
- [ ] Создать docker-compose.yml (скопировать из документации)
- [ ] Запустить:
  ```bash
  docker-compose up -d
  ```
- [ ] Проверить health:
  ```bash
  curl http://localhost:8003/health
  # Должен вернуть: {"status": "healthy", ...}
  ```
- [ ] Проверить логи без ошибок:
  ```bash
  docker-compose logs
  ```

## ☑️ Документация для пользователей

- [ ] README_DOCKER.md содержит ссылку на образ
- [ ] FIRST_TIME_SETUP.md содержит пошаговую инструкцию
- [ ] Указано где получить estimates.db
- [ ] Примеры docker-compose.yml актуальны

## ☑️ Коммуникация

Подготовьте для пользователей:

- [ ] Ссылка на Docker образ: `ghcr.io/victor2606/construction-estimator-mcp:latest`
- [ ] Инструкция: `FIRST_TIME_SETUP.md`
- [ ] Способ получения БД (приватно!)
- [ ] Контакты для поддержки

## 🎉 Готово к публикации!

Если все пункты отмечены ✅, можно публиковать.

### Команды для публикации:

```bash
# 1. Финальный commit
git add .
git commit -m "feat: production-ready Docker infrastructure"

# 2. Создать тег
git tag v1.0.0

# 3. Push
git push origin main
git push origin v1.0.0

# 4. Проверить Actions
# https://github.com/victor2606/n8npiplines-bim/actions

# 5. Дождаться успешной публикации

# 6. Тест скачивания
docker pull ghcr.io/victor2606/construction-estimator-mcp:latest

# 7. Готово! 🚀
```

---

## 🔄 После публикации

- [ ] Обновить README проекта со ссылкой на образ
- [ ] Создать Release Notes на GitHub
- [ ] Уведомить пользователей о доступности
- [ ] Предоставить БД через безопасный канал

---

## 📞 Если что-то пошло не так

### GitHub Actions failed

```bash
# Проверить логи
# https://github.com/victor2606/n8npiplines-bim/actions

# Частые причины:
# - Нет прав на packages:write (Settings → Actions → Permissions)
# - .dockerignore не работает (проверить синтаксис)
# - Dockerfile ошибка сборки (проверить локально)
```

### БД обнаружена в образе

```bash
# НЕМЕДЛЕННО удалить образ из registry!
# GitHub Packages → construction-estimator-mcp → Settings → Delete

# Исправить .dockerignore
# Пересобрать и протестировать
./build.sh --test

# Опубликовать заново
```

### Пользователи не могут запустить

- Убедитесь что они прочитали FIRST_TIME_SETUP.md
- Проверьте что они получили файл estimates.db
- Проверьте volume mount путь в их docker-compose.yml

---

Успехов! 🎯
