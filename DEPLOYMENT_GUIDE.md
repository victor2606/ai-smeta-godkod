# Deployment Guide - Construction Estimator MCP Server

## Overview

This guide explains how to deploy the MCP server using the public Docker image. **The database file is NOT included in the image** and must be provided separately.

## Quick Start for End Users

### Prerequisites

1. Docker and Docker Compose installed
2. Database file: `estimates.db` (~150MB, 28,686 rates)
3. Minimum 512MB RAM, 1GB disk space

### Step 1: Get the Database File

**Option A: Получить от администратора проекта**
```bash
# Администратор должен предоставить вам файл estimates.db
# НЕ публикуйте его в общедоступных местах!
```

**Option B: Сгенерировать самостоятельно** (если есть исходный Excel файл)
```bash
git clone https://github.com/victor2606/n8npiplines-bim.git
cd n8npiplines-bim

# Поместите Excel файл в data/raw/
# Запустите ETL процесс
python -m src.etl.excel_to_sqlite

# Результат: data/processed/estimates.db
```

### Step 2: Create Project Structure

```bash
mkdir -p construction-estimator/{data/processed,data/logs,data/cache}
cd construction-estimator
```

### Step 3: Place Database File

```bash
# Скопируйте estimates.db в нужное место
cp /path/to/estimates.db ./data/processed/estimates.db

# Проверьте размер файла
ls -lh ./data/processed/estimates.db
# Ожидаемый размер: ~150MB
```

### Step 4: Download docker-compose.yml

```bash
curl -O https://raw.githubusercontent.com/victor2606/n8npiplines-bim/main/docker-compose.yml
```

Or create `docker-compose.yml` manually:

```yaml
version: '3.8'

services:
  mcp-server:
    image: ghcr.io/victor2606/construction-estimator-mcp:latest
    container_name: construction-estimator-mcp
    ports:
      - "8002:8000"   # MCP server SSE endpoint
      - "8003:8001"   # Health check endpoint
    volumes:
      # CRITICAL: Mount your database file here
      - ./data/processed/estimates.db:/app/data/processed/estimates.db:ro
      - ./data/logs:/app/data/logs
      - ./data/cache:/app/data/cache
    environment:
      - PYTHONUNBUFFERED=1
      - LOG_LEVEL=INFO
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
```

### Step 5: Start the Server

```bash
# Pull latest image
docker-compose pull

# Start in background
docker-compose up -d

# Check status
docker-compose ps

# Expected output:
# NAME                          IMAGE                                              STATUS
# construction-estimator-mcp    ghcr.io/victor2606/construction-estimator-mcp      Up (healthy)
```

### Step 6: Verify Installation

```bash
# Check health endpoint
curl http://localhost:8003/health

# Expected response:
# {"status": "healthy", "database": "connected", "rates_count": 28686}

# Check MCP endpoint (returns SSE stream info)
curl http://localhost:8002/sse
```

### Step 7: Connect from n8n

In your n8n workflow, add MCP Client Tool node:

```
Endpoint URL: http://host.docker.internal:8002/sse
Server Transport: SSE
```

Done! Your MCP server is running.

---

## Volume Mounts Explained

### Required Mount (Read-Only)

```yaml
- ./data/processed/estimates.db:/app/data/processed/estimates.db:ro
```

**Purpose**: Database file with 28,686 construction rates
- **Source**: Your local `./data/processed/estimates.db`
- **Target**: Container path `/app/data/processed/estimates.db`
- **Mode**: `:ro` (read-only) - protects your database from accidental modification

**Why read-only?**
- MCP server only reads data, never writes
- Prevents data corruption
- Multiple containers can share the same database safely

### Optional Mounts

```yaml
- ./data/logs:/app/data/logs
```
**Purpose**: Application logs for debugging
- Not read-only - server writes logs here
- Useful for troubleshooting

```yaml
- ./data/cache:/app/data/cache
```
**Purpose**: Query result cache (if implemented)
- Improves performance for repeated queries
- Can be safely deleted to clear cache

---

## Alternative Deployment: Docker Run

If you prefer `docker run` over docker-compose:

```bash
docker pull ghcr.io/victor2606/construction-estimator-mcp:latest

docker run -d \
  --name construction-estimator-mcp \
  -p 8002:8000 \
  -p 8003:8001 \
  -v $(pwd)/data/processed/estimates.db:/app/data/processed/estimates.db:ro \
  -v $(pwd)/data/logs:/app/data/logs \
  -e LOG_LEVEL=INFO \
  --restart unless-stopped \
  ghcr.io/victor2606/construction-estimator-mcp:latest
```

---

## Troubleshooting

### Error: "Database file not found"

```bash
# Check if database file exists locally
ls -lh ./data/processed/estimates.db

# If missing, create directory structure
mkdir -p ./data/processed

# Copy database file to correct location
cp /path/to/estimates.db ./data/processed/
```

### Error: "Permission denied"

```bash
# Ensure database file is readable
chmod 644 ./data/processed/estimates.db

# Check file ownership
ls -l ./data/processed/estimates.db

# If needed, change ownership (Linux/macOS)
sudo chown $(id -u):$(id -g) ./data/processed/estimates.db
```

### Health Check Failing

```bash
# Check container logs
docker-compose logs mcp-server

# Look for errors related to:
# - Database connection
# - Port binding
# - Python dependencies
```

### Container Starts But Tools Don't Work

```bash
# Verify database has correct structure
docker exec construction-estimator-mcp python -c "
import sqlite3
conn = sqlite3.connect('/app/data/processed/estimates.db')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM rates')
print(f'Rates count: {cursor.fetchone()[0]}')
conn.close()
"

# Expected output: Rates count: 28686
```

### Port Already in Use

```bash
# Check what's using port 8002
lsof -i :8002  # macOS/Linux
netstat -ano | findstr :8002  # Windows

# Option 1: Stop conflicting service
# Option 2: Change port in docker-compose.yml
ports:
  - "8004:8000"  # Use different port
```

---

## Security Considerations

### Database File Protection

❌ **NEVER**:
- Commit `estimates.db` to public Git repositories
- Share database file in public channels
- Include database in Docker image
- Expose database file via HTTP/FTP

✅ **ALWAYS**:
- Mount database as read-only (`:ro`)
- Keep database file on secure storage
- Use encryption for database file transfer
- Implement access controls on host machine

### Network Security

**Production Setup**:
```yaml
# Use reverse proxy (nginx/traefik) with SSL
services:
  nginx:
    image: nginx:alpine
    ports:
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro

  mcp-server:
    # No ports exposed externally
    expose:
      - "8000"
    networks:
      - internal
```

**Firewall Rules**:
```bash
# Only allow localhost connections
sudo ufw allow from 127.0.0.1 to any port 8002

# Or allow specific IP range
sudo ufw allow from 192.168.1.0/24 to any port 8002
```

---

## Updating the Image

```bash
# Pull latest version
docker-compose pull

# Recreate container with new image
docker-compose up -d

# Old container is automatically stopped and removed
```

**Zero-downtime update** (advanced):
```bash
# Start new container with different name
docker-compose -p mcp-new up -d

# Verify new container is healthy
curl http://localhost:8004/health

# Switch n8n to new endpoint
# Then stop old container
docker-compose -p mcp-old down
```

---

## Backup Strategy

### Database Backup

```bash
# Create backup
cp ./data/processed/estimates.db \
   ./data/processed/estimates_backup_$(date +%Y%m%d_%H%M%S).db

# Automated backup (Linux/macOS cron)
0 2 * * * cd /path/to/construction-estimator && \
  cp ./data/processed/estimates.db \
     ./data/processed/estimates_backup_$(date +\%Y\%m\%d).db && \
  find ./data/processed/estimates_backup_*.db -mtime +30 -delete
```

### Restore from Backup

```bash
# Stop container
docker-compose down

# Restore database
cp ./data/processed/estimates_backup_20251020.db \
   ./data/processed/estimates.db

# Start container
docker-compose up -d
```

---

## Monitoring

### Health Checks

```bash
# Manual health check
curl http://localhost:8003/health

# Automated monitoring (with uptime-kuma, prometheus, etc.)
# Health endpoint: http://localhost:8003/health
# Expected response: {"status": "healthy", "database": "connected"}
```

### Resource Monitoring

```bash
# Container stats
docker stats construction-estimator-mcp

# Expected resource usage:
# CPU: 0-5% (idle), 10-30% (under load)
# Memory: 100-200MB
# Disk I/O: Minimal (read-only database)
```

### Log Monitoring

```bash
# Follow logs in real-time
docker-compose logs -f mcp-server

# Save logs to file
docker-compose logs --no-color > mcp-server.log

# Search for errors
docker-compose logs mcp-server | grep -i error
```

---

## Scaling

### Single Server (Current Setup)

Handles ~100-500 requests/minute depending on query complexity.

### Multiple Instances (Load Balancing)

```yaml
version: '3.8'

services:
  mcp-server-1:
    image: ghcr.io/victor2606/construction-estimator-mcp:latest
    volumes:
      - ./data/processed/estimates.db:/app/data/processed/estimates.db:ro
    expose:
      - "8000"

  mcp-server-2:
    image: ghcr.io/victor2606/construction-estimator-mcp:latest
    volumes:
      - ./data/processed/estimates.db:/app/data/processed/estimates.db:ro
    expose:
      - "8000"

  nginx:
    image: nginx:alpine
    ports:
      - "8002:80"
    volumes:
      - ./nginx-lb.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - mcp-server-1
      - mcp-server-2
```

nginx load balancer config (`nginx-lb.conf`):
```nginx
upstream mcp_backend {
    least_conn;
    server mcp-server-1:8000;
    server mcp-server-2:8000;
}

server {
    listen 80;
    location /sse {
        proxy_pass http://mcp_backend;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }
}
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_PATH` | `/app/data/processed/estimates.db` | Database file path |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `PYTHONUNBUFFERED` | `1` | Disable Python output buffering |

**Custom database path**:
```yaml
environment:
  - DB_PATH=/custom/path/to/database.db
volumes:
  - /custom/path/to/database.db:/custom/path/to/database.db:ro
```

---

## FAQ

### Q: Can I use a different database file name?

**A**: Yes, update the volume mount and environment variable:
```yaml
volumes:
  - ./my_rates.db:/app/data/processed/my_rates.db:ro
environment:
  - DB_PATH=/app/data/processed/my_rates.db
```

### Q: Can multiple users share the same database file?

**A**: Yes! Since it's mounted read-only, multiple containers can safely share:
```yaml
# On server 1
- /shared/nfs/estimates.db:/app/data/processed/estimates.db:ro

# On server 2
- /shared/nfs/estimates.db:/app/data/processed/estimates.db:ro
```

### Q: How do I update the database with new rates?

**A**:
1. Stop container: `docker-compose down`
2. Replace database file: `cp new_estimates.db ./data/processed/estimates.db`
3. Restart: `docker-compose up -d`

For zero-downtime updates, use blue-green deployment pattern.

### Q: Can I run this without Docker?

**A**: Yes, but you'll need to manually install Python dependencies:
```bash
pip install -r requirements.txt
python mcp_server.py
```

### Q: What if I lose the database file?

**A**: You must regenerate it from the source Excel file:
```bash
python -m src.etl.excel_to_sqlite
```
This requires the original Excel file with construction rates.

---

## Support

For issues or questions:
- GitHub Issues: https://github.com/victor2606/n8npiplines-bim/issues
- Check logs: `docker-compose logs mcp-server`
- Health check: `curl http://localhost:8003/health`

---

## License

This deployment setup is provided as-is. The database file (`estimates.db`) is proprietary and must be obtained separately.
