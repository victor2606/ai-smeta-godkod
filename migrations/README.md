# Database Migration: ГЭСН/ФЕР Hierarchy Fields

## Overview
This migration adds 13 hierarchy classification fields to the `rates` table, enabling full navigation through ГЭСН/ФЕР construction reference book structure.

**Migration Date:** 2025-10-20
**Schema Version:** 1.1 → 1.2
**Task:** 9.2 (P0 CRITICAL)
**Status:** ✅ COMPLETED SUCCESSFULLY

---

## Migration Results

### Database Statistics
- **Total Rates:** 28,686 (preserved, no data loss)
- **Database Size:** 224 MB (increased from 223 MB)
- **Total Columns:** 28 (15 existing + 13 new hierarchy fields)
- **Total Indexes:** 12 (6 existing + 6 new hierarchy indexes)

### Fields Added (13)
All fields are nullable TEXT columns with no default values:

| Level | Field Name | Description |
|-------|------------|-------------|
| 1 | `category_type` | Категория \| Тип |
| 2 | `collection_code` | Сборник \| Код |
| 2 | `collection_name` | Сборник \| Имя |
| 3 | `department_code` | Отдел \| Код |
| 3 | `department_name` | Отдел \| Имя |
| 3 | `department_type` | Отдел \| Тип |
| 4 | `section_code` | Раздел \| Код |
| 4 | `section_name` | Раздел \| Имя |
| 4 | `section_type` | Раздел \| Тип |
| 5 | `subsection_code` | Подраздел \| Код |
| 5 | `subsection_name` | Подраздел \| Имя |
| 6 | `table_code` | Таблица \| Код |
| 6 | `table_name` | Таблица \| Имя |

### Indexes Created (6)

1. **idx_rates_collection** - Collection level navigation
   ```sql
   CREATE INDEX idx_rates_collection ON rates(collection_code, collection_name);
   ```

2. **idx_rates_department** - Department level navigation
   ```sql
   CREATE INDEX idx_rates_department ON rates(department_code, department_name);
   ```

3. **idx_rates_section** - Section level navigation
   ```sql
   CREATE INDEX idx_rates_section ON rates(section_code, section_name, section_type);
   ```

4. **idx_rates_subsection** - Subsection level navigation
   ```sql
   CREATE INDEX idx_rates_subsection ON rates(subsection_code, subsection_name);
   ```

5. **idx_rates_table** - Table level navigation
   ```sql
   CREATE INDEX idx_rates_table ON rates(table_code, table_name);
   ```

6. **idx_rates_hierarchy_full** - Multi-level drill-down queries
   ```sql
   CREATE INDEX idx_rates_hierarchy_full ON rates(
       collection_code, department_code, section_code, subsection_code, table_code
   );
   ```

---

## Verification Tests

All 10 verification tests passed:

- ✅ **TEST 1:** All 13 hierarchy fields exist
- ✅ **TEST 2:** Total column count = 28
- ✅ **TEST 3:** All 6 new indexes created
- ✅ **TEST 4:** Total index count = 12
- ✅ **TEST 5:** No data loss (28,686 rates preserved)
- ✅ **TEST 6:** All hierarchy fields are NULL (awaiting ETL)
- ✅ **TEST 7:** Backward compatibility verified
- ✅ **TEST 8:** Hierarchical queries execute correctly
- ✅ **TEST 9:** Database size and performance acceptable
- ✅ **TEST 10:** FTS5 system intact

---

## Files Created

### Migration Scripts
- **`add_gesn_hierarchy.sql`** - Main migration script (ALTER TABLE + CREATE INDEX)
- **`verify_gesn_hierarchy.sql`** - Comprehensive verification tests

### Backup
- **`data/processed/estimates.db.backup`** - Pre-migration backup (223 MB)

---

## Next Steps

### 1. Run ETL Pipeline
The hierarchy fields are currently NULL. Run the ETL pipeline to populate them from Excel source files:

```bash
python scripts/build_database.py
```

This will:
- Extract hierarchy data from Excel columns 1-13
- Populate all 13 fields in the database
- Update FTS5 search index with hierarchy data

### 2. Verify Data Population
After ETL runs, verify hierarchy fields are populated:

```sql
-- Check collection distribution
SELECT collection_code, COUNT(*) as rate_count
FROM rates
WHERE collection_code IS NOT NULL
GROUP BY collection_code
ORDER BY collection_code;

-- Check hierarchy completeness
SELECT
    COUNT(*) as total_rates,
    SUM(CASE WHEN collection_code IS NOT NULL THEN 1 ELSE 0 END) as with_collection,
    SUM(CASE WHEN section_name IS NOT NULL THEN 1 ELSE 0 END) as with_section,
    SUM(CASE WHEN table_code IS NOT NULL THEN 1 ELSE 0 END) as with_table
FROM rates;
```

### 3. Test Hierarchical Navigation
Use the sample queries from `src/database/schema.sql` (lines 382-396):

```sql
-- Example: Navigate by collection
SELECT * FROM rates
WHERE collection_code = 'ГЭСНп81'
ORDER BY section_code, subsection_code, table_code;

-- Example: Hierarchical drill-down
SELECT
    collection_name,
    department_name,
    section_name,
    COUNT(*) as rate_count
FROM rates
WHERE collection_code = 'ГЭСНп81'
GROUP BY collection_name, department_name, section_name
ORDER BY department_code, section_code;
```

---

## Rollback Procedure

If rollback is needed:

### Option 1: Restore from Backup (Recommended)
```bash
cp data/processed/estimates.db.backup data/processed/estimates.db
```

### Option 2: Manual Rollback (Not Recommended)
SQLite does not support `DROP COLUMN`. Manual rollback requires:
1. Create new table without hierarchy fields
2. Copy all data except hierarchy columns
3. Drop old table and rename new table
4. Recreate all indexes and triggers

**Recommendation:** Always use backup restoration for rollback.

---

## Migration Impact

### Pros
- ✅ Enables full ГЭСН/ФЕР classification hierarchy navigation
- ✅ Supports filtering/grouping by any hierarchy level
- ✅ Improves searchability and discoverability
- ✅ Backward compatible (existing queries work unchanged)
- ✅ Minimal size increase (+1 MB)

### Cons
- ⚠️ Requires ETL pipeline update to populate fields
- ⚠️ Adds 6 indexes (minimal performance impact)
- ⚠️ SQLite rollback requires table recreation

### Performance
- **Index Creation Time:** ~1-2 seconds
- **Database Size Increase:** +1 MB (0.4%)
- **Query Performance:** No degradation (proper indexing)

---

## Technical Details

### SQLite Version Compatibility
- **Minimum SQLite Version:** 3.35+
- **Features Used:** ALTER TABLE ADD COLUMN
- **Journal Mode:** WAL (Write-Ahead Logging)

### Transaction Safety
- Migration runs in single transaction (ACID compliant)
- Automatic rollback on error
- No data loss risk

### Backward Compatibility
- ✅ All existing queries work unchanged
- ✅ No breaking changes to API
- ✅ FTS5 triggers remain functional
- ✅ All views and triggers intact

---

## Related Files

### Schema
- `/Users/vic/git/n8npiplines-bim/src/database/schema.sql` (lines 43-71, 121-144)

### ETL Code (requires update)
- `/Users/vic/git/n8npiplines-bim/src/etl/data_aggregator.py` (lines 219-244) ✅ Already updated
- `/Users/vic/git/n8npiplines-bim/src/etl/db_populator.py` (lines 603-620) ✅ Already updated

### Documentation
- `/Users/vic/git/n8npiplines-bim/docs/example_queries.md` (add hierarchy examples)

---

## Contact

For issues or questions about this migration:
- **Task Reference:** docs/tasks/active-tasks.md (Task 9.2)
- **Schema Version:** 1.2
- **Migration Date:** 2025-10-20
