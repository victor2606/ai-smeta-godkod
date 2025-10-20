-- Task 9.3 Phase 1: Add resource quantity parameter field
-- Excel column 24: "Параметры | Ресурс.Количество" (51.31% fill rate)
-- Data type: TEXT (preserves string format from Excel)
-- This field differs from 'quantity' (col 22, NUMERIC) as it stores the raw text representation

ALTER TABLE resources ADD COLUMN resource_quantity_parameter TEXT;
