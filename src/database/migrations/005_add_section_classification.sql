-- Task 9.3 P2: Add section classification fields (Excel cols 35-36)
-- Expected coverage: 25.66% of resources
-- Purpose: Additional hierarchy for machinery and equipment classification

ALTER TABLE resources ADD COLUMN section2_name TEXT;
ALTER TABLE resources ADD COLUMN section3_name TEXT;

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_resources_section2 ON resources(section2_name);
CREATE INDEX IF NOT EXISTS idx_resources_section3 ON resources(section3_name);
