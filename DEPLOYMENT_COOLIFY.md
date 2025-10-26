# Deployment Guide for Coolify

## Overview

This project consists of two services:
1. **Backend API** - FastAPI HTTP REST server (`api_server.py`)
2. **Frontend** - React SPA with Telegram WebApp integration

## Prerequisites

- Coolify instance running
- GitHub Container Registry access
- Database file: `estimates.db`

## Backend API Deployment

### Docker Image
```
ghcr.io/victor2606/construction-estimator-api:latest
```

### Environment Variables
```env
DATABASE_PATH=/app/data/processed/estimates.db
OPENAI_API_KEY=<your-openai-api-key>
OPENAI_BASE_URL=<optional-custom-endpoint>
HOST=0.0.0.0
PORT=8000
```

### Volume Mounts (Required)
```yaml
volumes:
  - /root/mcp-server/data/processed/estimates.db:/app/data/processed/estimates.db:ro
  - /root/mcp-server/data/cache:/app/data/cache
  - /root/mcp-server/data/logs:/app/data/logs
```

### Traefik Labels
```yaml
labels:
  - traefik.enable=true
  - traefik.http.routers.bim-api.rule=Host(`api.yourdomain.com`)
  - traefik.http.routers.bim-api.entrypoints=https
  - traefik.http.routers.bim-api.tls=true
  - traefik.http.routers.bim-api.tls.certresolver=letsencrypt
  - traefik.http.services.bim-api.loadbalancer.server.port=8000
```

### Health Check
- Endpoint: `GET /health`
- Expected response: `{"status": "healthy"}`

## Frontend Deployment

### Docker Image
```
ghcr.io/victor2606/bim-frontend:latest
```

### Environment Variables
```env
VITE_API_URL=https://api.yourdomain.com/api
```

**IMPORTANT**: Must be set at **build time**, not runtime. Rebuild image if API URL changes.

### Traefik Labels
```yaml
labels:
  - traefik.enable=true
  - traefik.http.routers.bim-frontend.rule=Host(`bim.yourdomain.com`)
  - traefik.http.routers.bim-frontend.entrypoints=https
  - traefik.http.routers.bim-frontend.tls=true
  - traefik.http.routers.bim-frontend.tls.certresolver=letsencrypt
  - traefik.http.services.bim-frontend.loadbalancer.server.port=80
```

## Deployment Steps

### 1. Deploy Backend API

In Coolify:

1. **Create New Resource** → Docker Image
2. **Image**: `ghcr.io/victor2606/construction-estimator-api:latest`
3. **Port**: 8000
4. **Environment Variables**: Set DATABASE_PATH, OPENAI_API_KEY
5. **Volumes**: Mount database and cache directories
6. **Domain**: `api.yourdomain.com`
7. **Deploy**

### 2. Deploy Frontend

In Coolify:

1. **Create New Resource** → Docker Image
2. **Image**: `ghcr.io/victor2606/bim-frontend:latest`
3. **Port**: 80
4. **Environment Variables**: Set VITE_API_URL (build-time)
5. **Domain**: `bim.yourdomain.com`
6. **Deploy**

### 3. Configure Telegram Bot

1. Create bot via @BotFather
2. Create Web App: `/newapp`
3. Set URL: `https://bim.yourdomain.com`
4. Get link: `https://t.me/your_bot/app_name`

## Testing

### Backend API
```bash
# Health check
curl https://api.yourdomain.com/health

# Natural search
curl -X POST https://api.yourdomain.com/api/natural_search \
  -H "Content-Type: application/json" \
  -d '{"query": "перегородки", "limit": 5}'

# Quick calculate
curl -X POST https://api.yourdomain.com/api/quick_calculate \
  -H "Content-Type: application/json" \
  -d '{"rate_identifier": "ГЭСНп10-05-001-01", "quantity": 50}'
```

### Frontend
```bash
# Should return HTML
curl https://bim.yourdomain.com

# Open in browser
open https://bim.yourdomain.com

# Open in Telegram
# Click the bot link: https://t.me/your_bot/app_name
```

## Troubleshooting

### Backend API Issues

**Problem**: Database not found
```
Solution: Check volume mount path matches DATABASE_PATH
```

**Problem**: Vector search disabled
```
Solution: Set OPENAI_API_KEY environment variable
```

**Problem**: CORS errors from frontend
```
Solution: Check CORS middleware allows frontend domain
```

### Frontend Issues

**Problem**: API requests fail
```
Solution: Check VITE_API_URL matches backend domain
Note: Must rebuild image if changing API URL
```

**Problem**: Blank page
```
Solution: 
1. Check nginx.conf has try_files $uri /index.html
2. Check browser console for errors
3. Verify index.html is served at root
```

**Problem**: Telegram WebApp not loading
```
Solution:
1. Domain must use HTTPS (Telegram requirement)
2. Check Telegram SDK script loaded
3. Check initTelegram() called in App.tsx
```

## Docker Compose Example

For local testing or manual deployment:

```yaml
version: '3.8'

services:
  backend-api:
    image: ghcr.io/victor2606/construction-estimator-api:latest
    container_name: bim-backend-api
    ports:
      - "8000:8000"
    environment:
      - DATABASE_PATH=/app/data/processed/estimates.db
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - ./data/processed/estimates.db:/app/data/processed/estimates.db:ro
      - ./data/cache:/app/data/cache
      - ./data/logs:/app/data/logs
    networks:
      - bim-network
    restart: unless-stopped

  frontend:
    image: ghcr.io/victor2606/bim-frontend:latest
    container_name: bim-frontend
    ports:
      - "3000:80"
    environment:
      - VITE_API_URL=http://backend-api:8000/api
    networks:
      - bim-network
    depends_on:
      - backend-api
    restart: unless-stopped

networks:
  bim-network:
    driver: bridge
```

Run:
```bash
docker-compose up -d
```

Access:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/health

## Updating Services

### Backend Update
```bash
# Build new image
docker build -f Dockerfile.api -t ghcr.io/victor2606/construction-estimator-api:latest .

# Push to registry
docker push ghcr.io/victor2606/construction-estimator-api:latest

# In Coolify: Redeploy service (pulls latest)
```

### Frontend Update
```bash
# Build with correct API URL
cd frontend
docker build --build-arg VITE_API_URL=https://api.yourdomain.com/api \
  -t ghcr.io/victor2606/bim-frontend:latest .

# Push to registry
docker push ghcr.io/victor2606/bim-frontend:latest

# In Coolify: Redeploy service
```

## Monitoring

### Logs
```bash
# Backend
docker logs -f bim-backend-api

# Frontend (nginx access logs)
docker logs -f bim-frontend
```

### Health Checks
Both services have health checks configured:
- Backend: Checks database connection
- Frontend: Nginx serves index.html

Monitor in Coolify dashboard or via Docker:
```bash
docker ps --filter health=healthy
```

## Security Notes

1. **HTTPS Required**: Telegram WebApps only work over HTTPS
2. **CORS**: Frontend domain must be allowed in backend CORS settings
3. **API Keys**: Store OPENAI_API_KEY securely (use Coolify secrets)
4. **Database**: Mount as read-only (`:ro`) if backend doesn't need write access

## Support

For issues:
1. Check logs in Coolify
2. Verify environment variables
3. Test API endpoints directly
4. Check Telegram WebApp console in DevTools
