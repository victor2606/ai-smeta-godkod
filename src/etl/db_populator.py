"""
Database Populator for Construction Rates ETL Pipeline

This module provides the DatabasePopulator class for loading aggregated rate and resource
data into SQLite database with transactional integrity, batch processing, and comprehensive
error handling.

Key Features:
- Batch insertion with configurable batch size (default: 1000 records)
- Full transactionality with automatic rollback on errors
- Progress tracking with tqdm
- Post-load validation with record counts
- NaN to NULL conversion for SQLite compatibility
- Detailed logging and error reporting
- FTS5 auto-sync via database triggers
"""

import logging
import sqlite3
import time
import json
from typing import List, Tuple, Any, Optional, Dict
import pandas as pd
from tqdm import tqdm

from src.database.db_manager import DatabaseManager


# Configure logging
logger = logging.getLogger(__name__)


class DatabasePopulatorError(Exception):
    """Base exception for DatabasePopulator errors."""
    pass


class DuplicateRateCodeError(DatabasePopulatorError):
    """Raised when attempting to insert duplicate rate_code."""
    pass


class MissingRateCodeError(DatabasePopulatorError):
    """Raised when resource references non-existent rate_code."""
    pass


class ValidationError(DatabasePopulatorError):
    """Raised when post-load validation fails."""
    pass


class DatabasePopulator:
    """
    Loads aggregated construction rate and resource data into SQLite database.

    This class handles the final ETL step of loading processed data from DataAggregator
    into the database with proper schema mapping, constraint handling, and validation.

    Features:
    - Batch processing for optimal performance (1000 records/batch)
    - Transactional integrity (all-or-nothing)
    - Progress tracking with percentage completion
    - Automatic NaN to NULL conversion
    - Foreign key constraint validation
    - Post-load validation with record count comparison
    - Comprehensive error messages for debugging

    Schema Mapping:
        rates_df -> rates table:
            - rate_code -> rate_code (PK)
            - rate_full_name -> rate_full_name
            - rate_short_name -> rate_short_name
            - unit_number -> unit_quantity
            - unit -> unit_type
            - section_name -> category
            - composition (JSON string) -> composition
            - search_text -> search_text
            - overhead_rate -> overhead_rate (PHASE 1)
            - profit_margin -> profit_margin (PHASE 1)

        resources_df -> resources table:
            - rate_code -> rate_code (FK to rates)
            - resource_code -> resource_code
            - row_type -> resource_type
            - resource_name -> resource_name
            - resource_quantity -> quantity
            - resource_cost -> unit_cost/total_cost
            - machinist_wage -> machinist_wage (PHASE 1)
            - machinist_labor_hours -> machinist_labor_hours (PHASE 1)
            - machinist_machine_hours -> machinist_machine_hours (PHASE 1)
            - cost_without_wages -> cost_without_wages (PHASE 1)
            - relocation_included -> relocation_included (PHASE 1)
            - personnel_code -> personnel_code (PHASE 1)
            - machinist_grade -> machinist_grade (PHASE 1)

        price_statistics_df -> resource_price_statistics table:
            - resource_code -> resource_code
            - rate_code -> rate_code
            - current_price_min/max/mean/median -> current_price_* (PHASE 1)
            - unit_match -> unit_match (PHASE 1)
            - material_resource_cost -> material_resource_cost (PHASE 1)
            - total_resource_cost -> total_resource_cost (PHASE 1)
            - total_material_cost -> total_material_cost (PHASE 1)
            - total_position_cost -> total_position_cost (PHASE 1)

    Attributes:
        db_manager (DatabaseManager): Database connection manager
        batch_size (int): Number of records per batch insert (default: 1000)

    Example:
        >>> with DatabaseManager('data/estimates.db') as db:
        ...     db.initialize_schema()
        ...     populator = DatabasePopulator(db)
        ...     populator.populate_rates(rates_df)
        ...     populator.populate_resources(resources_df)
        ...     populator.populate_price_statistics(price_statistics_df)
        ...     stats = populator.get_statistics()
    """

    DEFAULT_BATCH_SIZE = 1000

    # SQL statements
    INSERT_RATE_SQL = """
        INSERT INTO rates (
            rate_code,
            rate_full_name,
            rate_short_name,
            unit_quantity,
            unit_type,
            total_cost,
            materials_cost,
            resources_cost,
            category,
            category_type,
            collection_code,
            collection_name,
            department_code,
            department_name,
            department_type,
            section_code,
            section_name,
            section_type,
            subsection_code,
            subsection_name,
            table_code,
            table_name,
            composition,
            search_text,
            overhead_rate,
            profit_margin
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """


    INSERT_RESOURCE_SQL = """
        INSERT INTO resources (
            rate_code,
            resource_code,
            resource_type,
            resource_name,
            quantity,
            unit,
            unit_cost,
            total_cost,
            specifications,
            machinist_wage,
            machinist_labor_hours,
            machinist_machine_hours,
            cost_without_wages,
            relocation_included,
            personnel_code,
            machinist_grade,
            resource_quantity_parameter,
            section2_name,
            section3_name,
            electricity_consumption,
            electricity_cost
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    INSERT_PRICE_STATISTICS_SQL = """
        INSERT INTO resource_price_statistics (
            resource_code,
            rate_code,
            current_price_min,
            current_price_max,
            current_price_mean,
            current_price_median,
            unit_match,
            material_resource_cost,
            total_resource_cost,
            total_material_cost,
            total_position_cost
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(resource_code, rate_code) DO UPDATE SET
            current_price_min = excluded.current_price_min,
            current_price_max = excluded.current_price_max,
            current_price_mean = excluded.current_price_mean,
            current_price_median = excluded.current_price_median,
            unit_match = excluded.unit_match,
            material_resource_cost = excluded.material_resource_cost,
            total_resource_cost = excluded.total_resource_cost,
            total_material_cost = excluded.total_material_cost,
            total_position_cost = excluded.total_position_cost,
            updated_at = datetime('now')
    """


    # P2: Resource Mass table insertion SQL
    INSERT_RESOURCE_MASS_SQL = """
        INSERT INTO resource_mass (
            resource_code, mass_name, mass_value, mass_unit
        ) VALUES (?, ?, ?, ?)
    """

    # P2: Services table insertion SQL
    INSERT_SERVICES_SQL = """
        INSERT INTO services (
            rate_code, service_category, service_type, service_code,
            service_unit, service_name, service_quantity
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    def __init__(self, db_manager: DatabaseManager, batch_size: int = DEFAULT_BATCH_SIZE):
        """
        Initialize DatabasePopulator with database manager.

        Args:
            db_manager: DatabaseManager instance with active connection
            batch_size: Number of records to insert per batch (default: 1000)

        Raises:
            ValueError: If db_manager is not connected or batch_size is invalid
        """
        if not db_manager.connection:
            raise ValueError("DatabaseManager must have active connection")

        if batch_size <= 0:
            raise ValueError(f"batch_size must be positive, got: {batch_size}")

        self.db_manager = db_manager
        self.batch_size = batch_size
        self._statistics: Dict[str, Any] = {}

        logger.info(f"DatabasePopulator initialized with batch_size={batch_size}")

    def populate_rates(self, rates_df: pd.DataFrame) -> int:
        """
        Populate rates table with aggregated rate data using batch inserts.

        This method:
        1. Maps DataFrame columns to database schema
        2. Converts NaN values to None (NULL in SQLite)
        3. Inserts records in batches using executemany()
        4. Validates foreign key constraints
        5. Auto-populates FTS index via database triggers
        6. Performs post-load validation

        Args:
            rates_df: DataFrame from DataAggregator with columns:
                - rate_code (required)
                - rate_full_name (required)
                - rate_short_name
                - unit_number -> unit_quantity
                - unit -> unit_type
                - total_cost, materials_cost, resources_cost
                - section_name -> category
                - composition (JSON string)
                - search_text
                - overhead_rate (PHASE 1)
                - profit_margin (PHASE 1)

        Returns:
            Number of rates inserted

        Raises:
            ValueError: If required columns missing or DataFrame empty
            DuplicateRateCodeError: If rate_code already exists (UNIQUE constraint)
            sqlite3.Error: If database operation fails
            ValidationError: If post-load validation fails

        Example:
            >>> inserted = populator.populate_rates(rates_df)
            >>> print(f"Inserted {inserted} rates")
        """
        start_time = time.time()

        # Validate input
        if rates_df is None or len(rates_df) == 0:
            raise ValueError("rates_df cannot be None or empty")

        # Check required columns
        required_cols = ['rate_code', 'rate_full_name', 'unit']
        missing_cols = [col for col in required_cols if col not in rates_df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns in rates_df: {missing_cols}")

        logger.info(f"Starting rates population: {len(rates_df)} records")

        # Check for duplicate rate_codes in input
        duplicate_codes = rates_df[rates_df['rate_code'].duplicated()]['rate_code'].tolist()
        if duplicate_codes:
            raise DuplicateRateCodeError(
                f"Input DataFrame contains duplicate rate_codes: {duplicate_codes[:5]}"
            )

        # Map DataFrame to database schema
        data_list = self._map_rates_to_schema(rates_df)

        # Insert in batches with transaction
        inserted_count = self._batch_insert(
            sql=self.INSERT_RATE_SQL,
            data_list=data_list,
            entity_name="rates"
        )

        # Post-load validation
        self._validate_rates_count(expected_count=len(rates_df))

        elapsed = time.time() - start_time
        logger.info(
            f"Successfully inserted {inserted_count} rates in {elapsed:.2f}s "
            f"({inserted_count/elapsed:.0f} records/sec)"
        )

        # Update statistics
        self._statistics['rates_inserted'] = inserted_count
        self._statistics['rates_insert_time'] = elapsed

        return inserted_count

    def populate_resources(self, resources_df: pd.DataFrame) -> int:
        """
        Populate resources table with linked resource data.

        This method:
        1. Maps DataFrame columns to database schema
        2. Validates rate_code foreign key references
        3. Converts NaN values to None (NULL)
        4. Inserts records in batches
        5. Relies on SQLite AUTOINCREMENT for resource_id
        6. Performs post-load validation

        Args:
            resources_df: DataFrame from DataAggregator with columns:
                - rate_code (required, FK to rates)
                - resource_code (required)
                - row_type -> resource_type
                - resource_name (required)
                - resource_quantity -> quantity
                - unit
                - resource_cost -> unit_cost
                - total_cost (calculated or from source)
                - specifications
                - machinist_wage (PHASE 1)
                - machinist_labor_hours (PHASE 1)
                - machinist_machine_hours (PHASE 1)
                - cost_without_wages (PHASE 1)
                - relocation_included (PHASE 1)
                - personnel_code (PHASE 1)
                - machinist_grade (PHASE 1)

        Returns:
            Number of resources inserted

        Raises:
            ValueError: If required columns missing or DataFrame empty
            MissingRateCodeError: If rate_code references non-existent rate
            sqlite3.Error: If database operation fails
            ValidationError: If post-load validation fails

        Example:
            >>> inserted = populator.populate_resources(resources_df)
            >>> print(f"Inserted {inserted} resources")
        """
        start_time = time.time()

        # Validate input
        if resources_df is None or len(resources_df) == 0:
            logger.warning("resources_df is empty, skipping resource population")
            return 0

        # Check required columns
        required_cols = ['rate_code', 'resource_code', 'resource_name']
        missing_cols = [col for col in required_cols if col not in resources_df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns in resources_df: {missing_cols}")

        logger.info(f"Starting resources population: {len(resources_df)} records")

        # Validate foreign key references
        self._validate_rate_code_references(resources_df)

        # Map DataFrame to database schema
        data_list = self._map_resources_to_schema(resources_df)

        # Insert in batches with transaction
        inserted_count = self._batch_insert(
            sql=self.INSERT_RESOURCE_SQL,
            data_list=data_list,
            entity_name="resources"
        )

        # Post-load validation
        self._validate_resources_count(expected_count=len(resources_df))

        elapsed = time.time() - start_time
        logger.info(
            f"Successfully inserted {inserted_count} resources in {elapsed:.2f}s "
            f"({inserted_count/elapsed:.0f} records/sec)"
        )

        # Update statistics
        self._statistics['resources_inserted'] = inserted_count
        self._statistics['resources_insert_time'] = elapsed

        return inserted_count

    def populate_price_statistics(self, price_statistics_df: pd.DataFrame) -> int:
        """
        Insert price statistics data into resource_price_statistics table.

        This method:
        1. Maps DataFrame columns to database schema
        2. Converts NaN values to None (NULL)
        3. Inserts records in batches using executemany()
        4. Handles UNIQUE constraint violations with UPSERT (ON CONFLICT DO UPDATE)
        5. Performs post-load validation

        Args:
            price_statistics_df: DataFrame from DataAggregator with columns:
                - resource_code (required)
                - rate_code (required)
                - current_price_min
                - current_price_max
                - current_price_mean
                - current_price_median
                - unit_match
                - material_resource_cost
                - total_resource_cost
                - total_material_cost
                - total_position_cost

        Returns:
            Number of records inserted/updated

        Raises:
            ValueError: If required columns missing or DataFrame empty
            sqlite3.Error: If database operation fails
            ValidationError: If post-load validation fails

        Example:
            >>> inserted = populator.populate_price_statistics(price_statistics_df)
            >>> print(f"Inserted {inserted} price statistics records")
        """
        start_time = time.time()

        # Validate input
        if price_statistics_df is None or len(price_statistics_df) == 0:
            logger.warning("price_statistics_df is empty, skipping price statistics population")
            return 0

        # Check required columns
        required_cols = ['resource_code', 'rate_code']
        missing_cols = [col for col in required_cols if col not in price_statistics_df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns in price_statistics_df: {missing_cols}")

        logger.info(f"Starting price statistics population: {len(price_statistics_df)} records")

        # Map DataFrame to database schema
        data_list = self._map_price_statistics_to_schema(price_statistics_df)

        # Insert in batches with transaction
        inserted_count = self._batch_insert(
            sql=self.INSERT_PRICE_STATISTICS_SQL,
            data_list=data_list,
            entity_name="price_statistics"
        )

        # Post-load validation
        self._validate_price_statistics_count(expected_count=len(price_statistics_df))

        elapsed = time.time() - start_time
        logger.info(
            f"Successfully inserted/updated {inserted_count} price statistics in {elapsed:.2f}s "
            f"({inserted_count/elapsed:.0f} records/sec)"
        )

        # Update statistics
        self._statistics['price_statistics_inserted'] = inserted_count
        self._statistics['price_statistics_insert_time'] = elapsed

        return inserted_count


    def _populate_resource_mass(self, resource_mass_df: pd.DataFrame) -> int:
        """
        Populate resource_mass table from aggregated DataFrame.

        Args:
            resource_mass_df: DataFrame with mass data

        Returns:
            Number of records inserted
        """
        if resource_mass_df.empty:
            logger.info("No mass data to populate")
            return 0

        logger.info(f"Populating resource_mass table with {len(resource_mass_df)} records...")

        # Prepare batch data
        mass_batches = self._prepare_batches(
            resource_mass_df,
            ['resource_code', 'mass_name', 'mass_value', 'mass_unit']
        )

        total_inserted = 0
        with tqdm(total=len(resource_mass_df), desc="Inserting mass records") as pbar:
            for batch in mass_batches:
                self.db_manager.execute_many(self.INSERT_RESOURCE_MASS_SQL, batch)
                batch_size = len(batch)
                total_inserted += batch_size
                pbar.update(batch_size)

        logger.info(f"Successfully inserted {total_inserted} mass records")
        return total_inserted

    def _populate_services(self, services_df: pd.DataFrame) -> int:
        """
        Populate services table from aggregated DataFrame.

        Args:
            services_df: DataFrame with service data

        Returns:
            Number of records inserted
        """
        if services_df.empty:
            logger.info("No service data to populate")
            return 0

        logger.info(f"Populating services table with {len(services_df)} records...")

        # Prepare batch data
        service_batches = self._prepare_batches(
            services_df,
            ['rate_code', 'service_category', 'service_type', 'service_code',
             'service_unit', 'service_name', 'service_quantity']
        )

        total_inserted = 0
        with tqdm(total=len(services_df), desc="Inserting service records") as pbar:
            for batch in service_batches:
                self.db_manager.execute_many(self.INSERT_SERVICES_SQL, batch)
                batch_size = len(batch)
                total_inserted += batch_size
                pbar.update(batch_size)

        logger.info(f"Successfully inserted {total_inserted} service records")
        return total_inserted

    def clear_database(self) -> None:
        """
        Truncate rates and resources tables, removing all data.

        This method:
        1. Deletes all records from resources table (child table)
        2. Deletes all records from rates table (parent table)
        3. Resets SQLite AUTOINCREMENT sequences
        4. Clears FTS index (via CASCADE trigger)
        5. Uses transaction for atomicity

        CAUTION: This operation is irreversible and removes ALL data from tables.

        Raises:
            sqlite3.Error: If truncation fails

        Example:
            >>> populator.clear_database()
            >>> print("All data cleared")
        """
        try:
            logger.warning("Starting database truncation (all data will be deleted)")

            # Delete in order: child tables first (resources), then parent (rates)
            tables = ['resource_price_statistics', 'resources', 'rates']

            for table in tables:
                delete_sql = f"DELETE FROM {table}"
                self.db_manager.execute_update(delete_sql)

                # Reset AUTOINCREMENT sequence for tables with auto-increment
                if table in ['resources', 'resource_price_statistics']:
                    reset_sql = f"DELETE FROM sqlite_sequence WHERE name = '{table}'"
                    self.db_manager.execute_update(reset_sql)

                # Get count to verify
                count_result = self.db_manager.execute_query(f"SELECT COUNT(*) FROM {table}")
                remaining = count_result[0][0] if count_result else 0

                logger.info(f"Truncated table '{table}' (remaining records: {remaining})")

            logger.warning("Database truncation completed successfully")

        except sqlite3.Error as e:
            error_msg = f"Failed to clear database: {str(e)}"
            logger.error(error_msg)
            raise sqlite3.Error(error_msg) from e

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about the population process.

        Returns:
            Dictionary with statistics including:
                - rates_inserted: Number of rates inserted
                - resources_inserted: Number of resources inserted
                - price_statistics_inserted: Number of price statistics inserted
                - rates_insert_time: Time taken for rates (seconds)
                - resources_insert_time: Time taken for resources (seconds)
                - price_statistics_insert_time: Time taken for price statistics (seconds)
                - total_records: Total records inserted
                - database_size: Size of database file (if available)

        Example:
            >>> stats = populator.get_statistics()
            >>> print(f"Total records: {stats['total_records']}")
        """
        # Add current database counts
        try:
            rates_count = self.db_manager.execute_query("SELECT COUNT(*) FROM rates")[0][0]
            resources_count = self.db_manager.execute_query("SELECT COUNT(*) FROM resources")[0][0]
            price_stats_count = self.db_manager.execute_query("SELECT COUNT(*) FROM resource_price_statistics")[0][0]

            stats = {
                **self._statistics,
                'current_rates_count': rates_count,
                'current_resources_count': resources_count,
                'current_price_statistics_count': price_stats_count,
                'total_records': rates_count + resources_count + price_stats_count
            }

            # Add FTS index count
            try:
                fts_count = self.db_manager.execute_query("SELECT COUNT(*) FROM rates_fts")[0][0]
                stats['fts_index_count'] = fts_count
            except sqlite3.Error:
                pass  # FTS table may not exist

            return stats

        except sqlite3.Error as e:
            logger.warning(f"Could not fetch current statistics: {str(e)}")
            return self._statistics

    # ========================================================================
    # Private Helper Methods
    # ========================================================================

    def _map_rates_to_schema(self, rates_df: pd.DataFrame) -> List[Tuple[Any, ...]]:
        """
        Map rates DataFrame to database schema tuple format.

        Handles:
        - Column name mapping (unit_number -> unit_quantity, etc.)
        - NaN to None conversion for SQLite NULL
        - Default values for missing columns
        - JSON composition validation
        - search_text computation if not provided (required for FTS triggers)
        - PHASE 1 fields: overhead_rate, profit_margin
        - TASK 9.2 fields: 13 ГЭСН/ФЕР hierarchy fields

        Args:
            rates_df: Source DataFrame from DataAggregator

        Returns:
            List of tuples ready for executemany()
        """
        data_list = []

        for _, row in rates_df.iterrows():
            # Extract base fields
            rate_code = self._safe_value(row.get('rate_code'))
            rate_full_name = self._safe_value(row.get('rate_full_name'))
            rate_short_name = self._safe_value(row.get('rate_short_name'))
            category = self._safe_value(row.get('section_name'))  # Backward compatibility
            composition = self._safe_value(row.get('composition'))

            # TASK 9.2: Extract 13 ГЭСН/ФЕР hierarchy fields
            category_type = self._safe_value(row.get('category_type'))
            collection_code = self._safe_value(row.get('collection_code'))
            collection_name = self._safe_value(row.get('collection_name'))
            department_code = self._safe_value(row.get('department_code'))
            department_name = self._safe_value(row.get('department_name'))
            department_type = self._safe_value(row.get('department_type'))
            section_code = self._safe_value(row.get('section_code'))
            # Use section_name_new from aggregator (contains 'Раздел | Имя')
            section_name = self._safe_value(row.get('section_name_new'))
            if not section_name:
                # Fallback to old 'section_name' field for backward compatibility
                section_name = category
            section_type = self._safe_value(row.get('section_type'))
            subsection_code = self._safe_value(row.get('subsection_code'))
            subsection_name = self._safe_value(row.get('subsection_name'))
            table_code = self._safe_value(row.get('table_code'))
            table_name = self._safe_value(row.get('table_name'))

            # TASK 9.2: Extract aggregated costs from Excel columns 32-34
            total_cost = self._safe_numeric(row.get('total_cost'), default=0.0)
            materials_cost = self._safe_numeric(row.get('materials_cost'), default=0.0)
            resources_cost = self._safe_numeric(row.get('resources_cost'), default=0.0)

            # Compute search_text if not provided (required for FTS trigger)
            # Include hierarchy fields for better FTS5 matching
            search_text = self._safe_value(row.get('search_text'))
            if not search_text:
                # Concatenate all searchable fields including hierarchy
                parts = [
                    rate_code or '',
                    rate_full_name or '',
                    rate_short_name or '',
                    category or '',
                    collection_name or '',
                    department_name or '',
                    section_name or '',
                    subsection_name or '',
                    table_name or '',
                    composition or ''
                ]
                search_text = ' '.join(parts).strip()

            # PHASE 1: Extract overhead_rate and profit_margin
            overhead_rate = self._safe_numeric(row.get('overhead_rate'), default=0.0)
            profit_margin = self._safe_numeric(row.get('profit_margin'), default=0.0)

            # Build rate tuple (26 fields total: 13 base + 13 hierarchy)
            rate_tuple = (
                rate_code,                                                  # 1. rate_code
                rate_full_name,                                             # 2. rate_full_name
                rate_short_name,                                            # 3. rate_short_name
                self._safe_numeric(row.get('unit_number'), default=1.0),   # 4. unit_quantity
                self._safe_value(row.get('unit')),                          # 5. unit_type
                total_cost,                                                 # 6. total_cost (TASK 9.2 FIX #3)
                materials_cost,                                             # 7. materials_cost (TASK 9.2 FIX #3)
                resources_cost,                                             # 8. resources_cost (TASK 9.2 FIX #3)
                category,                                                   # 9. category (backward compat)
                category_type,                                              # 10. category_type (TASK 9.2)
                collection_code,                                            # 11. collection_code (TASK 9.2)
                collection_name,                                            # 12. collection_name (TASK 9.2)
                department_code,                                            # 13. department_code (TASK 9.2)
                department_name,                                            # 14. department_name (TASK 9.2)
                department_type,                                            # 15. department_type (TASK 9.2)
                section_code,                                               # 16. section_code (TASK 9.2)
                section_name,                                               # 17. section_name (TASK 9.2)
                section_type,                                               # 18. section_type (TASK 9.2)
                subsection_code,                                            # 19. subsection_code (TASK 9.2)
                subsection_name,                                            # 20. subsection_name (TASK 9.2)
                table_code,                                                 # 21. table_code (TASK 9.2)
                table_name,                                                 # 22. table_name (TASK 9.2)
                composition,                                                # 23. composition (JSON)
                search_text,                                                # 24. search_text
                overhead_rate,                                              # 25. overhead_rate (PHASE 1)
                profit_margin                                               # 26. profit_margin (PHASE 1)
            )
            data_list.append(rate_tuple)

        return data_list

    def _map_resources_to_schema(self, resources_df: pd.DataFrame) -> List[Tuple[Any, ...]]:
        """
        Map resources DataFrame to database schema tuple format.

        Handles:
        - Column name mapping (row_type -> resource_type, etc.)
        - NaN to None conversion
        - Default values for missing columns
        - Unit cost calculation if not provided
        - PHASE 1 fields: machinist_wage, machinist_labor_hours, machinist_machine_hours,
                          cost_without_wages, relocation_included, personnel_code, machinist_grade

        Args:
            resources_df: Source DataFrame from DataAggregator

        Returns:
            List of tuples ready for executemany()
        """
        data_list = []

        for _, row in resources_df.iterrows():
            # Calculate total_cost if not provided (quantity * unit_cost)
            quantity = self._safe_numeric(row.get('resource_quantity'), default=0.0)
            unit_cost = self._safe_numeric(row.get('resource_cost'), default=0.0)

            # Try resource_price_median as fallback for unit_cost
            if unit_cost == 0.0 and 'resource_price_median' in row:
                unit_cost = self._safe_numeric(row.get('resource_price_median'), default=0.0)

            total_cost = quantity * unit_cost if quantity and unit_cost else 0.0

            # Extract unit from various possible column names
            unit = self._safe_value(row.get('unit'))
            if not unit and 'resource_unit' in row:
                unit = self._safe_value(row.get('resource_unit'))

            # PHASE 1: Extract machinery and labor fields
            machinist_wage = self._safe_numeric(row.get('machinist_wage'), default=0.0)
            machinist_labor_hours = self._safe_numeric(row.get('machinist_labor_hours'), default=0.0)
            machinist_machine_hours = self._safe_numeric(row.get('machinist_machine_hours'), default=0.0)
            cost_without_wages = self._safe_numeric(row.get('cost_without_wages'), default=0.0)
            relocation_included = self._safe_int(row.get('relocation_included'), default=0)
            personnel_code = self._safe_value(row.get('personnel_code'))
            machinist_grade = self._safe_int(row.get('machinist_grade'), default=None)

            # TASK 9.3 P1: Extract resource quantity parameter (TEXT field from col 24)
            resource_quantity_parameter = self._safe_value(row.get('resource_quantity_parameter'))

            # TASK 9.3 P2: Extract section classification fields (TEXT fields from cols 35-36)
            section2_name = self._safe_value(row.get('section2_name'))
            section3_name = self._safe_value(row.get('section3_name'))

            # TASK 9.3 P2: Extract electricity fields (REAL fields from cols 37-38)
            electricity_consumption = self._safe_numeric(row.get('electricity_consumption'), default=0.0)
            electricity_cost = self._safe_numeric(row.get('electricity_cost'), default=0.0)

            # Build resource tuple (21 fields total)
            resource_tuple = (
                self._safe_value(row.get('rate_code')),              # rate_code (FK)
                self._safe_value(row.get('resource_code')),          # resource_code
                self._safe_value(row.get('row_type')),               # resource_type
                self._safe_value(row.get('resource_name')),          # resource_name
                quantity,                                             # quantity
                unit,                                                 # unit
                unit_cost,                                            # unit_cost
                total_cost,                                           # total_cost
                self._safe_value(row.get('specifications')),         # specifications
                machinist_wage,                                       # machinist_wage (PHASE 1)
                machinist_labor_hours,                                # machinist_labor_hours (PHASE 1)
                machinist_machine_hours,                              # machinist_machine_hours (PHASE 1)
                cost_without_wages,                                   # cost_without_wages (PHASE 1)
                relocation_included,                                  # relocation_included (PHASE 1)
                personnel_code,                                       # personnel_code (PHASE 1)
                machinist_grade,                                      # machinist_grade (PHASE 1)
                resource_quantity_parameter,                          # resource_quantity_parameter (TASK 9.3 P1)
                section2_name,                                        # section2_name (TASK 9.3 P2)
                section3_name,                                        # section3_name (TASK 9.3 P2)
                electricity_consumption,                              # electricity_consumption (TASK 9.3 P2)
                electricity_cost                                      # electricity_cost (TASK 9.3 P2)
            )
            data_list.append(resource_tuple)

        return data_list

    def _map_price_statistics_to_schema(self, price_statistics_df: pd.DataFrame) -> List[Tuple[Any, ...]]:
        """
        Map price statistics DataFrame to database schema tuple format.

        Handles:
        - NaN to None conversion for SQLite NULL
        - Default values for missing columns
        - PHASE 1 fields: All price statistics fields

        Args:
            price_statistics_df: Source DataFrame from DataAggregator

        Returns:
            List of tuples ready for executemany()
        """
        data_list = []

        for _, row in price_statistics_df.iterrows():
            # Extract required fields
            resource_code = self._safe_value(row.get('resource_code'))
            rate_code = self._safe_value(row.get('rate_code'))

            # Extract price statistics fields
            current_price_min = self._safe_numeric(row.get('current_price_min'), default=0.0)
            current_price_max = self._safe_numeric(row.get('current_price_max'), default=0.0)
            current_price_mean = self._safe_numeric(row.get('current_price_mean'), default=0.0)
            current_price_median = self._safe_numeric(row.get('current_price_median'), default=0.0)

            # Extract unit match and cost fields
            unit_match = self._safe_int(row.get('unit_match'), default=0)
            material_resource_cost = self._safe_numeric(row.get('material_resource_cost'), default=0.0)
            total_resource_cost = self._safe_numeric(row.get('total_resource_cost'), default=0.0)
            total_material_cost = self._safe_numeric(row.get('total_material_cost'), default=0.0)
            total_position_cost = self._safe_numeric(row.get('total_position_cost'), default=0.0)

            # Build price statistics tuple (11 fields total)
            price_stats_tuple = (
                resource_code,                  # resource_code
                rate_code,                      # rate_code
                current_price_min,              # current_price_min
                current_price_max,              # current_price_max
                current_price_mean,             # current_price_mean
                current_price_median,           # current_price_median
                unit_match,                     # unit_match
                material_resource_cost,         # material_resource_cost
                total_resource_cost,            # total_resource_cost
                total_material_cost,            # total_material_cost
                total_position_cost             # total_position_cost
            )
            data_list.append(price_stats_tuple)

        return data_list

    def _batch_insert(
        self,
        sql: str,
        data_list: List[Tuple[Any, ...]],
        entity_name: str
    ) -> int:
        """
        Perform batch insert with progress tracking and error handling.

        Args:
            sql: INSERT SQL statement with placeholders
            data_list: List of tuples with data
            entity_name: Name for logging (e.g., "rates", "resources")

        Returns:
            Total number of records inserted

        Raises:
            sqlite3.Error: If batch insert fails
            sqlite3.IntegrityError: If constraint violated
            DuplicateRateCodeError: If UNIQUE constraint violated on rate_code
        """
        total_records = len(data_list)
        inserted_count = 0

        # Process in batches
        num_batches = (total_records + self.batch_size - 1) // self.batch_size

        logger.info(
            f"Inserting {total_records} {entity_name} in {num_batches} batches "
            f"(batch_size={self.batch_size})"
        )

        try:
            with tqdm(total=total_records, desc=f"Loading {entity_name}", unit="records") as pbar:
                for i in range(0, total_records, self.batch_size):
                    batch = data_list[i:i + self.batch_size]
                    batch_num = i // self.batch_size + 1

                    try:
                        # Use DatabaseManager's execute_many for transactional insert
                        rows_affected = self.db_manager.execute_many(sql, batch)
                        inserted_count += rows_affected

                        pbar.update(len(batch))

                        # Log progress every 10 batches
                        if batch_num % 10 == 0:
                            progress = (inserted_count / total_records) * 100
                            logger.debug(
                                f"Progress: {inserted_count}/{total_records} "
                                f"({progress:.1f}%) - Batch {batch_num}/{num_batches}"
                            )

                    except sqlite3.Error as e:
                        # Check if this is a wrapped IntegrityError
                        error_str = str(e).lower()

                        # Check for UNIQUE constraint on rate_code
                        if 'unique' in error_str and 'rate_code' in error_str:
                            raise DuplicateRateCodeError(
                                f"Duplicate rate_code in batch {batch_num}: {str(e)}"
                            ) from e

                        # Check for FOREIGN KEY constraint
                        elif 'foreign key' in error_str:
                            raise MissingRateCodeError(
                                f"Invalid rate_code reference in batch {batch_num}: {str(e)}"
                            ) from e

                        # Check for CHECK constraint (re-raise as IntegrityError for tests)
                        elif 'check constraint' in error_str:
                            # Extract original IntegrityError if wrapped
                            if hasattr(e, '__cause__') and isinstance(e.__cause__, sqlite3.IntegrityError):
                                raise e.__cause__
                            else:
                                # Recreate IntegrityError from wrapped error
                                raise sqlite3.IntegrityError(str(e)) from e

                        # For other errors, re-raise
                        else:
                            raise

            return inserted_count

        except (DuplicateRateCodeError, MissingRateCodeError, sqlite3.IntegrityError):
            # Re-raise specific exceptions without wrapping
            raise
        except sqlite3.Error as e:
            error_msg = f"Batch insert failed for {entity_name}: {str(e)}"
            logger.error(error_msg)
            raise sqlite3.Error(error_msg) from e

    def _validate_rate_code_references(self, resources_df: pd.DataFrame) -> None:
        """
        Validate that all rate_code references in resources exist in rates table.

        Args:
            resources_df: Resources DataFrame to validate

        Raises:
            MissingRateCodeError: If any rate_code references don't exist
        """
        # Get unique rate_codes from resources
        resource_rate_codes = set(resources_df['rate_code'].unique())

        # Query existing rate_codes from database
        existing_rates_result = self.db_manager.execute_query(
            "SELECT rate_code FROM rates"
        )
        existing_rate_codes = set(row[0] for row in existing_rates_result)

        # Find missing references
        missing_codes = resource_rate_codes - existing_rate_codes

        if missing_codes:
            raise MissingRateCodeError(
                f"Resources reference non-existent rate_codes: {list(missing_codes)[:10]}... "
                f"({len(missing_codes)} total). Please populate rates table first."
            )

        logger.debug(
            f"Foreign key validation passed: {len(resource_rate_codes)} unique rate_codes validated"
        )

    def _validate_rates_count(self, expected_count: int) -> None:
        """
        Validate that rates table has expected number of records.

        Args:
            expected_count: Expected number of rates

        Raises:
            ValidationError: If count mismatch detected
        """
        result = self.db_manager.execute_query("SELECT COUNT(*) FROM rates")
        actual_count = result[0][0] if result else 0

        if actual_count != expected_count:
            raise ValidationError(
                f"Post-load validation failed for rates: expected {expected_count}, "
                f"found {actual_count} records"
            )

        logger.info(f"Validation passed: rates table has {actual_count} records")

    def _validate_resources_count(self, expected_count: int) -> None:
        """
        Validate that resources table has expected number of records.

        Args:
            expected_count: Expected number of resources

        Raises:
            ValidationError: If count mismatch detected
        """
        result = self.db_manager.execute_query("SELECT COUNT(*) FROM resources")
        actual_count = result[0][0] if result else 0

        if actual_count != expected_count:
            raise ValidationError(
                f"Post-load validation failed for resources: expected {expected_count}, "
                f"found {actual_count} records"
            )

        logger.info(f"Validation passed: resources table has {actual_count} records")

    def _validate_price_statistics_count(self, expected_count: int) -> None:
        """
        Validate that resource_price_statistics table has expected number of records.

        Args:
            expected_count: Expected number of price statistics

        Raises:
            ValidationError: If count mismatch detected
        """
        result = self.db_manager.execute_query("SELECT COUNT(*) FROM resource_price_statistics")
        actual_count = result[0][0] if result else 0

        # Due to UNIQUE constraint on (resource_code, rate_code), duplicates are merged via UPSERT
        # So actual_count may be less than expected_count (but should be close)
        if actual_count == 0:
            raise ValidationError(
                f"Post-load validation failed for price statistics: no records loaded!"
            )

        if actual_count < expected_count * 0.95:  # Allow up to 5% difference for duplicates
            logger.warning(
                f"Validation warning: expected {expected_count}, found {actual_count} records "
                f"({expected_count - actual_count} duplicates merged via UPSERT)"
            )

        logger.info(
            f"Validation passed: resource_price_statistics table has {actual_count} records "
            f"(expected {expected_count}, {expected_count - actual_count} duplicates merged)"
        )

    @staticmethod
    def _safe_value(value: Any) -> Optional[Any]:
        """
        Safely convert value to database-compatible format.

        Converts pandas NaN to None (NULL in SQLite) and strips whitespace from strings.

        Args:
            value: Value to convert

        Returns:
            Converted value or None for NaN/empty
        """
        if value is None or pd.isna(value):
            return None

        if isinstance(value, str):
            stripped = value.strip()
            return stripped if stripped else None

        return value

    @staticmethod
    def _safe_numeric(value: Any, default: float = 0.0) -> float:
        """
        Safely convert value to numeric, returning default for invalid values.

        Args:
            value: Value to convert
            default: Default value for invalid conversions

        Returns:
            Float value or default
        """
        if value is None or pd.isna(value):
            return default

        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _safe_int(value: Any, default: Optional[int] = 0) -> Optional[int]:
        """
        Safely convert value to integer, returning default for invalid values.

        Args:
            value: Value to convert
            default: Default value for invalid conversions (None allowed)

        Returns:
            Integer value or default
        """
        if value is None or pd.isna(value):
            return default

        try:
            return int(value)
        except (ValueError, TypeError):
            return default
