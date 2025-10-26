# Production Dockerfile for MCP Server (Construction Estimator)
# Database and Excel files are NOT included - they must be mounted as volumes
#
# Build: docker build -t ghcr.io/victor2606/construction-estimator-mcp:latest .
# Run:   docker run -v /path/to/estimates.db:/app/data/processed/estimates.db:ro \
#                   -p 8000:8000 ghcr.io/victor2606/construction-estimator-mcp:latest

# Stage 1: Build dependencies
FROM python:3.10-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies globally
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime image
FROM python:3.10-slim

WORKDIR /app

# Install nginx for internal routing
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    && rm -rf /var/lib/apt/lists/*

# Create directories
RUN mkdir -p /app/data/processed /app/data/logs /app/data/raw

# Copy Python dependencies from builder (installed globally)
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code (NO DATA FILES)
COPY src/ ./src/
COPY mcp_server.py .
COPY health_server.py .
COPY api_server.py .
COPY --chmod=755 start_both.sh .

# Copy nginx config
COPY nginx-internal.conf /etc/nginx/nginx.conf
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Database path (will be mounted as volume)
ENV DB_PATH=/app/data/processed/estimates.db

# Expose only nginx port (8080) - nginx will route internally
EXPOSE 8080

# Health check via nginx
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Run both servers
ENTRYPOINT ["./start_both.sh"]
