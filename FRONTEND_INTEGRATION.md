# Frontend Integration Guide

## Submodule Setup

Фронтенд добавлен как git submodule в директорию `frontend/`.

### Клонирование проекта с submodule

```bash
# Первичное клонирование
git clone --recurse-submodules <main-repo-url>

# Или если уже клонировали
git submodule update --init --recursive
```

### Обновление frontend submodule

```bash
# Перейти в директорию submodule
cd frontend

# Получить изменения
git pull origin main

# Вернуться в корень проекта
cd ..

# Зафиксировать новую версию submodule
git add frontend
git commit -m "Update frontend submodule"
git push
```

## Docker Compose Integration

### Вариант 1: Общий docker-compose.yml (рекомендуется)

Создайте/обновите `docker-compose.yml` в корне проекта:

```yaml
version: '3.8'

services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: bim-backend
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    networks:
      - bim-network
    environment:
      - DATABASE_PATH=/app/data/bim.db

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: bim-frontend
    ports:
      - "3000:80"
    environment:
      - VITE_API_URL=http://backend:8000/api
    networks:
      - bim-network
    depends_on:
      - backend

networks:
  bim-network:
    driver: bridge
```

### Вариант 2: Отдельные docker-compose файлы

**backend/docker-compose.yml** (ваш текущий)
```yaml
# Без изменений
```

**frontend/docker-compose.yml** (уже есть)
```yaml
# Использует external network: bim-network
```

Запуск:
```bash
# Создать сеть
docker network create bim-network

# Запустить backend
docker-compose up -d

# Запустить frontend
cd frontend
docker-compose up -d
```

## Локальная разработка

### Backend
```bash
# Запустить MCP сервер
uvicorn mcp_server:app --reload --host 0.0.0.0 --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
# Доступен на http://localhost:5173
```

Frontend будет подключаться к backend через `http://localhost:8000/api`

## Production Deployment

### С Nginx reverse proxy

**nginx.conf** (на хосте):
```nginx
server {
    listen 80;
    server_name your-domain.com;

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Backend API
    location /api/ {
        proxy_pass http://localhost:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### С Traefik

```yaml
version: '3.8'

services:
  traefik:
    image: traefik:v2.10
    command:
      - "--api.insecure=true"
      - "--providers.docker=true"
      - "--entrypoints.web.address=:80"
    ports:
      - "80:80"
      - "8080:8080"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock

  backend:
    build: .
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.backend.rule=PathPrefix(`/api`)"
      - "traefik.http.services.backend.loadbalancer.server.port=8000"
    networks:
      - bim-network

  frontend:
    build: ./frontend
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.frontend.rule=PathPrefix(`/`)"
      - "traefik.http.services.frontend.loadbalancer.server.port=80"
    environment:
      - VITE_API_URL=http://backend:8000/api
    networks:
      - bim-network

networks:
  bim-network:
    driver: bridge
```

## Environment Variables

### Backend
- `DATABASE_PATH` - путь к SQLite базе данных
- `PORT` - порт для API (default: 8000)

### Frontend
- `VITE_API_URL` - URL бэкенд API
  - Development: `http://localhost:8000/api`
  - Docker: `http://backend:8000/api`
  - Production: `https://api.yourdomain.com/api`

## Telegram Mini App Setup

1. Создайте бота через @BotFather
2. Создайте Web App: `/newapp`
3. Укажите production URL (обязательно HTTPS)
4. Получите ссылку: `https://t.me/your_bot/app_name`

## Troubleshooting

### Frontend не видит backend API

**Проверьте:**
1. Оба контейнера в одной сети: `docker network inspect bim-network`
2. Backend доступен: `docker exec bim-frontend curl http://backend:8000/api/health`
3. CORS настроен на backend для frontend домена

### Submodule пустой после клонирования

```bash
git submodule update --init --recursive
```

### Ошибка при git pull с submodule

```bash
# Сначала обновить submodule
cd frontend
git pull origin main
cd ..

# Потом основной проект
git pull origin main
```

## Полезные команды

```bash
# Проверить статус submodule
git submodule status

# Выполнить команду во всех submodules
git submodule foreach 'git pull origin main'

# Удалить submodule (если нужно)
git submodule deinit frontend
git rm frontend
rm -rf .git/modules/frontend

# Пересобрать контейнеры
docker-compose build --no-cache
docker-compose up -d
```

## Структура проекта

```
n8npiplines-bim/
├── frontend/                 # Git submodule
│   ├── src/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── README.md
├── src/
│   ├── database/
│   ├── search/
│   └── ...
├── mcp_server.py
├── docker-compose.yml        # Общий compose файл
└── FRONTEND_INTEGRATION.md   # Этот файл
```
