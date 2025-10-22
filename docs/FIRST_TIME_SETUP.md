# Первый запуск - Пошаговая инструкция

Инструкция для того, кто первый раз разворачивает MCP сервер из публичного Docker образа.

## 📋 Предварительные требования

- [x] Docker установлен ([скачать](https://www.docker.com/products/docker-desktop))
- [x] Docker Compose установлен (обычно идёт вместе с Docker Desktop)
- [x] Получен файл `estimates.db` от администратора проекта
- [x] Минимум 512 MB свободной RAM
- [x] Минимум 1 GB свободного места на диске

---

## 🚀 Шаг 1: Подготовка директории

```bash
# Создайте рабочую директорию
mkdir ~/construction-estimator
cd ~/construction-estimator

# Создайте структуру поддиректорий
mkdir -p data/processed data/logs data/cache
```

**Результат:**
```
~/construction-estimator/
├── data/
│   ├── processed/
│   ├── logs/
│   └── cache/
```

---

## 🗄️ Шаг 2: Размещение базы данных

```bash
# Скопируйте полученный файл estimates.db в нужную директорию
cp /path/to/estimates.db ./data/processed/estimates.db

# Проверьте, что файл на месте
ls -lh ./data/processed/estimates.db

# Должно показать файл размером ~150 MB
```

**Ожидаемый вывод:**
```
-rw-r--r--  1 user  staff   147M Oct 20 18:27 data/processed/estimates.db
```

---

## 📝 Шаг 3: Создание docker-compose.yml

Создайте файл `docker-compose.yml` в директории `~/construction-estimator/`:

```bash
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  mcp-server:
    image: ghcr.io/victor2606/construction-estimator-mcp:latest
    container_name: construction-estimator-mcp

    ports:
      - "8002:8000"   # MCP сервер (SSE endpoint)
      - "8003:8001"   # Health check

    volumes:
      # ВАЖНО: База данных монтируется как read-only (:ro)
      - ./data/processed/estimates.db:/app/data/processed/estimates.db:ro
      # Логи (опционально)
      - ./data/logs:/app/data/logs
      # Кэш (опционально)
      - ./data/cache:/app/data/cache

    environment:
      - PYTHONUNBUFFERED=1
      - LOG_LEVEL=INFO
      - DB_PATH=/app/data/processed/estimates.db

    restart: unless-stopped

    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s

networks:
  default:
    name: mcp-network
EOF
```

**Проверьте, что файл создан:**
```bash
ls -lh docker-compose.yml
cat docker-compose.yml
```

---

## 🏃 Шаг 4: Запуск сервера

```bash
# Скачайте Docker образ
docker-compose pull

# Запустите сервер в фоновом режиме
docker-compose up -d

# Проверьте статус
docker-compose ps
```

**Ожидаемый вывод:**
```
NAME                          IMAGE                                              STATUS
construction-estimator-mcp    ghcr.io/victor2606/construction-estimator-mcp      Up 10 seconds (healthy)
```

---

## ✅ Шаг 5: Проверка работоспособности

### Проверка 1: Health Check

```bash
curl http://localhost:8003/health
```

**Ожидаемый ответ:**
```json
{
  "status": "healthy",
  "database": "connected",
  "rates_count": 28686,
  "timestamp": "2025-10-22T12:00:00Z"
}
```

### Проверка 2: Логи контейнера

```bash
docker-compose logs mcp-server
```

**Не должно быть ошибок.** Ожидаемые строки:
```
[INFO] DatabaseManager connected successfully
[INFO] SearchEngine initialized
[INFO] CostCalculator initialized
[INFO] RateComparator initialized
[INFO] Starting MCP server with SSE transport on 0.0.0.0:8000
```

### Проверка 3: SSE Endpoint

```bash
curl http://localhost:8002/sse
```

**Должен вернуть информацию о SSE stream** (не ошибку).

---

## 🔌 Шаг 6: Подключение из n8n

### Вариант A: n8n в Docker на том же хосте

В n8n добавьте **MCP Client Tool** node:

```
Endpoint URL: http://host.docker.internal:8002/sse
Server Transport: SSE
```

### Вариант B: n8n на другом сервере

```
Endpoint URL: http://<IP вашего сервера>:8002/sse
Server Transport: SSE
```

**Важно:** Убедитесь, что порт 8002 доступен через firewall.

### Проверка подключения из n8n

1. Создайте новый workflow
2. Добавьте **Chat Trigger** node
3. Добавьте **AI Agent** node
4. Добавьте **MCP Client Tool** node с настройками выше
5. Подключите узлы
6. Отправьте тестовое сообщение: "Сколько стоит 100 м² перегородок?"

**Ожидаемый результат:** Агент должен использовать инструменты MCP сервера и вернуть ответ с расценками.

---

## 🛑 Остановка сервера

```bash
# Остановить контейнер
docker-compose down

# Остановить и удалить volumes (осторожно! удалит логи)
docker-compose down -v
```

---

## 🔄 Обновление до новой версии

```bash
# Остановить текущую версию
docker-compose down

# Скачать новую версию образа
docker-compose pull

# Запустить с новой версией
docker-compose up -d

# Проверить версию
docker inspect construction-estimator-mcp | grep -A 5 Labels
```

**База данных сохранится**, так как она не в контейнере, а смонтирована как volume.

---

## 🐛 Troubleshooting (Решение проблем)

### Проблема 1: Контейнер запускается и сразу останавливается

**Диагностика:**
```bash
docker-compose logs mcp-server
```

**Частая причина:** База данных не найдена

**Решение:**
```bash
# Проверьте путь к БД
ls -lh ./data/processed/estimates.db

# Если файла нет:
# 1. Убедитесь, что вы скопировали estimates.db
# 2. Проверьте права доступа: chmod 644 ./data/processed/estimates.db
```

---

### Проблема 2: Health check failed

**Диагностика:**
```bash
docker-compose ps  # Смотрим статус
docker exec construction-estimator-mcp python -c "
import sqlite3
conn = sqlite3.connect('/app/data/processed/estimates.db')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM rates')
print(f'Rates: {cursor.fetchone()[0]}')
conn.close()
"
```

**Ожидаемый вывод:** `Rates: 28686`

**Если ошибка:**
- Проверьте, что БД не повреждена
- Проверьте версию SQLite в контейнере
- Проверьте права доступа к файлу

---

### Проблема 3: Порт 8002 уже занят

**Диагностика:**
```bash
# Linux/macOS
lsof -i :8002

# Windows
netstat -ano | findstr :8002
```

**Решение 1:** Остановить другой процесс

**Решение 2:** Изменить порт в `docker-compose.yml`:
```yaml
ports:
  - "8004:8000"  # Используйте другой порт
```

Не забудьте обновить URL в n8n!

---

### Проблема 4: Permission denied (Linux)

```bash
# Проверьте владельца файла
ls -l ./data/processed/estimates.db

# Если нужно, измените владельца
sudo chown $(id -u):$(id -g) ./data/processed/estimates.db

# Или дайте права на чтение всем
chmod 644 ./data/processed/estimates.db
```

---

### Проблема 5: n8n не может подключиться к MCP серверу

**Проверьте:**

1. **Сервер запущен:**
   ```bash
   docker-compose ps
   curl http://localhost:8002/sse
   ```

2. **Firewall не блокирует порт:**
   ```bash
   # Linux
   sudo ufw status
   sudo ufw allow 8002

   # macOS (обычно не нужно)
   # Windows: проверьте Windows Defender Firewall
   ```

3. **Правильный хост в n8n:**
   - n8n в Docker на том же хосте: `http://host.docker.internal:8002/sse`
   - n8n на другом сервере: `http://<IP>:8002/sse`
   - n8n не в Docker: `http://localhost:8002/sse`

---

## 📊 Мониторинг

### Просмотр логов в реальном времени

```bash
docker-compose logs -f mcp-server
```

### Использование ресурсов

```bash
docker stats construction-estimator-mcp
```

**Нормальные значения:**
- CPU: 0-5% (idle), 10-30% (under load)
- Memory: 100-200 MB
- Network: зависит от нагрузки

### Размер логов

```bash
du -sh ./data/logs/
```

**Очистка старых логов:**
```bash
# Удалить логи старше 7 дней
find ./data/logs/ -name "*.log" -mtime +7 -delete
```

---

## 🔐 Безопасность

### Рекомендации для production:

1. **Не открывайте порты публично**
   ```bash
   # Привязывайте к localhost только
   ports:
     - "127.0.0.1:8002:8000"
   ```

2. **Используйте reverse proxy (nginx/traefik) с SSL**

3. **Ограничьте доступ через firewall**
   ```bash
   # Разрешить только с определённой подсети
   sudo ufw allow from 192.168.1.0/24 to any port 8002
   ```

4. **Регулярно обновляйте образ**
   ```bash
   docker-compose pull
   docker-compose up -d
   ```

---

## 📚 Дополнительная информация

- **Полная документация:** [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)
- **Интеграция с n8n:** [N8N_WORKFLOW_OPTIMIZATION_GUIDE.md](./N8N_WORKFLOW_OPTIMIZATION_GUIDE.md)
- **Примеры запросов:** [docs/example_queries.md](./docs/example_queries.md)

---

## 🎉 Готово!

Ваш MCP сервер запущен и готов к работе.

**Следующие шаги:**
1. Импортировать workflow в n8n: `n8n-construction-estimator-optimized.json`
2. Настроить подключение к MCP серверу
3. Протестировать с примерами запросов

**Тестовый запрос для проверки:**
```
Сколько будет стоить устройство 150 м² перегородок из ГКЛ с двойным металлическим каркасом?
```

**Ожидаемый ответ от агента:**
- Найденная расценка (код типа ГЭСНп10-05-004-01)
- Общая стоимость (~59,000 руб.)
- Детализация по материалам и работам
- Альтернативные варианты

---

Успешного использования! 🚀
