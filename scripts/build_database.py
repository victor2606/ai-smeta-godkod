#!/usr/bin/env python3
"""
ETL Pipeline Script for Building SQLite Database from Excel Data

This script orchestrates the complete ETL pipeline for loading construction rate
data from Excel files into a SQLite database with full-text search capabilities.

Features:
- CLI argument parsing with validation
- Excel data loading and aggregation
- Database schema initialization
- Batch data population with transactions
- Automatic database backup with --force flag
- Comprehensive logging to file and console
- Data integrity checks (PRAGMA integrity_check)
- Statistics reporting (execution time, record counts, file size)
- Graceful error handling with cleanup

Usage:
    python scripts/build_database.py \
        --input data/raw/rates.xlsx \
        --output data/processed/estimates.db \
        --force \
        --batch-size 1000

Author: ETL Pipeline Team
Date: 2025-10-19
"""

import argparse
import logging
import sys
import shutil
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to path to import local modules
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.etl.excel_loader import ExcelLoader
from src.etl.data_aggregator import DataAggregator
from src.etl.db_populator import DatabasePopulator
from src.database.db_manager import DatabaseManager


# ============================================================================
# Logging Setup
# ============================================================================

def setup_logging(log_dir: Path) -> logging.Logger:
    """
    Configure logging to write to both file and console.

    Creates log directory if it doesn't exist and sets up dual handlers
    with timestamps and appropriate formatting.

    Args:
        log_dir: Directory where log files will be stored

    Returns:
        Configured logger instance

    Example:
        >>> logger = setup_logging(Path("data/logs"))
        >>> logger.info("ETL pipeline started")
    """
    # Create log directory
    log_dir.mkdir(parents=True, exist_ok=True)

    # Generate timestamped log filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"etl_{timestamp}.log"

    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # File handler with detailed formatting
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)

    # Console handler with simplified formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)

    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info(f"Logging initialized: {log_file}")
    return logger


# ============================================================================
# Database Backup
# ============================================================================

def backup_database(db_path: Path, logger: logging.Logger) -> Optional[Path]:
    """
    Create timestamped backup of existing database file.

    Uses shutil.copy2() to preserve file metadata while creating backup.
    Backup filename format: {original_name}_backup_{timestamp}.db

    Args:
        db_path: Path to database file to backup
        logger: Logger instance for logging

    Returns:
        Path to backup file if created, None if original doesn't exist

    Raises:
        IOError: If backup creation fails

    Example:
        >>> backup_path = backup_database(Path("data/estimates.db"), logger)
        >>> print(f"Backup created: {backup_path}")
    """
    if not db_path.exists():
        logger.info(f"Database does not exist, no backup needed: {db_path}")
        return None

    # Generate timestamped backup filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.parent / f"{db_path.stem}_backup_{timestamp}{db_path.suffix}"

    try:
        logger.info(f"Creating backup: {db_path} -> {backup_path}")
        shutil.copy2(db_path, backup_path)

        # Verify backup size matches original
        original_size = db_path.stat().st_size
        backup_size = backup_path.stat().st_size

        if original_size == backup_size:
            logger.info(f"Backup created successfully: {backup_path} ({original_size:,} bytes)")
            return backup_path
        else:
            raise IOError(
                f"Backup size mismatch: original={original_size}, backup={backup_size}"
            )

    except Exception as e:
        logger.error(f"Failed to create backup: {str(e)}")
        raise IOError(f"Backup creation failed: {str(e)}") from e


# ============================================================================
# Database Schema Loading
# ============================================================================

def load_schema(db_manager: DatabaseManager, logger: logging.Logger) -> None:
    """
    Execute schema.sql to create database tables, indexes, and triggers.

    Uses DatabaseManager's initialize_schema() method which reads and executes
    the SQL schema file located at src/database/schema.sql.

    Args:
        db_manager: DatabaseManager instance with active connection
        logger: Logger instance for logging

    Raises:
        FileNotFoundError: If schema.sql file not found
        sqlite3.Error: If schema execution fails

    Example:
        >>> with DatabaseManager('data/estimates.db') as db:
        ...     load_schema(db, logger)
    """
    logger.info("Loading database schema from schema.sql")
    start_time = time.time()

    try:
        db_manager.initialize_schema()
        elapsed = time.time() - start_time
        logger.info(f"Schema loaded successfully in {elapsed:.2f}s")

    except FileNotFoundError as e:
        logger.error(f"Schema file not found: {str(e)}")
        raise
    except sqlite3.Error as e:
        logger.error(f"Schema execution failed: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error loading schema: {str(e)}")
        raise


# ============================================================================
# Data Integrity Checks
# ============================================================================

def run_integrity_checks(
    db_manager: DatabaseManager,
    logger: logging.Logger
) -> Dict[str, Any]:
    """
    Run SQLite integrity checks and validate record counts.

    Performs:
    1. PRAGMA integrity_check - SQLite internal consistency check
    2. Validates rates count > 0
    3. Validates resources count > 0

    Args:
        db_manager: DatabaseManager instance with active connection
        logger: Logger instance for logging

    Returns:
        Dictionary with integrity check results:
            - integrity_check: "ok" or error message
            - rates_count: Number of rates in database
            - resources_count: Number of resources in database
            - checks_passed: Boolean indicating all checks passed

    Example:
        >>> results = run_integrity_checks(db, logger)
        >>> if results['checks_passed']:
        ...     print("All integrity checks passed")
    """
    logger.info("Running data integrity checks")
    results = {
        'integrity_check': None,
        'rates_count': 0,
        'resources_count': 0,
        'checks_passed': False
    }

    try:
        # 1. SQLite PRAGMA integrity_check
        logger.info("Running PRAGMA integrity_check")
        integrity_result = db_manager.execute_query("PRAGMA integrity_check")

        if integrity_result and integrity_result[0][0] == 'ok':
            results['integrity_check'] = 'ok'
            logger.info("PRAGMA integrity_check: OK")
        else:
            results['integrity_check'] = str(integrity_result)
            logger.error(f"PRAGMA integrity_check FAILED: {integrity_result}")
            return results

        # 2. Validate rates count
        logger.info("Validating rates count")
        rates_result = db_manager.execute_query("SELECT COUNT(*) FROM rates")
        rates_count = rates_result[0][0] if rates_result else 0
        results['rates_count'] = rates_count

        if rates_count == 0:
            logger.error("Integrity check FAILED: No rates found in database")
            return results

        logger.info(f"Rates count: {rates_count:,}")

        # 3. Validate resources count
        logger.info("Validating resources count")
        resources_result = db_manager.execute_query("SELECT COUNT(*) FROM resources")
        resources_count = resources_result[0][0] if resources_result else 0
        results['resources_count'] = resources_count

        if resources_count == 0:
            logger.warning("Warning: No resources found in database")
            # Don't fail on zero resources - some datasets might not have them
        else:
            logger.info(f"Resources count: {resources_count:,}")

        # All checks passed
        results['checks_passed'] = True
        logger.info("All integrity checks passed successfully")

        return results

    except sqlite3.Error as e:
        logger.error(f"Integrity check failed with database error: {str(e)}")
        results['integrity_check'] = f"ERROR: {str(e)}"
        return results
    except Exception as e:
        logger.error(f"Unexpected error during integrity checks: {str(e)}")
        results['integrity_check'] = f"ERROR: {str(e)}"
        return results


# ============================================================================
# Statistics Collection
# ============================================================================

def get_statistics(
    db_path: Path,
    execution_time: float,
    db_manager: DatabaseManager,
    logger: logging.Logger
) -> Dict[str, Any]:
    """
    Collect and return pipeline execution statistics.

    Gathers:
    - Total execution time
    - Number of rates loaded
    - Number of resources loaded
    - Database file size in MB

    Args:
        db_path: Path to database file
        execution_time: Total pipeline execution time in seconds
        db_manager: DatabaseManager instance for querying counts
        logger: Logger instance for logging

    Returns:
        Dictionary with statistics:
            - execution_time: Total time in seconds
            - rates_count: Number of rates
            - resources_count: Number of resources
            - db_size_mb: Database file size in megabytes
            - success: Pipeline success status

    Example:
        >>> stats = get_statistics(db_path, 45.2, db, logger)
        >>> print(f"Loaded {stats['rates_count']} rates in {stats['execution_time']:.2f}s")
    """
    logger.info("Collecting pipeline statistics")
    stats = {
        'execution_time': execution_time,
        'rates_count': 0,
        'resources_count': 0,
        'db_size_mb': 0.0,
        'success': True
    }

    try:
        # Get record counts
        rates_result = db_manager.execute_query("SELECT COUNT(*) FROM rates")
        stats['rates_count'] = rates_result[0][0] if rates_result else 0

        resources_result = db_manager.execute_query("SELECT COUNT(*) FROM resources")
        stats['resources_count'] = resources_result[0][0] if resources_result else 0

        # Get database file size
        if db_path.exists():
            size_bytes = db_path.stat().st_size
            stats['db_size_mb'] = size_bytes / (1024 * 1024)  # Convert to MB
        else:
            logger.warning(f"Database file not found: {db_path}")

        logger.info(f"Statistics collected: {stats}")
        return stats

    except Exception as e:
        logger.error(f"Failed to collect statistics: {str(e)}")
        return stats


# ============================================================================
# Main ETL Pipeline
# ============================================================================

def main() -> int:
    """
    Main ETL pipeline orchestration function.

    Coordinates the complete ETL process:
    1. Parse CLI arguments
    2. Setup logging
    3. Backup existing database (if --force)
    4. Load Excel data
    5. Aggregate rates and resources
    6. Initialize database schema
    7. Populate database with transactions
    8. Run integrity checks
    9. Report statistics

    Returns:
        Exit code: 0 for success, 1 for failure

    Raises:
        SystemExit: On keyboard interrupt or critical error
    """
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Build SQLite database from Excel construction rate data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python scripts/build_database.py \\
    --input data/raw/rates.xlsx \\
    --output data/processed/estimates.db

  # Overwrite existing database with backup
  python scripts/build_database.py \\
    --input data/raw/rates.xlsx \\
    --output data/processed/estimates.db \\
    --force

  # Custom batch size for large datasets
  python scripts/build_database.py \\
    --input data/raw/rates.xlsx \\
    --output data/processed/estimates.db \\
    --batch-size 5000
        """
    )

    parser.add_argument(
        '--input',
        type=str,
        required=True,
        help='Path to input Excel file (required)'
    )

    parser.add_argument(
        '--output',
        type=str,
        required=True,
        help='Path to output SQLite database (required)'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='Overwrite existing database (creates backup first)'
    )

    parser.add_argument(
        '--batch-size',
        type=int,
        default=1000,
        help='Batch size for database inserts (default: 1000)'
    )

    args = parser.parse_args()

    # Convert to Path objects
    input_path = Path(args.input)
    output_path = Path(args.output)
    batch_size = args.batch_size

    # Validate input file exists
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}", file=sys.stderr)
        return 1

    # Validate batch size
    if batch_size <= 0:
        print(f"ERROR: Batch size must be positive, got: {batch_size}", file=sys.stderr)
        return 1

    # Check if output database exists and --force not set
    if output_path.exists() and not args.force:
        print(
            f"ERROR: Database already exists: {output_path}\n"
            f"Use --force to overwrite (creates backup automatically)",
            file=sys.stderr
        )
        return 1

    # Setup logging
    log_dir = PROJECT_ROOT / "data" / "logs"
    logger = setup_logging(log_dir)

    # Track if database was newly created (for cleanup on failure)
    db_was_new = not output_path.exists()

    # Start pipeline
    logger.info("=" * 80)
    logger.info("ETL Pipeline Started")
    logger.info("=" * 80)
    logger.info(f"Input file: {input_path}")
    logger.info(f"Output database: {output_path}")
    logger.info(f"Batch size: {batch_size:,}")
    logger.info(f"Force overwrite: {args.force}")

    start_time = time.time()

    try:
        # ====================================================================
        # Step 0: Backup existing database (if --force and exists)
        # ====================================================================
        if args.force and output_path.exists():
            logger.info("Step 0: Creating database backup")
            backup_path = backup_database(output_path, logger)
            if backup_path:
                logger.info(f"Backup created: {backup_path}")

        # ====================================================================
        # Step 1: Load Excel file
        # ====================================================================
        logger.info("Step 1: Loading Excel file")
        excel_loader = ExcelLoader(str(input_path))
        df = excel_loader.load()
        excel_loader.validate()

        excel_stats = excel_loader.get_statistics()
        logger.info(f"Excel loaded: {excel_stats['total_rows']:,} rows, "
                   f"{excel_stats['unique_rates']:,} unique rates")

        # ====================================================================
        # Step 2: Aggregate data
        # ====================================================================
        logger.info("Step 2: Aggregating rates and resources")
        aggregator = DataAggregator(df)

        # Aggregate rates
        logger.info("Step 2a: Aggregating rates")
        rates_df = aggregator.aggregate_rates(df)
        logger.info(f"Aggregated {len(rates_df):,} rates")

        # Aggregate resources
        logger.info("Step 2b: Aggregating resources")
        resources_df = aggregator.aggregate_resources(df)
        logger.info(f"Aggregated {len(resources_df):,} resources")

        aggregator_stats = aggregator.get_statistics()
        logger.info(f"Aggregation complete: {aggregator_stats}")

        # ====================================================================
        # Step 3: Initialize database and load schema
        # ====================================================================
        logger.info("Step 3: Initializing database")

        # Delete existing database if --force
        if args.force and output_path.exists():
            logger.info(f"Removing existing database: {output_path}")
            output_path.unlink()

        # Create database and load schema
        with DatabaseManager(str(output_path)) as db:
            load_schema(db, logger)

            # ================================================================
            # Step 4: Populate database with transactions
            # ================================================================
            logger.info("Step 4: Populating database")
            populator = DatabasePopulator(db, batch_size=batch_size)

            # Populate rates
            logger.info("Step 4a: Populating rates table")
            rates_inserted = populator.populate_rates(rates_df)
            logger.info(f"Inserted {rates_inserted:,} rates")

            # Populate resources
            logger.info("Step 4b: Populating resources table")
            resources_inserted = populator.populate_resources(resources_df)
            logger.info(f"Inserted {resources_inserted:,} resources")

            # ================================================================
            # Step 5: Run integrity checks
            # ================================================================
            logger.info("Step 5: Running integrity checks")
            integrity_results = run_integrity_checks(db, logger)

            if not integrity_results['checks_passed']:
                logger.error("Integrity checks FAILED")
                logger.error(f"Results: {integrity_results}")
                raise RuntimeError("Data integrity validation failed")

            logger.info("Integrity checks PASSED")

            # ================================================================
            # Step 6: Collect and report statistics
            # ================================================================
            logger.info("Step 6: Collecting statistics")
            elapsed = time.time() - start_time
            stats = get_statistics(output_path, elapsed, db, logger)

        # ====================================================================
        # Pipeline Complete - Report Success
        # ====================================================================
        logger.info("=" * 80)
        logger.info("ETL Pipeline Completed Successfully")
        logger.info("=" * 80)
        logger.info(f"Execution time: {stats['execution_time']:.2f}s")
        logger.info(f"Rates loaded: {stats['rates_count']:,}")
        logger.info(f"Resources loaded: {stats['resources_count']:,}")
        logger.info(f"Database size: {stats['db_size_mb']:.2f} MB")
        logger.info(f"Database location: {output_path}")
        logger.info("=" * 80)

        return 0  # Success

    except KeyboardInterrupt:
        logger.warning("\nPipeline interrupted by user (Ctrl+C)")
        logger.info("Cleaning up...")

        # Clean up partial database if it was newly created
        if db_was_new and output_path.exists():
            logger.info(f"Removing partial database: {output_path}")
            try:
                output_path.unlink()
                logger.info("Cleanup complete")
            except Exception as e:
                logger.error(f"Failed to remove partial database: {str(e)}")

        return 1  # Failure

    except Exception as e:
        logger.error("=" * 80)
        logger.error("ETL Pipeline FAILED")
        logger.error("=" * 80)
        logger.error(f"Error: {str(e)}", exc_info=True)

        # Clean up partial database if it was newly created
        if db_was_new and output_path.exists():
            logger.info(f"Cleaning up partial database: {output_path}")
            try:
                output_path.unlink()
                logger.info("Cleanup complete")
            except Exception as cleanup_error:
                logger.error(f"Failed to remove partial database: {str(cleanup_error)}")

        return 1  # Failure


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    sys.exit(main())
