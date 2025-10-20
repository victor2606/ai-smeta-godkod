-- ============================================================================
-- Database Schema for Construction Rates Management System
-- Database: SQLite with FTS5 Full-Text Search
-- Version: 1.2
-- Created: 2025-10-19
-- Updated: 2025-10-20 (Task 9.2 - Added GЕСН/ФЕР hierarchy fields)
-- ============================================================================

-- ============================================================================
-- TABLE: rates
-- Description: Main table for storing construction rate information including
--              costs, units, descriptive information, and ГЭСН/ФЕР hierarchy
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

    -- ========================================================================
    -- ГЭСН/ФЕР HIERARCHY FIELDS (Task 9.2 - 2025-10-20)
    -- Description: 13 fields representing the full classification hierarchy
    -- Purpose: Enable navigation through construction rate reference books
    -- ========================================================================

    -- Level 1: Category (Категория | Тип)
    category_type TEXT,

    -- Level 2: Collection (Сборник | Код, Имя)
    collection_code TEXT,
    collection_name TEXT,

    -- Level 3: Department (Отдел | Код, Имя, Тип)
    department_code TEXT,
    department_name TEXT,
    department_type TEXT,

    -- Level 4: Section (Раздел | Код, Имя, Тип)
    section_code TEXT,
    section_name TEXT,   -- Replaces old 'category' field semantically
    section_type TEXT,

    -- Level 5: Subsection (Подраздел | Код, Имя)
    subsection_code TEXT,
    subsection_name TEXT,

    -- Level 6: Table (Таблица | Код, Имя)
    table_code TEXT,
    table_name TEXT,

    -- JSON composition data from DataAggregator (work composition details)
    composition TEXT,

    -- Concatenated searchable text (populated by trigger)
    -- Contains: rate_code + rate_full_name + rate_short_name + hierarchy fields + composition
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

-- Index on category for hierarchical navigation (backward compatibility)
-- Used for: Browsing rates by category/section
CREATE INDEX IF NOT EXISTS idx_category ON rates(category);

-- Composite index for cost-based queries
-- Used for: Finding rates within cost ranges
CREATE INDEX IF NOT EXISTS idx_costs ON rates(total_cost, materials_cost, resources_cost);

-- Index on created_at for temporal queries
-- Used for: Recent additions, audit queries
CREATE INDEX IF NOT EXISTS idx_created_at ON rates(created_at);

-- ============================================================================
-- NEW INDEXES for ГЭСН/ФЕР HIERARCHY (Task 9.2 - 2025-10-20)
-- Description: Enable fast navigation through classification hierarchy
-- ============================================================================

-- Index on collection for Level 2 navigation
CREATE INDEX IF NOT EXISTS idx_rates_collection ON rates(collection_code, collection_name);

-- Index on department for Level 3 navigation
CREATE INDEX IF NOT EXISTS idx_rates_department ON rates(department_code, department_name);

-- Composite index for full section navigation (Level 4)
CREATE INDEX IF NOT EXISTS idx_rates_section ON rates(section_code, section_name, section_type);

-- Index on subsection for Level 5 navigation
CREATE INDEX IF NOT EXISTS idx_rates_subsection ON rates(subsection_code, subsection_name);

-- Index on table for Level 6 navigation
CREATE INDEX IF NOT EXISTS idx_rates_table ON rates(table_code, table_name);

-- Composite index for hierarchical drill-down queries
-- Enables fast filtering by multiple hierarchy levels simultaneously
CREATE INDEX IF NOT EXISTS idx_rates_hierarchy_full ON rates(
    collection_code,
    department_code,
    section_code,
    subsection_code,
    table_code
);

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

-- Example 6: Hierarchical navigation by collection
-- SELECT * FROM rates
-- WHERE collection_code = 'ГЭСНп81'
-- ORDER BY section_code, subsection_code, table_code;

-- Example 7: Drill-down through hierarchy levels
-- SELECT
--     collection_name,
--     department_name,
--     section_name,
--     COUNT(*) as rate_count
-- FROM rates
-- WHERE collection_code = 'ГЭСНп81'
-- GROUP BY collection_name, department_name, section_name
-- ORDER BY department_code, section_code;

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
-- PHASE 1: HIGH PRIORITY EXTENSIONS (Task 9.1 Stage 2, 2025-10-20)
-- Description: Critical fields for construction cost estimation
-- Target: ~24-31% size increase from 125.65 MB baseline
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Extension: rates table - Overhead and Profit Margin
-- Purpose: Store НР (Накладные расходы) and СП (Сметная прибыль) percentages
-- Usage: Essential for calculating final construction costs
-- ----------------------------------------------------------------------------
ALTER TABLE rates ADD COLUMN overhead_rate REAL DEFAULT 0
    CHECK (overhead_rate >= 0);

ALTER TABLE rates ADD COLUMN profit_margin REAL DEFAULT 0
    CHECK (profit_margin >= 0);

-- Index for filtering by overhead/profit rates
CREATE INDEX IF NOT EXISTS idx_rates_overhead_profit
    ON rates(overhead_rate, profit_margin);

-- ----------------------------------------------------------------------------
-- Extension: resources table - Machinery and Labor Details
-- Purpose: Store detailed machinery operator costs and work hours
-- Fields:
--   - machinist_wage: Wage cost for machinery operators (Зарплата машиниста)
--   - machinist_labor_hours: Labor hours for machinist (Трудозатраты машиниста, чел.-ч)
--   - machinist_machine_hours: Machine operation hours (Затраты машин и механизмов, маш.-ч)
--   - cost_without_wages: Material/equipment cost excluding labor (Стоимость без ЗП)
--   - relocation_included: Flag indicating if relocation costs are included (1=yes, 0=no)
--   - personnel_code: Personnel classification code (Код персонала)
--   - machinist_grade: Skill grade/rank of the machinist (Разряд машиниста)
-- ----------------------------------------------------------------------------
ALTER TABLE resources ADD COLUMN machinist_wage REAL DEFAULT 0
    CHECK (machinist_wage >= 0);

ALTER TABLE resources ADD COLUMN machinist_labor_hours REAL DEFAULT 0
    CHECK (machinist_labor_hours >= 0);

ALTER TABLE resources ADD COLUMN machinist_machine_hours REAL DEFAULT 0
    CHECK (machinist_machine_hours >= 0);

ALTER TABLE resources ADD COLUMN cost_without_wages REAL DEFAULT 0
    CHECK (cost_without_wages >= 0);

ALTER TABLE resources ADD COLUMN relocation_included INTEGER DEFAULT 0
    CHECK (relocation_included IN (0, 1));

ALTER TABLE resources ADD COLUMN personnel_code TEXT;

ALTER TABLE resources ADD COLUMN machinist_grade INTEGER
    CHECK (machinist_grade IS NULL OR machinist_grade > 0);

-- Indexes for machinery cost analysis queries
CREATE INDEX IF NOT EXISTS idx_resources_machinist_costs
    ON resources(machinist_wage, machinist_labor_hours, machinist_machine_hours);

CREATE INDEX IF NOT EXISTS idx_resources_personnel
    ON resources(personnel_code, machinist_grade);

-- ----------------------------------------------------------------------------
-- NEW TABLE: resource_price_statistics
-- Purpose: Store current price statistics for resources across different rates
-- Usage: Price analysis, variance tracking, cost forecasting
-- Business Logic:
--   - Tracks min/max/mean/median prices for each resource
--   - Links resource pricing to specific rate codes
--   - Stores various cost breakdowns (material, total, position)
--   - unit_match flag indicates if resource unit matches rate unit
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS resource_price_statistics (
    -- Primary key
    price_stat_id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Foreign keys to resources and rates
    resource_code TEXT NOT NULL,
    rate_code TEXT NOT NULL,

    -- Price statistics (min/max/mean/median)
    current_price_min REAL DEFAULT 0 CHECK (current_price_min >= 0),
    current_price_max REAL DEFAULT 0 CHECK (current_price_max >= 0),
    current_price_mean REAL DEFAULT 0 CHECK (current_price_mean >= 0),
    current_price_median REAL DEFAULT 0 CHECK (current_price_median >= 0),

    -- Unit matching flag (1 if resource unit matches rate unit, 0 otherwise)
    unit_match INTEGER DEFAULT 0 CHECK (unit_match IN (0, 1)),

    -- Cost breakdowns
    material_resource_cost REAL DEFAULT 0 CHECK (material_resource_cost >= 0),
    total_resource_cost REAL DEFAULT 0 CHECK (total_resource_cost >= 0),
    total_material_cost REAL DEFAULT 0 CHECK (total_material_cost >= 0),
    total_position_cost REAL DEFAULT 0 CHECK (total_position_cost >= 0),

    -- Timestamps
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),

    -- Foreign key constraints
    -- NOTE: No FK on resource_code because resources(resource_code) is not PRIMARY KEY/UNIQUE
    --       (one resource can appear in multiple rates, making resource_code non-unique)
    FOREIGN KEY (rate_code) REFERENCES rates(rate_code) ON DELETE CASCADE,

    -- Ensure one price stat record per resource-rate combination
    UNIQUE(resource_code, rate_code)
);

-- ----------------------------------------------------------------------------
-- INDEXES for resource_price_statistics table
-- Purpose: Optimize price analysis and variance queries
-- ----------------------------------------------------------------------------

-- Index for resource-based price lookups
CREATE INDEX IF NOT EXISTS idx_price_stats_resource
    ON resource_price_statistics(resource_code);

-- Index for rate-based price lookups
CREATE INDEX IF NOT EXISTS idx_price_stats_rate
    ON resource_price_statistics(rate_code);

-- Composite index for price range queries
CREATE INDEX IF NOT EXISTS idx_price_stats_ranges
    ON resource_price_statistics(current_price_min, current_price_max, current_price_mean);

-- Index for unit matching queries
CREATE INDEX IF NOT EXISTS idx_price_stats_unit_match
    ON resource_price_statistics(unit_match, resource_code);

-- Index for cost analysis queries
CREATE INDEX IF NOT EXISTS idx_price_stats_costs
    ON resource_price_statistics(total_resource_cost, total_material_cost, total_position_cost);

-- Index for temporal queries
CREATE INDEX IF NOT EXISTS idx_price_stats_updated
    ON resource_price_statistics(updated_at);

-- ----------------------------------------------------------------------------
-- TRIGGER: update_price_stats_timestamp
-- Purpose: Automatically update the updated_at timestamp on modifications
-- ----------------------------------------------------------------------------
CREATE TRIGGER IF NOT EXISTS update_price_stats_timestamp
AFTER UPDATE ON resource_price_statistics
BEGIN
    UPDATE resource_price_statistics
    SET updated_at = datetime('now')
    WHERE price_stat_id = NEW.price_stat_id
      AND updated_at != datetime('now');
END;

-- ============================================================================
-- MIGRATION NOTES - PHASE 1 EXTENSIONS
-- ============================================================================
-- Migration Date: 2025-10-20
-- Schema Version: 1.1
--
-- Changes Summary:
-- 1. Extended 'rates' table with overhead_rate and profit_margin columns
-- 2. Extended 'resources' table with 7 new machinery/labor-related columns
-- 3. Added new 'resource_price_statistics' table for price analysis
-- 4. Created 9 new indexes for query optimization
-- 5. Added 1 trigger for automatic timestamp updates
--
-- Expected Impact:
-- - Database size increase: ~24-31% (from 125.65 MB baseline)
-- - New estimated size: ~155-165 MB
-- - Performance: Minimal impact due to proper indexing
-- - Backward Compatibility: Maintained (all new fields have defaults)
--
-- Rollback Strategy:
-- To rollback these changes (if needed):
--   1. DROP TABLE resource_price_statistics;
--   2. Drop all new indexes (idx_rates_overhead_profit, etc.)
--   3. Use ALTER TABLE to remove added columns (SQLite limitation: requires table recreation)
--
-- Testing Required:
--   - Verify ETL pipeline populates new fields correctly
--   - Test price statistics calculations
--   - Validate query performance with new indexes
--   - Confirm size increase is within expected range
-- ============================================================================

-- ============================================================================
-- MIGRATION NOTES - TASK 9.2 (P0 CRITICAL)
-- ============================================================================
-- Migration Date: 2025-10-20
-- Schema Version: 1.2
--
-- Changes Summary:
-- 1. Added 13 ГЭСН/ФЕР hierarchy fields to 'rates' table:
--    - category_type (Категория | Тип)
--    - collection_code, collection_name (Сборник)
--    - department_code, department_name, department_type (Отдел)
--    - section_code, section_name, section_type (Раздел)
--    - subsection_code, subsection_name (Подраздел)
--    - table_code, table_name (Таблица)
-- 2. Created 6 new indexes for hierarchical navigation
-- 3. Added sample queries demonstrating hierarchy usage
--
-- Purpose:
-- - Enable full navigation through ГЭСН/ФЕР classification hierarchy
-- - Support filtering and grouping by any hierarchy level
-- - Improve searchability and discoverability of rates
--
-- Expected Impact:
-- - Enables hierarchical drill-down queries
-- - Supports faceted search by classification
-- - Minimal performance impact due to proper indexing
-- - Full backward compatibility (all new fields nullable with defaults)
--
-- Next Steps (data_aggregator.py):
-- - Extract all 13 hierarchy fields from Excel columns 1-13
-- - Map to corresponding rate_record fields in _aggregate_single_rate()
-- - Include hierarchy fields in search_text for FTS5
--
-- Next Steps (db_populator.py):
-- - Update INSERT_RATE_SQL to include 13 new fields
-- - Update _map_rates_to_schema() to extract hierarchy values
-- - Ensure proper NULL handling for missing values
-- ============================================================================

-- ============================================================================
-- TASK 9.2 P2 (OPTIONAL) - Resource Mass and Services Tables
-- Migration Date: 2025-10-20
-- ============================================================================

-- ----------------------------------------------------------------------------
-- TABLE: resource_mass
-- Purpose: Store mass data for resources (Excel columns 64-66)
-- Fields: Масса | Имя, Значение, Ед. изм.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS resource_mass (
    mass_id INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_code TEXT NOT NULL,
    mass_name TEXT,          -- Масса | Имя (column 64)
    mass_value REAL,         -- Масса | Значение (column 65)
    mass_unit TEXT,          -- Масса | Ед. изм. (column 66)

    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (resource_code) REFERENCES resources(resource_code) ON DELETE CASCADE,
    CHECK (mass_value IS NULL OR mass_value >= 0)
);

CREATE INDEX IF NOT EXISTS idx_resource_mass_code ON resource_mass(resource_code);

-- ----------------------------------------------------------------------------
-- TABLE: services
-- Purpose: Store service data linked to rates (Excel columns 67-72)
-- Fields: Услуга.Категория, Услуга.Вид, Параметры.Услуга.*
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS services (
    service_id INTEGER PRIMARY KEY AUTOINCREMENT,
    rate_code TEXT NOT NULL,
    service_category TEXT,   -- Услуга.Категория (column 67)
    service_type TEXT,       -- Услуга.Вид (column 68)
    service_code TEXT,       -- Параметры.Услуга.Код (column 69)
    service_unit TEXT,       -- Параметры.Услуга.Ед. изм. (column 70)
    service_name TEXT,       -- Параметры.Услуга.Наименование (column 71)
    service_quantity REAL,   -- Параметры.Услуга.Кол-во (column 72)

    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (rate_code) REFERENCES rates(rate_code) ON DELETE CASCADE,
    CHECK (service_quantity IS NULL OR service_quantity >= 0)
);

CREATE INDEX IF NOT EXISTS idx_services_rate ON services(rate_code);
CREATE INDEX IF NOT EXISTS idx_services_type ON services(service_type, service_category);

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================
