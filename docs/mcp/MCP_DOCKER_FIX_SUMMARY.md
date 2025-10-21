# MCP Server Docker Setup - Fix Summary

**Date:** 2025-10-21
**Status:** FIXED AND VERIFIED

## Problems Identified

### 1. Missing health_server.py in Docker Container
**Issue:** `health_server.py` existed at project root but was not copied to Docker container in `Dockerfile.mcp` line 32.

**Fix Applied:** Added missing COPY command at line 33 in Dockerfile.mcp:
```dockerfile
COPY --chown=mcpuser:mcpuser health_server.py .
```

### 2. Incorrect MCP Transport Configuration
**Issue:** `mcp_server.py` was using STDIO transport (`mcp.run()`) instead of SSE transport needed for N8N HTTP connections.

**Fix Applied:** Changed line 631 in mcp_server.py from:
```python
mcp.run()
```
To:
```python
mcp.run(transport="sse", host="0.0.0.0", port=8000)
```

### 3. Health Check Database Connection Issue
**Issue:** Health server was initializing DatabaseManager but not calling `connect()` method, causing health checks to fail.

**Fix Applied:** Added explicit `connect()` call in health_server.py line 113:
```python
db_manager = DatabaseManager(db_path)
db_manager.connect()  # Explicitly connect to the database
```

## Verification Results

### Container Status
```
NAME         STATUS
mcp-server   Up 19 seconds (healthy)
```

### Health Check Endpoint
```bash
curl http://localhost:8003/health
```
Response:
```json
{
    "status": "healthy",
    "database": "connected",
    "timestamp": "2025-10-21T16:15:57.677116"
}
```

### MCP SSE Endpoint
```bash
curl http://localhost:8002/sse
```
Response:
```
event: endpoint
data: /messages/?session_id=8e5df1318fa545bca3905ae31396509e
```

### Server Configuration
- **MCP Server URL:** `http://0.0.0.0:8000/sse` (internal)
- **External MCP Port:** `8002` (mapped to 8000)
- **Health Check Port:** `8003` (mapped to 8001)
- **Transport:** SSE (Server-Sent Events)
- **FastMCP Version:** 2.12.5
- **Database:** `/app/data/processed/estimates.db` (mounted read-only)

## N8N Connection Information

To connect N8N to this MCP server:

1. **MCP Server Endpoint:** `http://localhost:8002/sse`
2. **Connection Type:** HTTP/SSE
3. **Health Check:** `http://localhost:8003/health`

### Available MCP Tools
1. `natural_search` - Full-text search for construction rates
2. `quick_calculate` - Auto-detecting cost calculator
3. `show_rate_details` - Detailed resource breakdown
4. `compare_variants` - Compare multiple rates
5. `find_similar_rates` - Find alternative rates

## Files Modified

1. **Dockerfile.mcp**
   - Line 33: Added `COPY --chown=mcpuser:mcpuser health_server.py .`

2. **mcp_server.py**
   - Line 631: Changed to `mcp.run(transport="sse", host="0.0.0.0", port=8000)`

3. **health_server.py**
   - Line 113: Added `db_manager.connect()`

## Docker Commands

### Build and Start
```bash
docker-compose -f docker-compose.mcp.yml build
docker-compose -f docker-compose.mcp.yml up -d
```

### Check Status
```bash
docker-compose -f docker-compose.mcp.yml ps
docker-compose -f docker-compose.mcp.yml logs -f mcp-server
```

### Stop
```bash
docker-compose -f docker-compose.mcp.yml down
```

## Test Results

All tests passed:
- Container builds successfully
- Container starts and stays healthy
- Health check endpoint returns 200 OK
- MCP SSE endpoint responds with session info
- Database connection verified
- All 5 MCP tools registered and ready

## Next Steps

The MCP server is now ready for N8N integration:
1. Configure N8N to connect to `http://localhost:8002/sse`
2. Test tool invocations from N8N workflows
3. Monitor logs for any connection issues

## Performance Notes

- Container startup time: ~5 seconds
- Health check interval: 30 seconds
- Database: Read-only mount for safety
- Non-root user: mcpuser (uid 1000)
