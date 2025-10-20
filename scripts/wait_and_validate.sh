#!/bin/bash
# ============================================================================
# Wait for ETL completion and run validation
# Task 9.2 P1 - Automated validation after ETL rebuild
# ============================================================================

set -e

ETL_LOG="/tmp/etl_rebuild_corrected.log"
DB_PATH="data/processed/estimates.db"
VALIDATION_SQL="migrations/validate_task_9_2_p1.sql"
RESULTS_FILE="validation_results_$(date +%Y%m%d_%H%M%S).txt"

echo "=========================================================================="
echo "ETL Monitoring and Validation Script"
echo "=========================================================================="
echo "ETL Log: $ETL_LOG"
echo "Database: $DB_PATH"
echo "Validation: $VALIDATION_SQL"
echo "Results: $RESULTS_FILE"
echo ""

# Function to check if ETL is still running
check_etl_running() {
    ps aux | grep "build_database.py" | grep -v grep > /dev/null
    return $?
}

# Monitor ETL progress
echo "Monitoring ETL progress..."
echo ""

while check_etl_running; do
    # Get last line from log
    LAST_LINE=$(tail -1 "$ETL_LOG" 2>/dev/null | grep -o "Converting XLSX:.*%" | tail -1)

    if [ -n "$LAST_LINE" ]; then
        echo -ne "\r$LAST_LINE                    "
    fi

    sleep 5
done

echo ""
echo ""
echo "✅ ETL process completed!"
echo ""

# Check if ETL was successful
if tail -50 "$ETL_LOG" | grep -q "Pipeline completed successfully"; then
    echo "✅ ETL completed successfully"
else
    echo "❌ ETL may have failed - check log: $ETL_LOG"
    exit 1
fi

# Wait a moment for file system
sleep 2

# Check database file exists and is not empty
if [ ! -f "$DB_PATH" ]; then
    echo "❌ Database file not found: $DB_PATH"
    exit 1
fi

DB_SIZE=$(du -h "$DB_PATH" | cut -f1)
echo "Database size: $DB_SIZE"
echo ""

# Run validation queries
echo "=========================================================================="
echo "Running validation queries..."
echo "=========================================================================="
echo ""

sqlite3 "$DB_PATH" < "$VALIDATION_SQL" | tee "$RESULTS_FILE"

echo ""
echo "=========================================================================="
echo "Validation completed!"
echo "=========================================================================="
echo "Results saved to: $RESULTS_FILE"
echo ""

# Parse validation results
echo "Parsing key metrics..."
echo ""

# Extract coverage percentages
COLLECTION_COV=$(grep -A1 "Hierarchy Population" "$RESULTS_FILE" | grep -o "collection_coverage_pct[^|]*" | tail -1 | awk '{print $NF}')
SECTION_COV=$(grep -A1 "Hierarchy Population" "$RESULTS_FILE" | grep -o "section_coverage_pct[^|]*" | tail -1 | awk '{print $NF}')
COST_COV=$(grep -A1 "Cost Population" "$RESULTS_FILE" | grep -o "total_cost_coverage_pct[^|]*" | tail -1 | awk '{print $NF}')
COMPLETENESS=$(grep -A1 "Overall Quality Score" "$RESULTS_FILE" | grep -o "completeness_pct[^|]*" | tail -1 | awk '{print $NF}')

echo "Key Metrics:"
echo "  - Collection Coverage: ${COLLECTION_COV:-N/A}%"
echo "  - Section Coverage: ${SECTION_COV:-N/A}%"
echo "  - Cost Coverage: ${COST_COV:-N/A}%"
echo "  - Overall Completeness: ${COMPLETENESS:-N/A}%"
echo ""

# Check pass/fail criteria
PASS=true

if [ -n "$COLLECTION_COV" ] && (( $(echo "$COLLECTION_COV < 80" | bc -l) )); then
    echo "❌ FAIL: Collection coverage < 80%"
    PASS=false
fi

if [ -n "$SECTION_COV" ] && (( $(echo "$SECTION_COV < 90" | bc -l) )); then
    echo "❌ FAIL: Section coverage < 90%"
    PASS=false
fi

if [ -n "$COST_COV" ] && (( $(echo "$COST_COV < 70" | bc -l) )); then
    echo "❌ FAIL: Cost coverage < 70%"
    PASS=false
fi

if [ -n "$COMPLETENESS" ] && (( $(echo "$COMPLETENESS < 70" | bc -l) )); then
    echo "❌ FAIL: Overall completeness < 70%"
    PASS=false
fi

echo ""

if [ "$PASS" = true ]; then
    echo "=========================================================================="
    echo "✅ ALL VALIDATION CRITERIA PASSED!"
    echo "=========================================================================="
    echo ""
    echo "Task 9.2 P1 is COMPLETE. Next steps:"
    echo "  1. Review full results: $RESULTS_FILE"
    echo "  2. Update docs/tasks/active-tasks.md"
    echo "  3. Update docs/tasks/TASK_9_2_P1_COMPLETION_REPORT.md with metrics"
    echo "  4. Commit changes with git"
    echo ""
    exit 0
else
    echo "=========================================================================="
    echo "⚠️  SOME VALIDATION CRITERIA FAILED"
    echo "=========================================================================="
    echo ""
    echo "Review results: $RESULTS_FILE"
    echo "Investigate issues and re-run ETL if needed"
    echo ""
    exit 1
fi
