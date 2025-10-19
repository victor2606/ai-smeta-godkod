-- ============================================================================
-- Database Schema for Construction Rates Management System
-- Database: SQLite with FTS5 Full-Text Search
-- Version: 1.0
-- Created: 2025-10-19
-- ============================================================================

-- ============================================================================
-- TABLE: rates
-- Description: Main table for storing construction rate information including
--              costs, units, and descriptive information
-- ============================================================================
CREATE TABLE IF NOT EXISTS rates (
    -- Primary identifier for the rate (e.g., "ГЭСНп81-01-001-01")
    rate_code TEXT PRIMARY KEY NOT NULL,

    -- Full descriptive name of the rate
    rate_full_name TEXT NOT NULL,

    -- Abbreviated name for quick reference
    rate_short_name TEXT,

    -- Quantity of units this rate applies to (e.g., 100, 1, 1000)
    unit_quantity NUMERIC NOT NULL DEFAULT 1,

    -- Type of measurement unit (e.g., "м3", "т", "м2", "шт")
    unit_type TEXT NOT NULL,

    -- Total cost in currency units
    total_cost NUMERIC NOT NULL DEFAULT 0,

    -- Cost attributed to materials
    materials_cost NUMERIC NOT NULL DEFAULT 0,

    -- Cost attributed to labor and machinery resources
    resources_cost NUMERIC NOT NULL DEFAULT 0,

    -- Category or section code for grouping rates
    category TEXT,

    -- JSON composition data from DataAggregator (work composition details)
    composition TEXT,

    -- Concatenated searchable text (populated by trigger)
    -- Contains: rate_code + rate_full_name + rate_short_name + category + composition
    search_text TEXT,

    -- Timestamp fields for audit trail
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),

    -- Validation constraints
    CHECK (unit_quantity > 0),
    CHECK (total_cost >= 0),
    CHECK (materials_cost >= 0),
    CHECK (resources_cost >= 0)
);

-- ============================================================================
-- INDEXES for rates table
-- Description: Optimize query performance for common search patterns
-- ============================================================================

-- Index on rate_code (already covered by PRIMARY KEY, but explicit for documentation)
-- Used for: Direct rate lookups
CREATE INDEX IF NOT EXISTS idx_rate_code ON rates(rate_code);

-- Index on unit_type for filtering by measurement units
-- Used for: Queries filtering by "м3", "т", etc.
CREATE INDEX IF NOT EXISTS idx_unit_type ON rates(unit_type);

-- Index on category for hierarchical navigation
-- Used for: Browsing rates by category/section
CREATE INDEX IF NOT EXISTS idx_category ON rates(category);

-- Composite index for cost-based queries
-- Used for: Finding rates within cost ranges
CREATE INDEX IF NOT EXISTS idx_costs ON rates(total_cost, materials_cost, resources_cost);

-- Index on created_at for temporal queries
-- Used for: Recent additions, audit queries
CREATE INDEX IF NOT EXISTS idx_created_at ON rates(created_at);

-- ============================================================================
-- FTS5 VIRTUAL TABLE: rates_fts
-- Description: Full-text search index using FTS5 with Russian language support
-- Tokenizer: unicode61 with remove_diacritics=2 for proper Cyrillic handling
-- ============================================================================
CREATE VIRTUAL TABLE IF NOT EXISTS rates_fts USING fts5(
    rate_code,
    rate_full_name,
    rate_short_name,
    category,
    search_text,
    -- Configuration options
    tokenize='unicode61 remove_diacritics 2',
    -- Content table reference (external content table pattern)
    content='rates',
    content_rowid='rowid'
);

-- ============================================================================
-- TRIGGER: rates_fts_insert
-- Description: Automatically populate FTS index when new rate is inserted
-- Note: search_text must be pre-computed before INSERT (handled by DatabasePopulator)
-- ============================================================================
CREATE TRIGGER IF NOT EXISTS rates_fts_insert AFTER INSERT ON rates BEGIN
    -- Insert into FTS index using pre-computed search_text
    INSERT INTO rates_fts(rowid, rate_code, rate_full_name, rate_short_name, category, search_text)
    VALUES (
        NEW.rowid,
        NEW.rate_code,
        NEW.rate_full_name,
        NEW.rate_short_name,
        NEW.category,
        NEW.search_text
    );
END;

-- ============================================================================
-- TRIGGER: rates_fts_update
-- Description: Automatically update FTS index when rate is modified
-- Note: search_text should be updated before calling UPDATE
-- ============================================================================
CREATE TRIGGER IF NOT EXISTS rates_fts_update AFTER UPDATE ON rates BEGIN
    -- Update timestamp
    UPDATE rates SET updated_at = datetime('now')
    WHERE rate_code = NEW.rate_code AND updated_at != datetime('now');

    -- Update FTS index with new values
    UPDATE rates_fts
    SET
        rate_code = NEW.rate_code,
        rate_full_name = NEW.rate_full_name,
        rate_short_name = NEW.rate_short_name,
        category = NEW.category,
        search_text = NEW.search_text
    WHERE rowid = NEW.rowid;
END;

-- ============================================================================
-- TRIGGER: rates_fts_delete
-- Description: Automatically remove entry from FTS index when rate is deleted
-- ============================================================================
CREATE TRIGGER IF NOT EXISTS rates_fts_delete AFTER DELETE ON rates BEGIN
    DELETE FROM rates_fts WHERE rowid = OLD.rowid;
END;

-- ============================================================================
-- TABLE: resources
-- Description: Stores individual resources (materials, labor, machinery)
--              associated with construction rates
-- ============================================================================
CREATE TABLE IF NOT EXISTS resources (
    -- Primary key for the resource
    resource_id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Foreign key reference to the rates table
    rate_code TEXT NOT NULL,

    -- Resource code/identifier (e.g., material code, labor classification)
    resource_code TEXT NOT NULL,

    -- Type of resource (from Excel 'Тип строки' column)
    -- Possible values: 'Расценка', 'Ресурс', 'Состав работ', or any other row type
    resource_type TEXT NOT NULL,

    -- Name/description of the resource
    resource_name TEXT NOT NULL,

    -- Quantity of this resource required
    quantity NUMERIC NOT NULL DEFAULT 0,

    -- Unit of measurement for the resource
    unit TEXT NOT NULL,

    -- Unit cost/price
    unit_cost NUMERIC NOT NULL DEFAULT 0,

    -- Total cost (quantity * unit_cost)
    total_cost NUMERIC NOT NULL DEFAULT 0,

    -- Additional specifications or notes
    specifications TEXT,

    -- Timestamp fields
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),

    -- Foreign key constraint
    FOREIGN KEY (rate_code) REFERENCES rates(rate_code) ON DELETE CASCADE ON UPDATE CASCADE,

    -- Validation constraints
    CHECK (quantity >= 0),
    CHECK (unit_cost >= 0),
    CHECK (total_cost >= 0)
);

-- ============================================================================
-- INDEXES for resources table
-- Description: Optimize queries for resource lookups and aggregations
-- ============================================================================

-- Index on rate_code for joining with rates table
-- Used for: Finding all resources for a specific rate
CREATE INDEX IF NOT EXISTS idx_resources_rate_code ON resources(rate_code);

-- Index on resource_code for direct resource lookups
-- Used for: Finding all rates using a specific resource
CREATE INDEX IF NOT EXISTS idx_resources_resource_code ON resources(resource_code);

-- Index on resource_type for filtering by resource category
-- Used for: Queries filtering by material, labor, etc.
CREATE INDEX IF NOT EXISTS idx_resources_type ON resources(resource_type);

-- Composite index for resource cost analysis
-- Used for: Cost breakdown queries
CREATE INDEX IF NOT EXISTS idx_resources_costs ON resources(resource_type, unit_cost, total_cost);

-- ============================================================================
-- TABLE: rate_history
-- Description: Audit log for tracking changes to rates over time
-- ============================================================================
CREATE TABLE IF NOT EXISTS rate_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Reference to the rate
    rate_code TEXT NOT NULL,

    -- Type of change: 'INSERT', 'UPDATE', 'DELETE'
    change_type TEXT NOT NULL CHECK (change_type IN ('INSERT', 'UPDATE', 'DELETE')),

    -- Snapshot of data before change (JSON format)
    old_data TEXT,

    -- Snapshot of data after change (JSON format)
    new_data TEXT,

    -- Who made the change (user identifier)
    changed_by TEXT,

    -- When the change occurred
    changed_at TEXT NOT NULL DEFAULT (datetime('now')),

    -- Optional reason for the change
    change_reason TEXT,

    -- Foreign key constraint
    FOREIGN KEY (rate_code) REFERENCES rates(rate_code) ON DELETE CASCADE
);

-- Index on rate_code for audit trail queries
CREATE INDEX IF NOT EXISTS idx_history_rate_code ON rate_history(rate_code);

-- Index on changed_at for temporal queries
CREATE INDEX IF NOT EXISTS idx_history_timestamp ON rate_history(changed_at);

-- ============================================================================
-- VIEW: rates_with_resource_count
-- Description: Convenient view showing rates with their resource counts
-- ============================================================================
CREATE VIEW IF NOT EXISTS rates_with_resource_count AS
SELECT
    r.rate_code,
    r.rate_full_name,
    r.rate_short_name,
    r.unit_quantity,
    r.unit_type,
    r.total_cost,
    r.materials_cost,
    r.resources_cost,
    r.category,
    COUNT(res.resource_id) AS resource_count,
    SUM(CASE WHEN res.resource_type = 'material' THEN 1 ELSE 0 END) AS material_count,
    SUM(CASE WHEN res.resource_type = 'labor' THEN 1 ELSE 0 END) AS labor_count,
    SUM(CASE WHEN res.resource_type = 'machinery' THEN 1 ELSE 0 END) AS machinery_count,
    r.created_at,
    r.updated_at
FROM rates r
LEFT JOIN resources res ON r.rate_code = res.rate_code
GROUP BY r.rate_code;

-- ============================================================================
-- SAMPLE QUERIES FOR FTS5 SEARCH
-- Description: Example queries demonstrating full-text search capabilities
-- ============================================================================

-- Example 1: Simple full-text search
-- SELECT r.* FROM rates r
-- JOIN rates_fts fts ON r.rowid = fts.rowid
-- WHERE rates_fts MATCH 'бетон'
-- ORDER BY rank;

-- Example 2: Search with phrase matching
-- SELECT r.* FROM rates r
-- JOIN rates_fts fts ON r.rowid = fts.rowid
-- WHERE rates_fts MATCH '"монтаж конструкций"'
-- ORDER BY rank;

-- Example 3: Search in specific fields
-- SELECT r.* FROM rates r
-- JOIN rates_fts fts ON r.rowid = fts.rowid
-- WHERE rates_fts MATCH 'rate_full_name: земляные'
-- ORDER BY rank;

-- Example 4: Combined FTS and regular filters
-- SELECT r.* FROM rates r
-- JOIN rates_fts fts ON r.rowid = fts.rowid
-- WHERE rates_fts MATCH 'кирпич'
--   AND r.unit_type = 'м3'
--   AND r.total_cost BETWEEN 1000 AND 5000
-- ORDER BY rank;

-- Example 5: Boolean operators (AND, OR, NOT)
-- SELECT r.* FROM rates r
-- JOIN rates_fts fts ON r.rowid = fts.rowid
-- WHERE rates_fts MATCH 'бетон OR железобетон NOT монтаж'
-- ORDER BY rank;

-- ============================================================================
-- PERFORMANCE OPTIMIZATION SETTINGS
-- Description: Recommended SQLite PRAGMA settings for optimal performance
-- ============================================================================

-- Enable Write-Ahead Logging for better concurrency
-- PRAGMA journal_mode = WAL;

-- Optimize page size for modern systems
-- PRAGMA page_size = 4096;

-- Increase cache size (in pages, ~10MB with 4KB pages)
-- PRAGMA cache_size = 2500;

-- Enable foreign key constraints
-- PRAGMA foreign_keys = ON;

-- Optimize for read-heavy workloads
-- PRAGMA temp_store = MEMORY;

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================
