# Construction Estimator MCP Server - Docker Deployment

[![Docker](https://img.shields.io/badge/docker-ghcr.io-blue)](https://github.com/victor2606/n8npiplines-bim/pkgs/container/construction-estimator-mcp)
[![License](https://img.shields.io/badge/license-Proprietary-red)]()

Production-ready Docker image for MCP server providing construction cost estimation tools.

## 🚨 Important: Database Not Included

**This Docker image does NOT contain the database file.** Users must provide `estimates.db` separately and mount it as a volume.

## 🚀 Quick Start

```bash
# 1. Pull the image
docker pull ghcr.io/victor2606/construction-estimator-mcp:latest

# 2. Run with database mounted
docker run -d \
  --name mcp-server \
  -p 8002:8000 \
  -v /path/to/estimates.db:/app/data/processed/estimates.db:ro \
  ghcr.io/victor2606/construction-estimator-mcp:latest

# 3. Verify
curl http://localhost:8002/health
```

## 📦 What's Included

✅ Python MCP server application
✅ 5 specialized tools (search, calculate, compare, details, alternatives)
✅ FastMCP framework
✅ Health check endpoint

❌ Database file (`estimates.db`) - **must be mounted**
❌ Excel source files
❌ Logs and cache

## 📖 Documentation

- **[DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)** - Full deployment instructions
- **[DOCKER_BUILD_PUBLISH.md](./DOCKER_BUILD_PUBLISH.md)** - Build and publish guide
- **[N8N_WORKFLOW_OPTIMIZATION_GUIDE.md](./N8N_WORKFLOW_OPTIMIZATION_GUIDE.md)** - n8n integration

## 🔧 Usage with Docker Compose

```yaml
version: '3.8'

services:
  mcp-server:
    image: ghcr.io/victor2606/construction-estimator-mcp:latest
    ports:
      - "8002:8000"
    volumes:
      # Required: Mount database file
      - ./data/processed/estimates.db:/app/data/processed/estimates.db:ro
      # Optional: Logs
      - ./data/logs:/app/data/logs
    restart: unless-stopped
```

## 🔌 n8n Integration

Add MCP Client Tool node in n8n:

```
Endpoint URL: http://host.docker.internal:8002/sse
Server Transport: SSE
```

See [n8n-construction-estimator-optimized.json](./n8n-construction-estimator-optimized.json) for complete workflow.

## 🏗️ Build from Source

```bash
# Build
./build.sh

# Build with tests
./build.sh --test

# Build and push to registry
./build.sh --multi --push
```

See [DOCKER_BUILD_PUBLISH.md](./DOCKER_BUILD_PUBLISH.md) for details.

## 🗄️ Database Requirements

**File**: `estimates.db`
**Size**: ~150MB
**Contents**: 28,686 construction rates, 294,883 resources
**Format**: SQLite 3 with FTS5

**How to obtain**:
1. Contact project administrator
2. Or generate from Excel source (see ETL docs)

## 📊 API Endpoints

| Endpoint | Port | Description |
|----------|------|-------------|
| `/sse` | 8000 | MCP server (SSE transport) |
| `/health` | 8001 | Health check |

## 🏷️ Available Tags

| Tag | Description |
|-----|-------------|
| `latest` | Latest stable release |
| `vX.Y.Z` | Specific version (e.g., `v1.0.0`) |
| `main` | Latest from main branch |

## 🔒 Security Notes

- Database mounted as **read-only** (`:ro`)
- Container runs as non-root user (`mcpuser`, UID 1000)
- No sensitive data in image
- Health checks enabled

## 🐛 Troubleshooting

**Container starts but exits immediately:**
```bash
# Check logs
docker logs mcp-server

# Common issue: Database file not found
# Solution: Verify volume mount path
```

**Health check failing:**
```bash
# Verify database is accessible
docker exec mcp-server ls -lh /app/data/processed/estimates.db

# Check Python can connect
docker exec mcp-server python -c "
import sqlite3
conn = sqlite3.connect('/app/data/processed/estimates.db')
print(conn.execute('SELECT COUNT(*) FROM rates').fetchone())
"
```

## 📈 Performance

- **Memory**: ~150-200 MB
- **Startup**: <5 seconds
- **Requests/min**: 100-500 (depending on query complexity)

## 🛠️ Development

```bash
# Clone repository
git clone https://github.com/victor2606/n8npiplines-bim.git
cd n8npiplines-bim

# Build local image
docker build -t construction-estimator-mcp:dev .

# Run with local database
docker run -v ./data/processed/estimates.db:/app/data/processed/estimates.db:ro \
  -p 8002:8000 construction-estimator-mcp:dev
```

## 📝 License

Proprietary. Database file is confidential and must not be distributed publicly.

## 🤝 Support

- Issues: [GitHub Issues](https://github.com/victor2606/n8npiplines-bim/issues)
- Docs: See documentation files in repository

---

**Made with ❤️ for construction cost estimation**
