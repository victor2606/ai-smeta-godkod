#!/bin/bash
set -e

echo "Starting MCP server on port 8000..."
python mcp_server.py &
MCP_PID=$!

echo "Waiting 2 seconds for MCP server to start..."
sleep 2

echo "Starting FastAPI server on port 8002..."
DATABASE_PATH=${DB_PATH} PORT=8002 python api_server.py &
API_PID=$!

echo "Starting nginx on port 8080..."
nginx -g 'daemon off;' &
NGINX_PID=$!

echo "All services started:"
echo "  - MCP server (PID: $MCP_PID) on port 8000"
echo "  - FastAPI server (PID: $API_PID) on port 8002"
echo "  - Nginx (PID: $NGINX_PID) on port 8080"
echo ""
echo "External access via nginx:"
echo "  http://localhost:8080/mcp -> MCP server"
echo "  http://localhost:8080/api -> FastAPI server"
echo "  http://localhost:8080/health -> Health check"

# Function to handle shutdown
cleanup() {
    echo "Shutting down all services..."
    kill $MCP_PID $API_PID $NGINX_PID 2>/dev/null
    wait $MCP_PID $API_PID $NGINX_PID 2>/dev/null
    echo "All services stopped"
    exit 0
}

trap cleanup SIGTERM SIGINT

# Wait for any process to exit
wait -n

# If one exits, kill the others
kill $MCP_PID $API_PID $NGINX_PID 2>/dev/null
wait
