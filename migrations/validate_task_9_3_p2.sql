-- Validate Task 9.3 P2: section classification fields
SELECT
    COUNT(*) as total_resources,
    COUNT(section2_name) as with_section2,
    COUNT(section3_name) as with_section3,
    ROUND(COUNT(section2_name) * 100.0 / COUNT(*), 2) as section2_coverage_pct,
    ROUND(COUNT(section3_name) * 100.0 / COUNT(*), 2) as section3_coverage_pct
FROM resources;

-- Sample data check
SELECT resource_code, resource_name, section2_name, section3_name
FROM resources
WHERE section2_name IS NOT NULL
LIMIT 5;
