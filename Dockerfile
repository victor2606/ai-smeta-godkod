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

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime image
FROM python:3.10-slim

WORKDIR /app

# Create non-root user for security
RUN useradd -m -u 1000 mcpuser && \
    mkdir -p /app/data/processed /app/data/logs /app/data/raw && \
    chown -R mcpuser:mcpuser /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /home/mcpuser/.local

# Copy application code (NO DATA FILES)
COPY --chown=mcpuser:mcpuser src/ ./src/
COPY --chown=mcpuser:mcpuser mcp_server.py .
COPY --chown=mcpuser:mcpuser health_server.py .

# Set PATH for user-installed packages
ENV PATH=/home/mcpuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Database path (will be mounted as volume)
ENV DB_PATH=/app/data/processed/estimates.db

# Switch to non-root user
USER mcpuser

# Expose ports
EXPOSE 8000 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')" || exit 1

# Run MCP server
ENTRYPOINT ["python", "mcp_server.py"]
