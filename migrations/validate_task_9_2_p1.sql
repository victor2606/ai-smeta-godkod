-- ============================================================================
-- Validation Queries for TASK 9.2 P1 (Critical Priority)
-- Purpose: Verify that ГЭСН/ФЕР hierarchy and aggregated costs are populated
-- Date: 2025-10-20
-- ============================================================================

-- ============================================================================
-- TEST 1: Verify ГЭСН/ФЕР hierarchy fields are populated
-- Expected: Most rates should have at least collection_code and section_name
-- ============================================================================
SELECT
    'Hierarchy Population' as test_name,
    COUNT(*) as total_rates,
    COUNT(category_type) as has_category_type,
    COUNT(collection_code) as has_collection_code,
    COUNT(collection_name) as has_collection_name,
    COUNT(department_code) as has_department_code,
    COUNT(section_code) as has_section_code,
    COUNT(section_name) as has_section_name,
    COUNT(subsection_code) as has_subsection_code,
    COUNT(table_code) as has_table_code,
    ROUND(COUNT(collection_code) * 100.0 / COUNT(*), 2) as collection_coverage_pct,
    ROUND(COUNT(section_name) * 100.0 / COUNT(*), 2) as section_coverage_pct
FROM rates;

-- ============================================================================
-- TEST 2: Verify aggregated costs are populated (not all zeros)
-- Expected: Significant number of rates should have non-zero costs
-- ============================================================================
SELECT
    'Cost Population' as test_name,
    COUNT(*) as total_rates,
    COUNT(CASE WHEN total_cost > 0 THEN 1 END) as has_total_cost,
    COUNT(CASE WHEN materials_cost > 0 THEN 1 END) as has_materials_cost,
    COUNT(CASE WHEN resources_cost > 0 THEN 1 END) as has_resources_cost,
    ROUND(AVG(total_cost), 2) as avg_total_cost,
    ROUND(AVG(materials_cost), 2) as avg_materials_cost,
    ROUND(AVG(resources_cost), 2) as avg_resources_cost,
    ROUND(COUNT(CASE WHEN total_cost > 0 THEN 1 END) * 100.0 / COUNT(*), 2) as total_cost_coverage_pct
FROM rates;

-- ============================================================================
-- TEST 3: Check collection distribution (top 10 collections)
-- Expected: Multiple collections with meaningful rates distribution
-- ============================================================================
SELECT
    'Top Collections' as test_name,
    collection_code,
    collection_name,
    COUNT(*) as rate_count,
    ROUND(AVG(total_cost), 2) as avg_total_cost
FROM rates
WHERE collection_code IS NOT NULL
GROUP BY collection_code, collection_name
ORDER BY rate_count DESC
LIMIT 10;

-- ============================================================================
-- TEST 4: Hierarchical drill-down example (verify multi-level navigation)
-- Expected: Rates should be properly organized by hierarchy levels
-- ============================================================================
SELECT
    'Hierarchy Drill-Down' as test_name,
    collection_name,
    department_name,
    section_name,
    COUNT(*) as rate_count,
    ROUND(AVG(total_cost), 2) as avg_total_cost
FROM rates
WHERE collection_code IS NOT NULL
GROUP BY collection_name, department_name, section_name
ORDER BY collection_code, department_code, section_code
LIMIT 20;

-- ============================================================================
-- TEST 5: Verify cost relationship (total = resources + materials)
-- Expected: For rates with all costs populated, relationship should hold
-- Note: May have small rounding differences, allow ±1% tolerance
-- ============================================================================
SELECT
    'Cost Relationship Check' as test_name,
    COUNT(*) as rates_with_all_costs,
    COUNT(CASE
        WHEN ABS((resources_cost + materials_cost) - total_cost) <= (total_cost * 0.01)
        THEN 1
    END) as valid_cost_relationships,
    COUNT(CASE
        WHEN ABS((resources_cost + materials_cost) - total_cost) > (total_cost * 0.01)
        THEN 1
    END) as invalid_cost_relationships,
    ROUND(AVG(total_cost), 2) as avg_total_cost,
    ROUND(AVG(resources_cost + materials_cost), 2) as avg_sum_of_parts
FROM rates
WHERE total_cost > 0
  AND resources_cost > 0
  AND materials_cost > 0;

-- ============================================================================
-- TEST 6: Sample rates with full hierarchy and costs
-- Expected: Real data examples showing complete information
-- ============================================================================
SELECT
    'Sample Data' as test_name,
    rate_code,
    rate_full_name,
    collection_name,
    section_name,
    total_cost,
    materials_cost,
    resources_cost
FROM rates
WHERE collection_code IS NOT NULL
  AND total_cost > 0
ORDER BY total_cost DESC
LIMIT 5;

-- ============================================================================
-- TEST 7: Check for NULL patterns in hierarchy
-- Expected: Identify which hierarchy levels have most gaps
-- ============================================================================
SELECT
    'NULL Pattern Analysis' as test_name,
    ROUND(COUNT(CASE WHEN category_type IS NULL THEN 1 END) * 100.0 / COUNT(*), 2) as category_type_null_pct,
    ROUND(COUNT(CASE WHEN collection_code IS NULL THEN 1 END) * 100.0 / COUNT(*), 2) as collection_null_pct,
    ROUND(COUNT(CASE WHEN department_code IS NULL THEN 1 END) * 100.0 / COUNT(*), 2) as department_null_pct,
    ROUND(COUNT(CASE WHEN section_code IS NULL THEN 1 END) * 100.0 / COUNT(*), 2) as section_null_pct,
    ROUND(COUNT(CASE WHEN subsection_code IS NULL THEN 1 END) * 100.0 / COUNT(*), 2) as subsection_null_pct,
    ROUND(COUNT(CASE WHEN table_code IS NULL THEN 1 END) * 100.0 / COUNT(*), 2) as table_null_pct
FROM rates;

-- ============================================================================
-- TEST 8: Edge cases - rates with costs but no hierarchy
-- Expected: Should be minimal (ideally 0)
-- ============================================================================
SELECT
    'Orphaned Rates' as test_name,
    COUNT(*) as rates_with_cost_no_hierarchy
FROM rates
WHERE total_cost > 0
  AND collection_code IS NULL
  AND section_code IS NULL;

-- ============================================================================
-- TEST 9: Edge cases - rates with hierarchy but no costs
-- Expected: Some rates may legitimately have no costs (e.g., informational)
-- ============================================================================
SELECT
    'Rates Without Costs' as test_name,
    COUNT(*) as rates_with_hierarchy_no_cost
FROM rates
WHERE (collection_code IS NOT NULL OR section_code IS NOT NULL)
  AND total_cost = 0;

-- ============================================================================
-- TEST 10: Overall data quality score
-- Expected: High percentage of complete records (>80%)
-- ============================================================================
SELECT
    'Overall Quality Score' as test_name,
    COUNT(*) as total_rates,
    COUNT(CASE
        WHEN collection_code IS NOT NULL
        AND section_name IS NOT NULL
        AND total_cost > 0
        THEN 1
    END) as complete_rates,
    ROUND(COUNT(CASE
        WHEN collection_code IS NOT NULL
        AND section_name IS NOT NULL
        AND total_cost > 0
        THEN 1
    END) * 100.0 / COUNT(*), 2) as completeness_pct
FROM rates;

-- ============================================================================
-- PASS/FAIL CRITERIA FOR TASK 9.2 P1
-- ============================================================================
-- ✅ PASS if:
--    1. collection_coverage_pct > 80%
--    2. section_coverage_pct > 90%
--    3. total_cost_coverage_pct > 70%
--    4. completeness_pct > 70%
--    5. invalid_cost_relationships < 5% of rates_with_all_costs
--
-- ❌ FAIL if any of the above criteria not met
-- ============================================================================
