-- Migration: Add vector embeddings support to rates table
-- Date: 2025-10-24
-- Purpose: Enable semantic search using BGE-M3 embeddings (1024 dimensions)
-- Dependencies: sqlite-vec extension must be installed

-- ============================================================================
-- MIGRATION: Add embedding column to rates table
-- ============================================================================

-- Step 1: Add embedding column (BLOB to store vector data)
-- Note: sqlite-vec uses BLOB internally, but we'll treat it as FLOAT32[1024]
ALTER TABLE rates ADD COLUMN embedding BLOB;

-- Step 2: Create metadata table to track embedding generation
CREATE TABLE IF NOT EXISTS embedding_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name TEXT NOT NULL,
    embedding_dimension INTEGER NOT NULL,
    total_rates_embedded INTEGER DEFAULT 0,
    last_embedded_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(model_name)
);

-- Step 3: Insert initial metadata
INSERT OR REPLACE INTO embedding_metadata (model_name, embedding_dimension, total_rates_embedded)
VALUES ('BAAI/bge-m3', 1024, 0);

-- Step 4: Create index for vector similarity search
-- This will be created programmatically using sqlite-vec after embeddings are generated
-- CREATE VIRTUAL TABLE rates_vec_idx USING vec0(
--     embedding FLOAT32[1024],
--     distance_metric='cosine'
-- );

-- ============================================================================
-- ROLLBACK (if needed)
-- ============================================================================
-- To rollback this migration:
-- 1. DROP TABLE embedding_metadata;
-- 2. ALTER TABLE rates DROP COLUMN embedding; (Note: SQLite doesn't support DROP COLUMN in older versions)
-- 3. If rollback needed on older SQLite, recreate table without embedding column

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Verify column was added
-- SELECT sql FROM sqlite_master WHERE type='table' AND name='rates';

-- Check metadata table
-- SELECT * FROM embedding_metadata;

-- Count rates without embeddings (after initial migration, should be all)
-- SELECT COUNT(*) FROM rates WHERE embedding IS NULL;

-- ============================================================================
-- NOTES
-- ============================================================================
-- 1. Embeddings will be populated by separate script (generate_embeddings.py)
-- 2. Vector index will be created after embeddings are generated
-- 3. Embedding dimension: 1024 (BGE-M3 model)
-- 4. Distance metric: cosine similarity
-- 5. This migration is backward compatible - existing queries work unchanged
