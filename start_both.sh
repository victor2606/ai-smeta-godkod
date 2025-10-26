#!/bin/bash
set -e

echo "Starting FastAPI server on port 8000..."
DATABASE_PATH=${DB_PATH} PORT=8000 python api_server.py &
API_PID=$!

echo "FastAPI server started (PID: $API_PID) on port 8000"

# Function to handle shutdown
cleanup() {
    echo "Shutting down server..."
    kill $API_PID 2>/dev/null
    wait $API_PID 2>/dev/null
    echo "Server stopped"
    exit 0
}

trap cleanup SIGTERM SIGINT

# Wait for API server
wait $API_PID
