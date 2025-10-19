"""
Database Manager for Construction Rates Management System

This module provides a DatabaseManager class for managing SQLite connections
with optimized settings for full-text search and construction rate data.
"""

import sqlite3
import logging
import os
from pathlib import Path
from typing import List, Tuple, Any, Optional


# Configure logging
logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages SQLite database connections with context manager support.

    Features:
    - Context manager protocol for automatic resource cleanup
    - WAL (Write-Ahead Logging) mode for better concurrency
    - Optimized PRAGMA settings for performance
    - Schema initialization from SQL file
    - Comprehensive error handling and logging

    Attributes:
        db_path (str): Path to the SQLite database file
        connection (sqlite3.Connection): Active database connection
        cursor (sqlite3.Cursor): Database cursor for query execution

    Example:
        >>> with DatabaseManager('data/processed/estimates.db') as db:
        ...     db.initialize_schema()
        ...     results = db.execute_query("SELECT * FROM rates WHERE unit_type = ?", ("м2",))
    """

    def __init__(self, db_path: str):
        """
        Initialize DatabaseManager with database path.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.connection: Optional[sqlite3.Connection] = None
        self.cursor: Optional[sqlite3.Cursor] = None
        self._is_new_database = not os.path.exists(db_path)

        logger.info(f"DatabaseManager initialized for: {db_path}")
        if self._is_new_database:
            logger.info("Database file does not exist - will be created on first connection")

    def __enter__(self):
        """
        Context manager entry - establishes database connection.

        Returns:
            DatabaseManager: Self reference for context usage
        """
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Context manager exit - ensures proper cleanup.

        Args:
            exc_type: Exception type if error occurred
            exc_val: Exception value if error occurred
            exc_tb: Exception traceback if error occurred
        """
        self.disconnect()

        # Return False to propagate any exceptions
        return False

    def connect(self) -> None:
        """
        Establish connection to SQLite database and configure optimizations.

        Creates parent directories if needed and applies performance PRAGMA settings:
        - WAL mode for better concurrency
        - Optimized synchronous mode
        - Increased cache size
        - Foreign key constraints enabled

        Raises:
            sqlite3.Error: If connection fails
        """
        try:
            # Create parent directories if they don't exist
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
                logger.info(f"Created directory: {db_dir}")

            # Establish connection
            self.connection = sqlite3.connect(self.db_path)
            self.cursor = self.connection.cursor()

            logger.info(f"Database connection established: {self.db_path}")

            # Configure SQLite optimizations
            self._configure_pragmas()

            if self._is_new_database:
                logger.info("New database created successfully")

        except sqlite3.Error as e:
            error_msg = f"Failed to connect to database {self.db_path}: {str(e)}"
            logger.error(error_msg)
            raise sqlite3.Error(error_msg) from e

    def _configure_pragmas(self) -> None:
        """
        Configure SQLite PRAGMA settings for optimal performance.

        Settings applied:
        - journal_mode=WAL: Write-Ahead Logging for better concurrency
        - synchronous=NORMAL: Balance between safety and speed
        - cache_size=-64000: ~64MB cache for better performance
        - foreign_keys=ON: Enable foreign key constraints
        """
        pragma_settings = {
            'journal_mode': 'WAL',
            'synchronous': 'NORMAL',
            'cache_size': -64000,  # Negative value = KB (64MB)
            'foreign_keys': 'ON'
        }

        for pragma, value in pragma_settings.items():
            try:
                self.cursor.execute(f"PRAGMA {pragma} = {value}")
                result = self.cursor.fetchone()
                logger.debug(f"PRAGMA {pragma} set to {value}, confirmed: {result}")
            except sqlite3.Error as e:
                logger.warning(f"Failed to set PRAGMA {pragma}: {str(e)}")

        logger.info("Database PRAGMA settings configured successfully")

    def disconnect(self) -> None:
        """
        Close database connection and clean up resources.

        Commits any pending transactions before closing.
        """
        if self.connection:
            try:
                # Commit any pending transactions
                self.connection.commit()

                # Close cursor
                if self.cursor:
                    self.cursor.close()
                    self.cursor = None

                # Close connection
                self.connection.close()
                self.connection = None

                logger.info("Database connection closed successfully")

            except sqlite3.Error as e:
                logger.error(f"Error during disconnect: {str(e)}")
                raise

    def initialize_schema(self) -> None:
        """
        Read and execute SQL schema from schema.sql file.

        Reads the schema file located at src/database/schema.sql and executes
        all SQL statements to create tables, indexes, triggers, and views.

        Raises:
            FileNotFoundError: If schema.sql file is not found
            sqlite3.Error: If schema execution fails
        """
        # Determine schema file path relative to this file
        current_dir = Path(__file__).parent
        schema_path = current_dir / 'schema.sql'

        if not schema_path.exists():
            error_msg = f"Schema file not found: {schema_path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        try:
            logger.info(f"Reading schema from: {schema_path}")

            # Read schema file
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema_sql = f.read()

            logger.info(f"Executing schema (size: {len(schema_sql)} bytes)")

            # Execute schema (executescript handles multiple statements)
            self.cursor.executescript(schema_sql)
            self.connection.commit()

            logger.info("Database schema initialized successfully")

            # Log created tables for verification
            self.cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = [row[0] for row in self.cursor.fetchall()]
            logger.info(f"Created tables: {', '.join(tables)}")

        except FileNotFoundError:
            raise
        except sqlite3.Error as e:
            error_msg = f"Failed to initialize schema: {str(e)}"
            logger.error(error_msg)
            self.connection.rollback()
            raise sqlite3.Error(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error during schema initialization: {str(e)}"
            logger.error(error_msg)
            self.connection.rollback()
            raise

    def execute_query(
        self,
        sql: str,
        params: Optional[Tuple[Any, ...]] = None
    ) -> List[Tuple[Any, ...]]:
        """
        Execute a SELECT query and return results.

        Args:
            sql: SQL query string (use ? for parameters)
            params: Optional tuple of parameters for the query

        Returns:
            List of tuples containing query results

        Raises:
            sqlite3.Error: If query execution fails

        Example:
            >>> results = db.execute_query(
            ...     "SELECT * FROM rates WHERE unit_type = ?",
            ...     ("м2",)
            ... )
        """
        if not self.connection or not self.cursor:
            error_msg = "Database not connected. Use connect() or context manager."
            logger.error(error_msg)
            raise sqlite3.Error(error_msg)

        try:
            if params:
                self.cursor.execute(sql, params)
                logger.debug(f"Executed query with params: {sql[:100]}...")
            else:
                self.cursor.execute(sql)
                logger.debug(f"Executed query: {sql[:100]}...")

            results = self.cursor.fetchall()
            logger.debug(f"Query returned {len(results)} rows")

            return results

        except sqlite3.Error as e:
            error_msg = f"Query execution failed: {str(e)}\nSQL: {sql[:200]}"
            logger.error(error_msg)
            raise sqlite3.Error(error_msg) from e

    def execute_many(
        self,
        sql: str,
        data_list: List[Tuple[Any, ...]]
    ) -> int:
        """
        Execute batch INSERT/UPDATE operations with transaction support.

        Args:
            sql: SQL statement (INSERT, UPDATE, etc.)
            data_list: List of tuples containing parameter values

        Returns:
            Number of rows affected

        Raises:
            sqlite3.Error: If batch execution fails

        Example:
            >>> data = [
            ...     ("10-05-001-01", "Перегородки", 100, "м2", 138320.18),
            ...     ("10-06-037-02", "Перегородки двухслойные", 100, "м2", 197123.59)
            ... ]
            >>> db.execute_many("INSERT INTO rates VALUES (?, ?, ?, ?, ?)", data)
        """
        if not self.connection or not self.cursor:
            error_msg = "Database not connected. Use connect() or context manager."
            logger.error(error_msg)
            raise sqlite3.Error(error_msg)

        try:
            logger.info(f"Executing batch operation: {len(data_list)} records")

            # Use transaction for batch operations
            self.cursor.executemany(sql, data_list)
            self.connection.commit()

            rows_affected = self.cursor.rowcount
            logger.info(f"Batch operation completed: {rows_affected} rows affected")

            return rows_affected

        except sqlite3.Error as e:
            error_msg = f"Batch execution failed: {str(e)}\nSQL: {sql[:200]}"
            logger.error(error_msg)
            self.connection.rollback()
            raise sqlite3.Error(error_msg) from e

    def execute_update(
        self,
        sql: str,
        params: Optional[Tuple[Any, ...]] = None
    ) -> int:
        """
        Execute an INSERT/UPDATE/DELETE statement.

        Args:
            sql: SQL statement
            params: Optional tuple of parameters

        Returns:
            Number of rows affected

        Raises:
            sqlite3.Error: If execution fails
        """
        if not self.connection or not self.cursor:
            error_msg = "Database not connected. Use connect() or context manager."
            logger.error(error_msg)
            raise sqlite3.Error(error_msg)

        try:
            if params:
                self.cursor.execute(sql, params)
            else:
                self.cursor.execute(sql)

            self.connection.commit()
            rows_affected = self.cursor.rowcount

            logger.debug(f"Update executed: {rows_affected} rows affected")
            return rows_affected

        except sqlite3.Error as e:
            error_msg = f"Update execution failed: {str(e)}\nSQL: {sql[:200]}"
            logger.error(error_msg)
            self.connection.rollback()
            raise sqlite3.Error(error_msg) from e
