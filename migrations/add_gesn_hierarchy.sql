-- ============================================================================
-- MIGRATION: Add ГЭСН/ФЕР Hierarchy Fields to rates table
-- Version: 1.2
-- Created: 2025-10-20
-- Task: 9.2 (P0 CRITICAL)
-- ============================================================================
--
-- DESCRIPTION:
-- This migration adds 13 hierarchy classification fields to the rates table
-- to enable full navigation through ГЭСН/ФЕР reference book structure.
--
-- SCOPE:
-- - Adds 13 new TEXT columns (all nullable)
-- - Creates 6 new indexes for hierarchical queries
-- - Maintains backward compatibility (all existing queries continue to work)
-- - Does NOT drop or recreate tables (preserves all existing data)
--
-- PREREQUISITES:
-- - Database: data/processed/estimates.db (223 MB, ~70K+ rates)
-- - Existing schema version: 1.1 (with overhead_rate, profit_margin fields)
-- - SQLite version: 3.35+ (supports ALTER TABLE ADD COLUMN)
--
-- ROLLBACK:
-- SQLite does not support DROP COLUMN natively. To rollback:
-- 1. Restore from backup: cp data/processed/estimates.db.backup data/processed/estimates.db
-- 2. Or recreate table without hierarchy fields (requires full rebuild)
--
-- ESTIMATED TIME: ~5-10 seconds for 223MB database
-- ============================================================================

-- Enable Write-Ahead Logging for safe migration
PRAGMA journal_mode = WAL;

-- Begin transaction for atomic migration
BEGIN TRANSACTION;

-- ============================================================================
-- STEP 1: Add 13 hierarchy fields to rates table
-- ============================================================================

-- Level 1: Category (Категория | Тип)
ALTER TABLE rates ADD COLUMN category_type TEXT;

-- Level 2: Collection (Сборник | Код, Имя)
ALTER TABLE rates ADD COLUMN collection_code TEXT;
ALTER TABLE rates ADD COLUMN collection_name TEXT;

-- Level 3: Department (Отдел | Код, Имя, Тип)
ALTER TABLE rates ADD COLUMN department_code TEXT;
ALTER TABLE rates ADD COLUMN department_name TEXT;
ALTER TABLE rates ADD COLUMN department_type TEXT;

-- Level 4: Section (Раздел | Код, Имя, Тип)
ALTER TABLE rates ADD COLUMN section_code TEXT;
ALTER TABLE rates ADD COLUMN section_name TEXT;
ALTER TABLE rates ADD COLUMN section_type TEXT;

-- Level 5: Subsection (Подраздел | Код, Имя)
ALTER TABLE rates ADD COLUMN subsection_code TEXT;
ALTER TABLE rates ADD COLUMN subsection_name TEXT;

-- Level 6: Table (Таблица | Код, Имя)
ALTER TABLE rates ADD COLUMN table_code TEXT;
ALTER TABLE rates ADD COLUMN table_name TEXT;

-- ============================================================================
-- STEP 2: Create indexes for hierarchical navigation
-- ============================================================================

-- Index on collection for Level 2 navigation
CREATE INDEX IF NOT EXISTS idx_rates_collection
    ON rates(collection_code, collection_name);

-- Index on department for Level 3 navigation
CREATE INDEX IF NOT EXISTS idx_rates_department
    ON rates(department_code, department_name);

-- Composite index for full section navigation (Level 4)
CREATE INDEX IF NOT EXISTS idx_rates_section
    ON rates(section_code, section_name, section_type);

-- Index on subsection for Level 5 navigation
CREATE INDEX IF NOT EXISTS idx_rates_subsection
    ON rates(subsection_code, subsection_name);

-- Index on table for Level 6 navigation
CREATE INDEX IF NOT EXISTS idx_rates_table
    ON rates(table_code, table_name);

-- Composite index for hierarchical drill-down queries
-- Enables fast filtering by multiple hierarchy levels simultaneously
CREATE INDEX IF NOT EXISTS idx_rates_hierarchy_full
    ON rates(
        collection_code,
        department_code,
        section_code,
        subsection_code,
        table_code
    );

-- ============================================================================
-- STEP 3: Verify migration success
-- ============================================================================

-- Count total columns (should be 28 after migration: 15 existing + 13 new)
SELECT
    COUNT(*) as total_columns,
    'Expected: 28 columns (15 existing + 13 hierarchy fields)' as verification
FROM pragma_table_info('rates');

-- Verify all 13 hierarchy fields exist
SELECT
    name,
    type,
    CASE WHEN name IN (
        'category_type',
        'collection_code', 'collection_name',
        'department_code', 'department_name', 'department_type',
        'section_code', 'section_name', 'section_type',
        'subsection_code', 'subsection_name',
        'table_code', 'table_name'
    ) THEN '✓ Hierarchy field'
    ELSE 'Existing field'
    END as field_category
FROM pragma_table_info('rates')
WHERE name IN (
    'category_type',
    'collection_code', 'collection_name',
    'department_code', 'department_name', 'department_type',
    'section_code', 'section_name', 'section_type',
    'subsection_code', 'subsection_name',
    'table_code', 'table_name'
)
ORDER BY name;

-- Count indexes on rates table (should be 13 total: 7 existing + 6 new)
SELECT
    COUNT(*) as total_indexes,
    'Expected: 13 indexes (7 existing + 6 hierarchy)' as verification
FROM sqlite_master
WHERE type='index'
    AND tbl_name='rates'
    AND name NOT LIKE 'sqlite_autoindex_%';

-- Commit transaction
COMMIT;

-- ============================================================================
-- STEP 4: Post-migration verification queries
-- ============================================================================

-- Verify all hierarchy fields are NULL (no data loss)
SELECT
    COUNT(*) as total_rates,
    SUM(CASE WHEN collection_code IS NULL THEN 1 ELSE 0 END) as null_collection,
    SUM(CASE WHEN section_name IS NULL THEN 1 ELSE 0 END) as null_section,
    SUM(CASE WHEN table_code IS NULL THEN 1 ELSE 0 END) as null_table,
    'All hierarchy fields should be NULL initially' as note
FROM rates;

-- Test sample queries to ensure backward compatibility
SELECT
    rate_code,
    rate_full_name,
    unit_type,
    total_cost,
    category,
    'Existing queries still work' as verification
FROM rates
LIMIT 3;

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================
--
-- NEXT STEPS:
-- 1. Run ETL pipeline to populate hierarchy fields:
--    python scripts/build_database.py
--
-- 2. Verify hierarchy data populated correctly:
--    SELECT collection_code, COUNT(*) FROM rates
--    WHERE collection_code IS NOT NULL
--    GROUP BY collection_code;
--
-- 3. Test hierarchical queries:
--    SELECT
--        collection_name,
--        department_name,
--        section_name,
--        COUNT(*) as rate_count
--    FROM rates
--    WHERE collection_code = 'ГЭСНп81'
--    GROUP BY collection_name, department_name, section_name
--    ORDER BY department_code, section_code;
--
-- ============================================================================
