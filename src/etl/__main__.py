"""
Entry point for ETL process
Run with: python -m src.etl.excel_to_sqlite
"""

import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.etl.excel_loader import ExcelLoader
from src.etl.data_aggregator import DataAggregator
from src.etl.db_populator import DatabasePopulator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('data/logs/etl_{}.log'.format(
            __import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')
        ))
    ]
)

logger = logging.getLogger(__name__)


def main():
    """
    Main ETL process:
    1. Load Excel file
    2. Aggregate data
    3. Populate database
    """
    try:
        logger.info("=" * 60)
        logger.info("Starting ETL Process: Excel → SQLite")
        logger.info("=" * 60)

        # Configuration
        excel_path = "data/raw/Сonstruction_Works_Rate_Schedule_17102025_half.xlsx"
        db_path = "data/processed/estimates.db"

        # Check if Excel file exists
        if not Path(excel_path).exists():
            logger.error(f"Excel file not found: {excel_path}")
            logger.error("Please place your Excel file in data/raw/ directory")
            return 1

        logger.info(f"Input file: {excel_path}")
        logger.info(f"Output database: {db_path}")

        # Step 1: Load Excel
        logger.info("\n[1/3] Loading Excel file...")
        loader = ExcelLoader(excel_path)
        loader.load()
        df = loader.get_dataframe()
        logger.info(f"Loaded {len(df):,} rows from Excel")

        # Step 2: Aggregate data
        logger.info("\n[2/3] Aggregating data...")
        aggregator = DataAggregator(df)
        rates_df = aggregator.get_rates()
        resources_df = aggregator.get_resources()
        logger.info(f"Aggregated {len(rates_df):,} rates and {len(resources_df):,} resources")

        # Step 3: Populate database
        logger.info("\n[3/3] Populating database...")
        populator = DatabasePopulator(db_path)
        populator.populate(rates_df, resources_df)

        # Verify database
        logger.info("\n" + "=" * 60)
        logger.info("Verifying database...")
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        rates_count = cursor.execute("SELECT COUNT(*) FROM rates").fetchone()[0]
        resources_count = cursor.execute("SELECT COUNT(*) FROM resources").fetchone()[0]
        fts_count = cursor.execute("SELECT COUNT(*) FROM rates_fts").fetchone()[0]

        logger.info(f"✅ Rates: {rates_count:,}")
        logger.info(f"✅ Resources: {resources_count:,}")
        logger.info(f"✅ FTS index: {fts_count:,} entries")

        # Check database size
        db_size_mb = Path(db_path).stat().st_size / (1024 * 1024)
        logger.info(f"✅ Database size: {db_size_mb:.1f} MB")

        conn.close()

        logger.info("=" * 60)
        logger.info("🎉 ETL Process Completed Successfully!")
        logger.info(f"Database created: {db_path}")
        logger.info("=" * 60)

        return 0

    except Exception as e:
        logger.error(f"❌ ETL Process Failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
