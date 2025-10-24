#!/usr/bin/env python3
"""
Generate embeddings for all construction rates using OpenAI API.

This script:
1. Loads all rates from the database
2. Generates embeddings using OpenAI text-embedding-3-small model
3. Updates the rates table with embeddings in batches
4. Updates metadata tracking

Usage:
    python scripts/generate_embeddings_openai.py --api-key YOUR_KEY [--batch-size 100]

Requirements:
    - Database with migrated schema (embedding column exists)
    - Valid OpenAI API key
    - Internet connection

Cost estimate:
    - For 28,686 rates (~100 tokens each): ~$0.06 with text-embedding-3-small
"""

import argparse
import logging
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tqdm import tqdm

from src.database.db_manager import DatabaseManager
from src.search.vector_engine import VectorSearchEngine


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_rates_to_embed(db_manager: DatabaseManager, resume: bool = False):
    """
    Get list of rates that need embeddings.

    Args:
        db_manager: Database manager instance
        resume: If True, only get rates without embeddings

    Returns:
        List of tuples (rate_code, rate_full_name)
    """
    if resume:
        sql = """
            SELECT rate_code, rate_full_name
            FROM rates
            WHERE embedding IS NULL
            ORDER BY rate_code
        """
        logger.info("Resume mode: fetching rates without embeddings")
    else:
        sql = """
            SELECT rate_code, rate_full_name
            FROM rates
            ORDER BY rate_code
        """
        logger.info("Full mode: fetching all rates")

    rows = db_manager.execute_query(sql)
    logger.info(f"Found {len(rows)} rates to embed")
    return rows


def batch_generate_embeddings(
    db_manager: DatabaseManager,
    vector_engine: VectorSearchEngine,
    rates: list,
    batch_size: int = 100,
):
    """
    Generate embeddings in batches using OpenAI API and update database.

    Args:
        db_manager: Database manager instance
        vector_engine: Vector search engine with OpenAI client
        rates: List of (rate_code, rate_full_name) tuples
        batch_size: Number of rates to process per API call

    Returns:
        Tuple of (successful_count, failed_count)
    """
    total_rates = len(rates)
    successful = 0
    failed = 0

    logger.info(f"Starting batch embedding generation (batch_size={batch_size})")

    # Progress bar
    pbar = tqdm(total=total_rates, desc="Generating embeddings", unit="rate")

    # Process in batches
    for i in range(0, total_rates, batch_size):
        batch = rates[i : i + batch_size]
        batch_start = time.time()

        try:
            # Prepare batch data with validation
            valid_items = []
            for r in batch:
                rate_code = r[0]
                text = r[1]

                # Validate text
                if text and isinstance(text, str) and text.strip():
                    valid_items.append((rate_code, text.strip()))
                else:
                    logger.warning(f"Skipping rate {rate_code}: invalid text")
                    failed += 1
                    pbar.update(1)

            if not valid_items:
                continue

            rate_codes = [item[0] for item in valid_items]
            texts = [item[1] for item in valid_items]

            # Generate embeddings for entire batch with one API call
            try:
                embeddings = vector_engine.generate_embeddings_batch(texts)
            except Exception as e:
                logger.error(f"OpenAI API call failed for batch {i}: {e}")
                failed += len(valid_items)
                pbar.update(len(valid_items))
                continue

            # Update database
            update_sql = "UPDATE rates SET embedding = ? WHERE rate_code = ?"

            for rate_code, embedding in zip(rate_codes, embeddings):
                try:
                    db_manager.execute_query(update_sql, (embedding, rate_code))
                    successful += 1
                except Exception as e:
                    logger.error(f"Failed to update rate {rate_code}: {e}")
                    failed += 1

                pbar.update(1)

            # Commit batch
            db_manager.connection.commit()

            batch_time = time.time() - batch_start
            rates_per_sec = len(batch) / batch_time if batch_time > 0 else 0

            if (i + batch_size) % (batch_size * 10) == 0:  # Log every 10 batches
                logger.info(
                    f"Processed {i + len(batch)}/{total_rates} rates "
                    f"({rates_per_sec:.1f} rates/sec, {successful} success, {failed} failed)"
                )

        except Exception as e:
            logger.error(f"Batch processing failed at index {i}: {e}", exc_info=True)
            failed += len(batch)
            pbar.update(len(batch))

    pbar.close()

    logger.info(
        f"Embedding generation complete: {successful} successful, {failed} failed"
    )

    return successful, failed


def update_metadata(db_manager: DatabaseManager, model_name: str, embedded_count: int):
    """
    Update embedding metadata table.

    Args:
        db_manager: Database manager instance
        model_name: Name of embedding model used
        embedded_count: Total number of rates embedded
    """
    # Check if metadata row exists
    check_sql = "SELECT COUNT(*) FROM embedding_metadata WHERE model_name = ?"
    count = db_manager.execute_query(check_sql, (model_name,))[0][0]

    if count > 0:
        # Update existing row
        sql = """
            UPDATE embedding_metadata
            SET total_rates_embedded = ?,
                last_embedded_at = CURRENT_TIMESTAMP
            WHERE model_name = ?
        """
        db_manager.execute_query(sql, (embedded_count, model_name))
    else:
        # Insert new row
        sql = """
            INSERT INTO embedding_metadata
            (model_name, embedding_dimension, total_rates_embedded, last_embedded_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """
        # Determine dimension based on model name
        dimension = 1536 if "small" in model_name else 3072
        db_manager.execute_query(sql, (model_name, dimension, embedded_count))

    db_manager.connection.commit()

    logger.info(f"Updated metadata: {embedded_count} rates embedded with {model_name}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate embeddings for construction rates using OpenAI API"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        required=True,
        help="OpenAI API key",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of rates to process per API call (default: 100, max: 2048)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from previous run (only embed rates without embeddings)",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="data/processed/estimates.db",
        help="Path to database file",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="text-embedding-3-small",
        choices=["text-embedding-3-small", "text-embedding-3-large"],
        help="OpenAI embedding model (default: text-embedding-3-small)",
    )

    args = parser.parse_args()

    # Validate batch size (OpenAI allows up to 2048 inputs per request)
    if args.batch_size <= 0 or args.batch_size > 2048:
        logger.error("Batch size must be between 1 and 2048")
        sys.exit(1)

    # Verify database exists
    if not Path(args.db_path).exists():
        logger.error(f"Database not found: {args.db_path}")
        sys.exit(1)

    logger.info("=== OpenAI Embedding Generation Started ===")
    logger.info(f"Database: {args.db_path}")
    logger.info(f"Model: {args.model}")
    logger.info(f"Batch size: {args.batch_size}")
    logger.info(f"Resume mode: {args.resume}")

    # Initialize database and vector engine
    db_manager = DatabaseManager(args.db_path)
    db_manager.connect()

    vector_engine = VectorSearchEngine(
        db_manager, api_key=args.api_key, model_name=args.model
    )

    # Get rates to embed
    rates = get_rates_to_embed(db_manager, resume=args.resume)

    if len(rates) == 0:
        logger.info("No rates to embed. Exiting.")
        db_manager.disconnect()
        return

    # Estimate cost
    avg_tokens_per_rate = 100  # Conservative estimate
    total_tokens = len(rates) * avg_tokens_per_rate
    if "small" in args.model:
        cost = total_tokens / 1_000_000 * 0.02  # $0.02 per 1M tokens
    else:
        cost = total_tokens / 1_000_000 * 0.13  # $0.13 per 1M tokens

    logger.info(f"Estimated cost: ${cost:.4f} for ~{total_tokens:,} tokens")

    # Generate embeddings
    start_time = time.time()
    embedded_count, failed_count = batch_generate_embeddings(
        db_manager, vector_engine, rates, batch_size=args.batch_size
    )
    total_time = time.time() - start_time

    # Update metadata
    if embedded_count > 0:
        update_metadata(db_manager, args.model, embedded_count)

    # Print statistics
    logger.info("=== Embedding Generation Complete ===")
    logger.info(f"Total rates embedded: {embedded_count}")
    logger.info(f"Failed: {failed_count}")
    logger.info(f"Total time: {total_time:.1f} seconds")
    if total_time > 0:
        logger.info(f"Average rate: {embedded_count / total_time:.2f} rates/sec")

    # Get final stats
    stats = vector_engine.get_embedding_stats()
    logger.info(f"Database stats: {stats}")

    db_manager.disconnect()
    logger.info("Database connection closed")


if __name__ == "__main__":
    main()
