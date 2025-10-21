"""
Rate Comparator Module for Construction Rates Management System

This module provides the RateComparator class for comparing construction rates
and finding alternatives using full-text search capabilities.
"""

import logging
import pandas as pd
from typing import List, Optional
from pathlib import Path

from src.database.db_manager import DatabaseManager
from src.database.fts_config import prepare_fts_query


# Configure logging
logger = logging.getLogger(__name__)


class RateComparator:
    """
    Compare construction rates and find alternatives using FTS5 search.

    This class provides functionality to:
    - Compare multiple rates by calculating costs for specific quantities
    - Find alternative rates using full-text search on similar descriptions
    - Calculate cost differences and provide comparative analysis

    Attributes:
        db_path (str): Path to the SQLite database file

    Example:
        >>> comparator = RateComparator('data/processed/estimates.db')
        >>> df = comparator.compare(['10-05-001-01', '10-06-037-02'], quantity=50)
        >>> alternatives = comparator.find_alternatives('10-05-001-01', max_results=5)
    """

    def __init__(self, db_path: str = 'data/processed/estimates.db'):
        """
        Initialize RateComparator with database path.

        Args:
            db_path: Path to the SQLite database file (default: data/processed/estimates.db)
        """
        self.db_path = db_path
        logger.info(f"RateComparator initialized with database: {db_path}")

    def compare(self, rate_codes: List[str], quantity: float) -> pd.DataFrame:
        """
        Compare multiple rates by calculating costs for a specific quantity.

        Args:
            rate_codes: List of rate codes to compare
            quantity: Quantity to calculate costs for (must be > 0)

        Returns:
            DataFrame with columns:
                - rate_code: Rate identifier
                - rate_full_name: Full descriptive name
                - unit_type: Unit of measurement
                - cost_per_unit: Cost for one unit
                - total_for_quantity: Total cost for specified quantity
                - materials_for_quantity: Materials cost for specified quantity
                - difference_from_cheapest: Difference from minimum in rubles
                - difference_percent: Difference from minimum in percentage

            Sorted by total_for_quantity (ascending)

        Raises:
            ValueError: If quantity <= 0 or rate_codes is empty
            ValueError: If any rate_code does not exist in database
            sqlite3.Error: If database query fails

        Example:
            >>> df = comparator.compare(['10-05-001-01', '10-06-037-02'], quantity=50)
            >>> print(df[['rate_code', 'total_for_quantity', 'difference_percent']])
        """
        # Validate inputs
        if not rate_codes:
            raise ValueError("rate_codes list cannot be empty")

        if quantity <= 0:
            raise ValueError(f"quantity must be greater than 0, got: {quantity}")

        logger.info(f"Comparing {len(rate_codes)} rates for quantity: {quantity}")

        # Build SQL query with placeholders
        placeholders = ','.join('?' * len(rate_codes))
        sql = f"""
            SELECT
                rate_code,
                rate_full_name,
                unit_type,
                unit_quantity,
                total_cost,
                materials_cost,
                resources_cost
            FROM rates
            WHERE rate_code IN ({placeholders})
        """

        # Execute query
        with DatabaseManager(self.db_path) as db:
            results = db.execute_query(sql, tuple(rate_codes))

        # Validate that all rate_codes exist
        if len(results) != len(rate_codes):
            found_codes = {row[0] for row in results}
            missing_codes = set(rate_codes) - found_codes
            raise ValueError(f"Rate codes not found in database: {', '.join(missing_codes)}")

        logger.debug(f"Retrieved {len(results)} rates from database")

        # Build DataFrame with calculations
        data = []
        for row in results:
            rate_code, rate_full_name, unit_type, unit_quantity, total_cost, materials_cost, resources_cost = row

            # Calculate cost per unit
            cost_per_unit = total_cost / unit_quantity if unit_quantity > 0 else 0

            # Calculate totals for specified quantity
            total_for_quantity = cost_per_unit * quantity
            materials_for_quantity = (materials_cost / unit_quantity) * quantity if unit_quantity > 0 else 0

            data.append({
                'rate_code': rate_code,
                'rate_full_name': rate_full_name,
                'unit_type': unit_type,
                'cost_per_unit': round(cost_per_unit, 2),
                'total_for_quantity': round(total_for_quantity, 2),
                'materials_for_quantity': round(materials_for_quantity, 2)
            })

        # Create DataFrame
        df = pd.DataFrame(data)

        # Sort by total cost
        df = df.sort_values('total_for_quantity', ascending=True).reset_index(drop=True)

        # Calculate difference from cheapest
        if len(df) > 0:
            min_cost = df['total_for_quantity'].min()

            df['difference_from_cheapest'] = (df['total_for_quantity'] - min_cost).round(2)

            # Calculate percentage difference (avoid division by zero)
            if min_cost > 0:
                df['difference_percent'] = ((df['total_for_quantity'] - min_cost) / min_cost * 100).round(2)
            else:
                df['difference_percent'] = 0.0

        logger.info(f"Comparison completed: {len(df)} rates analyzed")

        return df

    def find_alternatives(self, rate_code: str, max_results: int = 5) -> pd.DataFrame:
        """
        Find similar rates using full-text search on rate descriptions.

        Uses FTS5 full-text search to find rates with similar search_text content.
        Extracts keywords from the source rate and searches for matching rates,
        excluding the source rate itself from results.

        Args:
            rate_code: Source rate code to find alternatives for
            max_results: Maximum number of alternative rates to return (default: 5)

        Returns:
            DataFrame with same format as compare() method, showing alternatives
            sorted by FTS5 rank (most relevant first), then by total_for_quantity

        Raises:
            ValueError: If rate_code does not exist in database
            ValueError: If max_results <= 0
            sqlite3.Error: If database query fails

        Example:
            >>> df = comparator.find_alternatives('10-05-001-01', max_results=5)
            >>> print(df[['rate_code', 'rate_full_name', 'difference_percent']])
        """
        # Validate inputs
        if max_results <= 0:
            raise ValueError(f"max_results must be greater than 0, got: {max_results}")

        logger.info(f"Finding alternatives for rate: {rate_code}, max_results: {max_results}")

        with DatabaseManager(self.db_path) as db:
            # Get source rate and its search_text
            source_sql = """
                SELECT
                    rate_code,
                    rate_full_name,
                    unit_type,
                    unit_quantity,
                    total_cost,
                    materials_cost,
                    resources_cost,
                    search_text
                FROM rates
                WHERE rate_code = ?
            """

            source_results = db.execute_query(source_sql, (rate_code,))

            if not source_results:
                raise ValueError(f"Rate code not found in database: {rate_code}")

            source_row = source_results[0]
            (source_code, source_name, source_unit_type, source_unit_quantity,
             source_total_cost, source_materials_cost, source_resources_cost, search_text) = source_row

            logger.debug(f"Source rate: {source_code} - {source_name}")

            # Extract keywords from search_text for FTS5 query
            # Use the full search_text as the query (FTS5 will tokenize and rank)
            fts_query = self._extract_keywords(search_text)

            logger.debug(f"FTS5 query: {fts_query[:100]}...")

            # Find similar rates using FTS5, excluding source rate
            # Note: We add +1 to max_results to account for potential inclusion of source rate
            alternatives_sql = """
                SELECT
                    r.rate_code,
                    r.rate_full_name,
                    r.unit_type,
                    r.unit_quantity,
                    r.total_cost,
                    r.materials_cost,
                    r.resources_cost,
                    fts.rank
                FROM rates r
                JOIN rates_fts fts ON r.rowid = fts.rowid
                WHERE rates_fts MATCH ?
                  AND r.rate_code != ?
                ORDER BY fts.rank, r.total_cost
                LIMIT ?
            """

            alternatives_results = db.execute_query(
                alternatives_sql,
                (fts_query, rate_code, max_results)
            )

            logger.debug(f"Found {len(alternatives_results)} alternative rates")

        # Handle empty results
        if not alternatives_results:
            logger.warning(f"No alternatives found for rate: {rate_code}")
            # Return empty DataFrame with correct schema
            return pd.DataFrame(columns=[
                'rate_code', 'rate_full_name', 'unit_type', 'cost_per_unit',
                'total_for_quantity', 'materials_for_quantity',
                'difference_from_cheapest', 'difference_percent'
            ])

        # Build DataFrame with source rate unit_quantity for comparison
        # We'll use source rate's unit_quantity as the comparison quantity
        comparison_quantity = source_unit_quantity

        data = []
        for row in alternatives_results:
            rate_code_alt, rate_full_name, unit_type, unit_quantity, total_cost, materials_cost, resources_cost, rank = row

            # Calculate cost per unit
            cost_per_unit = total_cost / unit_quantity if unit_quantity > 0 else 0

            # Calculate totals for comparison quantity
            total_for_quantity = cost_per_unit * comparison_quantity
            materials_for_quantity = (materials_cost / unit_quantity) * comparison_quantity if unit_quantity > 0 else 0

            data.append({
                'rate_code': rate_code_alt,
                'rate_full_name': rate_full_name,
                'unit_type': unit_type,
                'cost_per_unit': round(cost_per_unit, 2),
                'total_for_quantity': round(total_for_quantity, 2),
                'materials_for_quantity': round(materials_for_quantity, 2),
                'fts_rank': rank
            })

        # Add source rate to comparison for reference
        source_cost_per_unit = source_total_cost / source_unit_quantity if source_unit_quantity > 0 else 0
        source_total_for_quantity = source_cost_per_unit * comparison_quantity
        source_materials_for_quantity = (source_materials_cost / source_unit_quantity) * comparison_quantity if source_unit_quantity > 0 else 0

        data.insert(0, {
            'rate_code': source_code,
            'rate_full_name': source_name,
            'unit_type': source_unit_type,
            'cost_per_unit': round(source_cost_per_unit, 2),
            'total_for_quantity': round(source_total_for_quantity, 2),
            'materials_for_quantity': round(source_materials_for_quantity, 2),
            'fts_rank': 0  # Source rate gets best rank for sorting
        })

        # Create DataFrame
        df = pd.DataFrame(data)

        # Sort by total cost
        df = df.sort_values('total_for_quantity', ascending=True).reset_index(drop=True)

        # Calculate difference from cheapest (which might be source or an alternative)
        min_cost = df['total_for_quantity'].min()

        df['difference_from_cheapest'] = (df['total_for_quantity'] - min_cost).round(2)

        # Calculate percentage difference
        if min_cost > 0:
            df['difference_percent'] = ((df['total_for_quantity'] - min_cost) / min_cost * 100).round(2)
        else:
            df['difference_percent'] = 0.0

        # Drop fts_rank column (internal use only)
        df = df.drop(columns=['fts_rank'])

        logger.info(f"Found {len(df)} alternatives (including source rate)")

        return df

    def _extract_keywords(self, search_text: Optional[str]) -> str:
        """
        Extract keywords from search_text for FTS5 similarity query.

        For similarity search, we want to be less restrictive than full-text search.
        Strategy:
        1. Normalize and remove stopwords
        2. Take first 3-5 important keywords (enough to find similar rates, not too restrictive)
        3. Apply synonym expansion and wildcards
        4. Use AND to require all keywords (ensures relevance)

        Args:
            search_text: Full search text from rate

        Returns:
            FTS5 query string ready for MATCH clause

        Example:
            >>> query = self._extract_keywords("Устройство перегородок гипсокартонных на каркасе...")
            >>> # Returns: "устройство* AND перегородок* AND (гипсокартон* OR гкл*)"
        """
        if not search_text:
            logger.warning("Empty search_text provided, using wildcard query")
            return "*"

        # Clean up search text: remove extra whitespace
        keywords = ' '.join(search_text.split())

        # Limit to first few words to avoid overly restrictive queries
        # For similarity search, we want the most important/descriptive terms
        words = keywords.split()

        # Take first 2-3 keywords only - this is key for similarity search
        # Using too many keywords makes the query too restrictive
        max_keywords = 3
        if len(words) > max_keywords:
            keywords = ' '.join(words[:max_keywords])
            logger.debug(f"Limited similarity search to first {max_keywords} keywords: {keywords[:50]}...")

        # Use prepare_fts_query for proper FTS5 formatting
        try:
            fts_query = prepare_fts_query(keywords)
            return fts_query
        except ValueError as e:
            logger.warning(f"Failed to prepare FTS query from search_text: {e}, using cleaned keywords")
            # Fallback to cleaned keywords if preparation fails
            return keywords
