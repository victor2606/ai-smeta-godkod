"""
Search Engine Module for Construction Rates Full-Text Search

This module provides the SearchEngine class that implements full-text search
functionality for construction rates using SQLite FTS5 and vector embeddings.
"""

import sqlite3
import logging
from typing import Dict, List, Optional, Any

from src.database.db_manager import DatabaseManager
from src.database.fts_config import prepare_fts_query
from src.search.vector_engine import VectorSearchEngine


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

    def __init__(
        self,
        db_manager: DatabaseManager,
        openai_api_key: Optional[str] = None,
        openai_base_url: Optional[str] = None,
    ):
        """
        Initialize SearchEngine with database manager and optional vector search.

        Args:
            db_manager: DatabaseManager instance for database operations
            openai_api_key: Optional OpenAI API key for vector search. If provided,
                          enables semantic vector search in addition to FTS5.
            openai_base_url: Optional custom OpenAI API base URL. If not provided,
                           will use OPENAI_BASE_URL environment variable or OpenAI default.
        """
        self.db_manager = db_manager
        self.vector_engine = None

        if openai_api_key:
            try:
                self.vector_engine = VectorSearchEngine(
                    db_manager, api_key=openai_api_key, base_url=openai_base_url
                )
                logger.info("SearchEngine initialized with FTS5 + Vector search")
            except Exception as e:
                logger.warning(
                    f"Failed to initialize vector search: {e}. Using FTS5 only."
                )
        else:
            logger.info("SearchEngine initialized with FTS5 only")

    def search(
        self, query: str, filters: Optional[Dict[str, Any]] = None, limit: int = 100
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
            if "unit_type" in filters and filters["unit_type"]:
                sql += " AND r.unit_type = ?"
                params.append(filters["unit_type"])
                logger.debug(f"Applied unit_type filter: {filters['unit_type']}")

            if "min_cost" in filters and filters["min_cost"] is not None:
                sql += " AND r.total_cost >= ?"
                params.append(filters["min_cost"])
                logger.debug(f"Applied min_cost filter: {filters['min_cost']}")

            if "max_cost" in filters and filters["max_cost"] is not None:
                sql += " AND r.total_cost <= ?"
                params.append(filters["max_cost"])
                logger.debug(f"Applied max_cost filter: {filters['max_cost']}")

            if "category" in filters and filters["category"]:
                sql += " AND r.category = ?"
                params.append(filters["category"])
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
                (
                    rate_code,
                    rate_full_name,
                    unit_quantity,
                    unit_type,
                    total_cost,
                    rank,
                ) = row

                # Calculate cost per unit
                cost_per_unit = total_cost / unit_quantity if unit_quantity > 0 else 0

                # Build unit measure full description
                unit_measure_full = f"{unit_quantity} {unit_type}"

                results.append(
                    {
                        "rate_code": rate_code,
                        "rate_full_name": rate_full_name,
                        "unit_measure_full": unit_measure_full,
                        "unit_type": unit_type,
                        "cost_per_unit": round(cost_per_unit, 2),
                        "total_cost": round(total_cost, 2),
                        "rank": round(rank, 4),
                    }
                )

            logger.info(f"Search completed: {len(results)} results found")

            if len(results) == 0:
                logger.info(f"No results found for query: '{query}'")

            return results

        except sqlite3.Error as e:
            error_msg = f"Database error during search: {str(e)}"
            logger.error(error_msg)
            raise sqlite3.Error(error_msg) from e

    def vector_search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10,
        similarity_threshold: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic vector search on construction rates.

        Uses OpenAI embeddings for semantic similarity search. Returns results
        ranked by cosine similarity to the query.

        Args:
            query: Natural language search query (e.g., "бетонные работы")
            filters: Optional dict with filter criteria:
                - unit_type (str): Filter by unit type
                - min_cost (float): Minimum cost per unit
                - max_cost (float): Maximum cost per unit
            limit: Maximum number of results (default: 10, max: 100)
            similarity_threshold: Minimum cosine similarity 0-1 (default: 0.0)

        Returns:
            List of dicts with keys:
                - rate_code: Rate identifier code
                - rate_full_name: Full descriptive name
                - unit_type: Unit of measurement
                - cost_per_unit: Cost per single unit
                - total_cost: Total cost for the rate
                - similarity: Cosine similarity score (0-1, higher = better)

        Raises:
            RuntimeError: If vector search is not enabled (no API key provided)
            ValueError: If query is empty or invalid

        Examples:
            >>> # Semantic search
            >>> results = search_engine.vector_search("бетонные работы")

            >>> # With filters
            >>> results = search_engine.vector_search(
            ...     "укладка асфальта",
            ...     filters={"min_cost": 1000},
            ...     limit=5,
            ...     similarity_threshold=0.5
            ... )
        """
        if not self.vector_engine:
            raise RuntimeError(
                "Vector search is not enabled. Initialize SearchEngine with "
                "openai_api_key parameter to enable semantic search."
            )

        if not query or not query.strip():
            raise ValueError("Search query cannot be empty")

        logger.info(f"Vector search query: '{query}'")

        try:
            results = self.vector_engine.search(
                query=query,
                limit=min(limit, 100),
                filters=filters,
                similarity_threshold=similarity_threshold,
            )

            logger.info(f"Vector search completed: {len(results)} results found")
            return results

        except Exception as e:
            error_msg = f"Vector search failed: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def hybrid_search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        fts_limit: int = 50,
        vector_limit: int = 10,
        similarity_threshold: float = 0.3,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Perform hybrid search combining FTS5 and vector search.

        Returns results from both search methods, allowing comparison and
        combination of keyword-based and semantic search.

        Args:
            query: Search query
            filters: Optional filter criteria
            fts_limit: Max results from FTS5 search (default: 50)
            vector_limit: Max results from vector search (default: 10)
            similarity_threshold: Min similarity for vector results (default: 0.3)

        Returns:
            Dict with keys:
                - fts_results: Results from FTS5 full-text search
                - vector_results: Results from semantic vector search
                - combined: Merged and deduplicated results (if vector search enabled)

        Raises:
            ValueError: If query is empty

        Examples:
            >>> results = search_engine.hybrid_search("бетонные работы")
            >>> print(f"FTS5 found: {len(results['fts_results'])}")
            >>> print(f"Vector found: {len(results['vector_results'])}")
        """
        if not query or not query.strip():
            raise ValueError("Search query cannot be empty")

        logger.info(f"Hybrid search query: '{query}'")

        # Always perform FTS5 search
        fts_results = self.search(query, filters=filters, limit=fts_limit)

        result = {
            "fts_results": fts_results,
            "vector_results": [],
            "combined": fts_results,
        }

        # Perform vector search if available
        if self.vector_engine:
            try:
                vector_results = self.vector_search(
                    query,
                    filters=filters,
                    limit=vector_limit,
                    similarity_threshold=similarity_threshold,
                )
                result["vector_results"] = vector_results

                # Combine results (deduplicate by rate_code)
                seen_codes = set()
                combined = []

                # Add vector results first (higher priority for semantic relevance)
                for r in vector_results:
                    code = r.get("rate_code")
                    if code not in seen_codes:
                        combined.append(r)
                        seen_codes.add(code)

                # Add FTS results that aren't already included
                for r in fts_results:
                    code = r.get("rate_code")
                    if code not in seen_codes:
                        combined.append(r)
                        seen_codes.add(code)

                result["combined"] = combined

            except Exception as e:
                logger.warning(f"Vector search failed in hybrid mode: {e}")

        logger.info(
            f"Hybrid search completed: {len(result['fts_results'])} FTS, "
            f"{len(result['vector_results'])} vector, "
            f"{len(result['combined'])} combined"
        )

        return result

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
                code, full_name, unit_quantity, unit_type, total_cost = row

                # Calculate cost per unit
                cost_per_unit = total_cost / unit_quantity if unit_quantity > 0 else 0

                # Build unit measure full description
                unit_measure_full = f"{unit_quantity} {unit_type}"

                results.append(
                    {
                        "rate_code": code,
                        "rate_full_name": full_name,
                        "unit_measure_full": unit_measure_full,
                        "cost_per_unit": round(cost_per_unit, 2),
                        "total_cost": round(total_cost, 2),
                        "rank": 0,  # No FTS ranking for code-based search
                    }
                )

            logger.info(f"Code search completed: {len(results)} results found")

            if len(results) == 0:
                logger.info(f"No rates found with code prefix: '{rate_code}'")

            return results

        except sqlite3.Error as e:
            error_msg = f"Database error during code search: {str(e)}"
            logger.error(error_msg)
            raise sqlite3.Error(error_msg) from e
