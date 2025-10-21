#!/usr/bin/env python3
"""
Minimal HTTP health check server for MCP Server Docker healthcheck.

This server runs on port 8001 and provides a simple /health endpoint
that checks if the database connection is alive.

Usage:
    python health_server.py

    Or run in background as part of mcp_server.py startup.
"""

import logging
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
import threading
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from src.database.db_manager import DatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global database manager instance
db_manager = None


class HealthCheckHandler(BaseHTTPRequestHandler):
    """HTTP request handler for health checks."""

    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/health':
            self.handle_health_check()
        else:
            self.send_error(404, "Not Found")

    def handle_health_check(self):
        """Check database health and return status."""
        try:
            # Check if database manager is initialized
            if db_manager is None:
                self.send_health_response(503, {
                    "status": "unhealthy",
                    "database": "not_initialized",
                    "timestamp": datetime.utcnow().isoformat()
                })
                return

            # Try to execute a simple query to verify connection
            result = db_manager.execute_query("SELECT 1", ())

            if result and len(result) > 0:
                # Database connection is alive
                self.send_health_response(200, {
                    "status": "healthy",
                    "database": "connected",
                    "timestamp": datetime.utcnow().isoformat()
                })
            else:
                # Query failed
                self.send_health_response(503, {
                    "status": "unhealthy",
                    "database": "query_failed",
                    "timestamp": datetime.utcnow().isoformat()
                })

        except Exception as e:
            # Exception during health check
            logger.error(f"Health check failed: {e}")
            self.send_health_response(503, {
                "status": "unhealthy",
                "database": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            })

    def send_health_response(self, status_code, data):
        """Send JSON health response."""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def log_message(self, format, *args):
        """Override to use logger instead of stderr."""
        logger.info(f"{self.address_string()} - {format % args}")


def start_health_server(port=8001, db_path='data/processed/estimates.db'):
    """
    Start the health check HTTP server.

    Args:
        port: Port to listen on (default: 8001)
        db_path: Path to database file
    """
    global db_manager

    # Initialize database manager and connect
    try:
        db_manager = DatabaseManager(db_path)
        db_manager.connect()  # Explicitly connect to the database
        logger.info(f"Database manager initialized and connected: {db_path}")
    except Exception as e:
        logger.error(f"Failed to initialize database manager: {e}")
        db_manager = None

    # Start HTTP server
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    logger.info(f"Health check server listening on port {port}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Health check server shutting down...")
        server.shutdown()
        if db_manager:
            db_manager.disconnect()


def start_health_server_background(port=8001, db_path='data/processed/estimates.db'):
    """
    Start health server in background thread.

    Args:
        port: Port to listen on
        db_path: Path to database file

    Returns:
        Thread object
    """
    thread = threading.Thread(
        target=start_health_server,
        args=(port, db_path),
        daemon=True,
        name="HealthServer"
    )
    thread.start()
    logger.info(f"Health server started in background on port {port}")
    return thread


if __name__ == '__main__':
    # Run as standalone server
    import argparse

    parser = argparse.ArgumentParser(description='MCP Server Health Check')
    parser.add_argument('--port', type=int, default=8001, help='Port to listen on')
    parser.add_argument('--db', type=str, default='data/processed/estimates.db', help='Database path')

    args = parser.parse_args()

    start_health_server(port=args.port, db_path=args.db)
