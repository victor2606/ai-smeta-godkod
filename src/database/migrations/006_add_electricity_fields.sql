-- Migration: Add electricity consumption fields
-- Date: 2025-10-20
-- Related to: Task 9.3 Phase 3 (Electricity data)

ALTER TABLE resources ADD COLUMN electricity_consumption REAL;
ALTER TABLE resources ADD COLUMN electricity_cost REAL;
