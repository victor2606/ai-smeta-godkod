"""
Search Engine Module for Construction Rates Full-Text Search

This module provides the SearchEngine class that implements full-text search
functionality for construction rates using SQLite FTS5.
"""

import sqlite3
import logging
from typing import Dict, List, Optional, Any

from src.database.db_manager import DatabaseManager
from src.database.fts_config import prepare_fts_query


# Configure logging
logger = logging.getLogger(__name__)


class SearchEngine:
    """
    Full-text search engine for construction rates.

    Provides methods for searching construction rates using FTS5 full-text search
    and prefix matching by rate codes.

    Attributes:
        db_manager (DatabaseManager): Database manager instance for executing queries

    Example:
        >>> from src.database.db_manager import DatabaseManager
        >>> db = DatabaseManager('data/processed/estimates.db')
        >>> search_engine = SearchEngine(db)
        >>> results = search_engine.search("бетон монолитный")
        >>> code_results = search_engine.search_by_code("ГЭСНп81-01")
    """

    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize SearchEngine with database manager.

        Args:
            db_manager: DatabaseManager instance for database operations
        """
        self.db_manager = db_manager
        logger.info("SearchEngine initialized")

    def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Perform full-text search on construction rates.

        This method uses SQLite FTS5 for full-text search with Russian language support.
        The query is automatically processed for optimal matching (stopwords removal,
        synonym expansion, wildcard matching).

        Args:
            query: Russian text search query (e.g., "бетон монолитный")
            filters: Optional dict with filter criteria:
                - unit_type (str): Filter by unit type (e.g., "м3", "м2", "т")
                - min_cost (float): Minimum total cost
                - max_cost (float): Maximum total cost
                - category (str): Filter by category code
            limit: Maximum number of results to return (default: 100, max: 1000)

        Returns:
            List of dicts with keys:
                - rate_code: Rate identifier code
                - rate_full_name: Full descriptive name
                - rate_short_name: Short name
                - unit_measure_full: Full unit description (unit_quantity + unit_type)
                - cost_per_unit: Cost per single unit (total_cost / unit_quantity)
                - total_cost: Total cost for the rate
                - rank: FTS5 relevance score (negative float, lower = better match)

        Raises:
            ValueError: If query is empty or invalid
            sqlite3.Error: If database query fails

        Examples:
            >>> # Simple search
            >>> results = search_engine.search("бетон монолитный")

            >>> # Search with filters
            >>> results = search_engine.search(
            ...     "устройство перегородок",
            ...     filters={"unit_type": "м2", "min_cost": 1000, "max_cost": 5000}
            ... )
        """
        if not query or not query.strip():
            logger.error("Empty search query provided")
            raise ValueError("Search query cannot be empty")

        # Prepare FTS query using fts_config module
        try:
            fts_query = prepare_fts_query(query)
            logger.info(f"Searching with query: '{query}' -> FTS: '{fts_query}'")
        except ValueError as e:
            logger.error(f"Failed to prepare FTS query: {e}")
            raise

        # Build SQL query with JOIN
        sql = """
            SELECT
                r.rate_code,
                r.rate_full_name,
                r.rate_short_name,
                r.unit_quantity,
                r.unit_type,
                r.total_cost,
                fts.rank
            FROM rates r
            JOIN rates_fts fts ON r.rowid = fts.rowid
            WHERE rates_fts MATCH ?
        """

        # List to hold query parameters
        params = [fts_query]

        # Add optional filters
        if filters:
            if 'unit_type' in filters and filters['unit_type']:
                sql += " AND r.unit_type = ?"
                params.append(filters['unit_type'])
                logger.debug(f"Applied unit_type filter: {filters['unit_type']}")

            if 'min_cost' in filters and filters['min_cost'] is not None:
                sql += " AND r.total_cost >= ?"
                params.append(filters['min_cost'])
                logger.debug(f"Applied min_cost filter: {filters['min_cost']}")

            if 'max_cost' in filters and filters['max_cost'] is not None:
                sql += " AND r.total_cost <= ?"
                params.append(filters['max_cost'])
                logger.debug(f"Applied max_cost filter: {filters['max_cost']}")

            if 'category' in filters and filters['category']:
                sql += " AND r.category = ?"
                params.append(filters['category'])
                logger.debug(f"Applied category filter: {filters['category']}")

        # Add ordering and limit
        sql += " ORDER BY rank LIMIT ?"

        # Cap limit at 1000
        actual_limit = min(limit, 1000)
        params.append(actual_limit)

        # Execute query
        try:
            rows = self.db_manager.execute_query(sql, tuple(params))

            # Check if result count exceeds 1000
            if len(rows) >= 1000:
                logger.warning(
                    f"Search returned maximum limit (1000 results). "
                    f"Query: '{query}'. Consider refining search criteria."
                )

            # Transform results to dict format
            results = []
            for row in rows:
                rate_code, rate_full_name, rate_short_name, unit_quantity, unit_type, total_cost, rank = row

                # Calculate cost per unit
                cost_per_unit = total_cost / unit_quantity if unit_quantity > 0 else 0

                # Build unit measure full description
                unit_measure_full = f"{unit_quantity} {unit_type}"

                results.append({
                    'rate_code': rate_code,
                    'rate_full_name': rate_full_name,
                    'rate_short_name': rate_short_name,
                    'unit_measure_full': unit_measure_full,
                    'cost_per_unit': round(cost_per_unit, 2),
                    'total_cost': round(total_cost, 2),
                    'rank': round(rank, 4)
                })

            logger.info(f"Search completed: {len(results)} results found")

            if len(results) == 0:
                logger.info(f"No results found for query: '{query}'")

            return results

        except sqlite3.Error as e:
            error_msg = f"Database error during search: {str(e)}"
            logger.error(error_msg)
            raise sqlite3.Error(error_msg) from e

    def search_by_code(self, rate_code: str) -> List[Dict[str, Any]]:
        """
        Search construction rates by rate code prefix.

        Performs prefix matching using SQL LIKE operator to find all rates
        that start with the given code pattern.

        Args:
            rate_code: Rate code prefix to search for (e.g., "ГЭСНп81-01")

        Returns:
            List of dicts with same structure as search() method:
                - rate_code: Rate identifier code
                - rate_full_name: Full descriptive name
                - rate_short_name: Short name
                - unit_measure_full: Full unit description
                - cost_per_unit: Cost per single unit
                - total_cost: Total cost for the rate
                - rank: Always 0 for code-based searches (not FTS)

        Raises:
            ValueError: If rate_code is empty
            sqlite3.Error: If database query fails

        Examples:
            >>> # Find all rates starting with "ГЭСНп81-01"
            >>> results = search_engine.search_by_code("ГЭСНп81-01")

            >>> # Find specific rate
            >>> results = search_engine.search_by_code("ГЭСНп81-01-001-01")
        """
        if not rate_code or not rate_code.strip():
            logger.error("Empty rate_code provided")
            raise ValueError("Rate code cannot be empty")

        rate_code = rate_code.strip()
        logger.info(f"Searching by rate code prefix: '{rate_code}'")

        # Build SQL query with LIKE for prefix matching
        sql = """
            SELECT
                rate_code,
                rate_full_name,
                rate_short_name,
                unit_quantity,
                unit_type,
                total_cost
            FROM rates
            WHERE rate_code LIKE ?
            ORDER BY rate_code
        """

        # Add wildcard for prefix matching
        search_pattern = f"{rate_code}%"

        try:
            rows = self.db_manager.execute_query(sql, (search_pattern,))

            # Transform results to dict format
            results = []
            for row in rows:
                code, full_name, short_name, unit_quantity, unit_type, total_cost = row

                # Calculate cost per unit
                cost_per_unit = total_cost / unit_quantity if unit_quantity > 0 else 0

                # Build unit measure full description
                unit_measure_full = f"{unit_quantity} {unit_type}"

                results.append({
                    'rate_code': code,
                    'rate_full_name': full_name,
                    'rate_short_name': short_name,
                    'unit_measure_full': unit_measure_full,
                    'cost_per_unit': round(cost_per_unit, 2),
                    'total_cost': round(total_cost, 2),
                    'rank': 0  # No FTS ranking for code-based search
                })

            logger.info(f"Code search completed: {len(results)} results found")

            if len(results) == 0:
                logger.info(f"No rates found with code prefix: '{rate_code}'")

            return results

        except sqlite3.Error as e:
            error_msg = f"Database error during code search: {str(e)}"
            logger.error(error_msg)
            raise sqlite3.Error(error_msg) from e
