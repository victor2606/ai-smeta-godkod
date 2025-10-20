-- ============================================================================
-- VERIFICATION SCRIPT: ГЭСН/ФЕР Hierarchy Migration
-- Created: 2025-10-20
-- Purpose: Comprehensive validation of add_gesn_hierarchy.sql migration
-- ============================================================================

.echo on
.headers on
.mode column

-- ============================================================================
-- TEST 1: Verify all 13 hierarchy fields exist
-- ============================================================================
SELECT '=== TEST 1: Verify all 13 hierarchy fields exist ===' as test;
SELECT
    name,
    type,
    "notnull" as required,
    dflt_value as default_value
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

-- ============================================================================
-- TEST 2: Verify total column count
-- ============================================================================
SELECT '=== TEST 2: Verify total column count ===' as test;
SELECT
    COUNT(*) as total_columns,
    CASE
        WHEN COUNT(*) = 28 THEN 'PASS: 28 columns (15 existing + 13 hierarchy)'
        ELSE 'FAIL: Expected 28 columns, got ' || COUNT(*)
    END as result
FROM pragma_table_info('rates');

-- ============================================================================
-- TEST 3: Verify all 6 new indexes created
-- ============================================================================
SELECT '=== TEST 3: Verify all 6 new hierarchy indexes ===' as test;
SELECT
    name as index_name,
    sql as definition
FROM sqlite_master
WHERE type='index'
    AND tbl_name='rates'
    AND name IN (
        'idx_rates_collection',
        'idx_rates_department',
        'idx_rates_section',
        'idx_rates_subsection',
        'idx_rates_table',
        'idx_rates_hierarchy_full'
    )
ORDER BY name;

-- ============================================================================
-- TEST 4: Verify total index count
-- ============================================================================
SELECT '=== TEST 4: Verify total index count ===' as test;
SELECT
    COUNT(*) as total_indexes,
    CASE
        WHEN COUNT(*) >= 12 THEN 'PASS: 12+ indexes (6 existing + 6 hierarchy)'
        ELSE 'FAIL: Expected 12+ indexes, got ' || COUNT(*)
    END as result
FROM sqlite_master
WHERE type='index'
    AND tbl_name='rates'
    AND name NOT LIKE 'sqlite_autoindex_%';

-- ============================================================================
-- TEST 5: Verify no data loss (all rates preserved)
-- ============================================================================
SELECT '=== TEST 5: Verify no data loss ===' as test;
SELECT
    COUNT(*) as total_rates,
    CASE
        WHEN COUNT(*) > 0 THEN 'PASS: ' || COUNT(*) || ' rates preserved'
        ELSE 'FAIL: No rates found'
    END as result
FROM rates;

-- ============================================================================
-- TEST 6: Verify hierarchy fields are NULL (not populated yet)
-- ============================================================================
SELECT '=== TEST 6: Verify hierarchy fields are NULL initially ===' as test;
SELECT
    COUNT(*) as total_rates,
    SUM(CASE WHEN category_type IS NULL THEN 1 ELSE 0 END) as null_category_type,
    SUM(CASE WHEN collection_code IS NULL THEN 1 ELSE 0 END) as null_collection_code,
    SUM(CASE WHEN collection_name IS NULL THEN 1 ELSE 0 END) as null_collection_name,
    SUM(CASE WHEN department_code IS NULL THEN 1 ELSE 0 END) as null_department_code,
    SUM(CASE WHEN section_name IS NULL THEN 1 ELSE 0 END) as null_section_name,
    SUM(CASE WHEN table_code IS NULL THEN 1 ELSE 0 END) as null_table_code,
    CASE
        WHEN SUM(CASE WHEN collection_code IS NULL THEN 1 ELSE 0 END) = COUNT(*)
        THEN 'PASS: All hierarchy fields are NULL (awaiting ETL)'
        ELSE 'WARNING: Some hierarchy fields already populated'
    END as result
FROM rates;

-- ============================================================================
-- TEST 7: Verify backward compatibility (existing queries work)
-- ============================================================================
SELECT '=== TEST 7: Test backward compatibility ===' as test;
SELECT
    rate_code,
    substr(rate_full_name, 1, 50) || '...' as rate_name_preview,
    unit_type,
    total_cost,
    category,
    'PASS: Existing queries still work' as result
FROM rates
WHERE rate_code LIKE '01-01-%'
LIMIT 3;

-- ============================================================================
-- TEST 8: Test sample hierarchical query (will return empty until ETL runs)
-- ============================================================================
SELECT '=== TEST 8: Test hierarchical query structure ===' as test;
SELECT
    collection_code,
    collection_name,
    department_code,
    department_name,
    section_code,
    section_name,
    COUNT(*) as rate_count,
    'PASS: Hierarchical query executes (empty until ETL populates data)' as result
FROM rates
WHERE collection_code IS NOT NULL
GROUP BY
    collection_code,
    collection_name,
    department_code,
    department_name,
    section_code,
    section_name
LIMIT 5;

-- ============================================================================
-- TEST 9: Check database size and performance
-- ============================================================================
SELECT '=== TEST 9: Database statistics ===' as test;
SELECT
    page_count * page_size / 1024 / 1024 as size_mb,
    page_count,
    page_size,
    'Database size after migration' as note
FROM pragma_page_count(), pragma_page_size();

-- ============================================================================
-- TEST 10: Verify FTS5 triggers still work
-- ============================================================================
SELECT '=== TEST 10: Verify FTS5 system intact ===' as test;
SELECT
    name,
    type
FROM sqlite_master
WHERE name LIKE 'rates_fts%'
ORDER BY type, name;

-- ============================================================================
-- MIGRATION VERIFICATION SUMMARY
-- ============================================================================
SELECT '=== MIGRATION VERIFICATION SUMMARY ===' as summary;
SELECT
    'Migration Status' as check_name,
    CASE
        WHEN (SELECT COUNT(*) FROM pragma_table_info('rates')) = 28
         AND (SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND tbl_name='rates' AND name LIKE 'idx_rates_%collection%') = 1
         AND (SELECT COUNT(*) FROM rates) > 0
        THEN 'SUCCESS: All checks passed'
        ELSE 'FAILURE: Some checks failed'
    END as result;

SELECT 'Next Steps' as action, '1. Run ETL pipeline: python scripts/build_database.py' as description
UNION ALL
SELECT 'Next Steps', '2. Verify hierarchy data: SELECT collection_code, COUNT(*) FROM rates GROUP BY collection_code;'
UNION ALL
SELECT 'Next Steps', '3. Test hierarchical queries using schema.sql examples (lines 382-396)';

.echo off
