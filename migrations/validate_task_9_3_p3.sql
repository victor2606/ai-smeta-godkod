-- Validation Script for Task 9.3 Phase 3: Electricity Fields
-- Date: 2025-10-20
-- Purpose: Verify electricity_consumption and electricity_cost data loading

-- 1. Verify columns exist
SELECT '=== Column Existence Check ===' as check_type;
SELECT name, type
FROM pragma_table_info('resources')
WHERE name IN ('electricity_consumption', 'electricity_cost')
ORDER BY name;

-- 2. Count non-NULL electricity data
SELECT '=== Non-NULL Data Count ===' as check_type;
SELECT
    COUNT(*) as total_resources,
    COUNT(electricity_consumption) as has_consumption,
    COUNT(electricity_cost) as has_cost,
    ROUND(COUNT(electricity_consumption) * 100.0 / COUNT(*), 2) as consumption_fill_pct,
    ROUND(COUNT(electricity_cost) * 100.0 / COUNT(*), 2) as cost_fill_pct
FROM resources;

-- 3. Sample data with electricity values
SELECT '=== Sample Records with Electricity Data ===' as check_type;
SELECT
    resource_code,
    resource_name,
    electricity_consumption,
    electricity_cost,
    unit_cost,
    resource_type
FROM resources
WHERE electricity_consumption IS NOT NULL
   OR electricity_cost IS NOT NULL
ORDER BY electricity_consumption DESC NULLS LAST
LIMIT 10;

-- 4. Statistics on electricity consumption ranges
SELECT '=== Electricity Consumption Statistics ===' as check_type;
SELECT
    MIN(electricity_consumption) as min_consumption,
    MAX(electricity_consumption) as max_consumption,
    ROUND(AVG(electricity_consumption), 2) as avg_consumption,
    COUNT(DISTINCT electricity_consumption) as distinct_values
FROM resources
WHERE electricity_consumption IS NOT NULL;

-- 5. Statistics on electricity cost ranges
SELECT '=== Electricity Cost Statistics ===' as check_type;
SELECT
    MIN(electricity_cost) as min_cost,
    MAX(electricity_cost) as max_cost,
    ROUND(AVG(electricity_cost), 2) as avg_cost,
    COUNT(DISTINCT electricity_cost) as distinct_values
FROM resources
WHERE electricity_cost IS NOT NULL;

-- 6. Distribution by resource type
SELECT '=== Electricity Data by Resource Type ===' as check_type;
SELECT
    resource_type,
    COUNT(*) as total_count,
    COUNT(electricity_consumption) as has_consumption,
    COUNT(electricity_cost) as has_cost,
    ROUND(COUNT(electricity_consumption) * 100.0 / COUNT(*), 2) as consumption_pct
FROM resources
GROUP BY resource_type
ORDER BY has_consumption DESC;

-- 7. Check for data quality issues
SELECT '=== Data Quality Checks ===' as check_type;
SELECT
    'Records with consumption but no cost' as issue,
    COUNT(*) as count
FROM resources
WHERE electricity_consumption IS NOT NULL
  AND electricity_cost IS NULL
UNION ALL
SELECT
    'Records with cost but no consumption' as issue,
    COUNT(*) as count
FROM resources
WHERE electricity_cost IS NOT NULL
  AND electricity_consumption IS NULL
UNION ALL
SELECT
    'Records with negative consumption' as issue,
    COUNT(*) as count
FROM resources
WHERE electricity_consumption < 0
UNION ALL
SELECT
    'Records with negative cost' as issue,
    COUNT(*) as count
FROM resources
WHERE electricity_cost < 0;
