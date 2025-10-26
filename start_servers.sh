#!/bin/bash

# Start both MCP server and FastAPI server
# MCP server on port 8000, FastAPI on port 8001

echo "Starting MCP server on port 8000..."
python mcp_server.py &
MCP_PID=$!

echo "Starting FastAPI server on port 8001..."
PORT=8001 python api_server.py &
API_PID=$!

echo "MCP server PID: $MCP_PID"
echo "API server PID: $API_PID"

# Wait for any process to exit
wait -n

# Exit with status of process that exited first
exit $?
