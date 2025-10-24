#!/usr/bin/env python3
"""
Full system test for vector search integration.

Tests the complete pipeline:
1. Database connectivity
2. FTS5 search
3. Vector search (if embeddings exist)
4. MCP tools
5. Cost calculation
"""

import sys
import json
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.db_manager import DatabaseManager
from src.search.search_engine import SearchEngine
from src.search.cost_calculator import CostCalculator
from src.search.vector_engine import VectorSearchEngine


def test_database_connection(db_path):
    """Test database connectivity."""
    print("\n=== Test 1: Database Connection ===")
    try:
        db = DatabaseManager(db_path)
        db.connect()

        # Count rates
        result = db.execute_query("SELECT COUNT(*) FROM rates")
        count = result[0][0]
        print(f"✅ Database connected: {count} rates found")

        db.disconnect()
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


def test_fts5_search(db_path):
    """Test FTS5 full-text search."""
    print("\n=== Test 2: FTS5 Search ===")
    try:
        db = DatabaseManager(db_path)
        db.connect()

        search_engine = SearchEngine(db)
        results = search_engine.search("перегородки гипсокартон", limit=5)

        print(f"✅ FTS5 search: {len(results)} results found")
        if results:
            print(
                f"   Top result: {results[0]['rate_code']} - {results[0]['rate_full_name'][:60]}..."
            )

        db.disconnect()
        return True
    except Exception as e:
        print(f"❌ FTS5 search failed: {e}")
        return False


def test_vector_search(db_path):
    """Test vector search."""
    print("\n=== Test 3: Vector Search ===")
    try:
        db = DatabaseManager(db_path)
        db.connect()

        vector_engine = VectorSearchEngine(db)

        # Check embedding stats
        stats = vector_engine.get_embedding_stats()
        print(f"   Embedding coverage: {stats['embedding_coverage']:.1f}%")
        print(f"   Total rates: {stats['total_rates']}")
        print(f"   Embedded rates: {stats['embedded_rates']}")

        if stats["embedded_rates"] == 0:
            print("⚠️  No embeddings found - run generate_embeddings.py first")
            db.disconnect()
            return None

        # Try search
        results = vector_engine.search(
            "внутренние стены из листовых материалов", limit=5
        )

        print(f"✅ Vector search: {len(results)} results found")
        if results:
            print(
                f"   Top result: {results[0]['rate_code']} - {results[0]['rate_full_name'][:60]}..."
            )
            print(f"   Similarity: {results[0]['similarity']:.4f}")

        db.disconnect()
        return True
    except Exception as e:
        print(f"❌ Vector search failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_cost_calculation(db_path):
    """Test cost calculation."""
    print("\n=== Test 4: Cost Calculation ===")
    try:
        db = DatabaseManager(db_path)
        db.connect()

        # Get first rate code
        result = db.execute_query("SELECT rate_code FROM rates LIMIT 1")
        if not result:
            print("❌ No rates found in database")
            return False

        rate_code = result[0][0]

        calculator = CostCalculator(db)
        calc_result = calculator.calculate(rate_code, quantity=100.0)

        print(f"✅ Cost calculation for {rate_code}:")
        print(f"   Cost per unit: {calc_result['cost_per_unit']:.2f} руб.")
        print(f"   Total (100 units): {calc_result['calculated_total']:.2f} руб.")

        db.disconnect()
        return True
    except Exception as e:
        print(f"❌ Cost calculation failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_mcp_tools():
    """Test MCP tool imports."""
    print("\n=== Test 5: MCP Tools ===")
    try:
        # Try importing mcp_server
        import mcp_server

        # Check if vector_search tool exists
        has_vector_search = hasattr(mcp_server, "vector_search")

        print(f"✅ MCP server module loaded")
        print(f"   vector_search tool: {'✅' if has_vector_search else '❌'}")

        return True
    except Exception as e:
        print(f"❌ MCP tools failed: {e}")
        return False


def main():
    db_path = "data/processed/estimates.db"

    print("=" * 60)
    print("FULL SYSTEM TEST")
    print("=" * 60)

    # Check if database exists
    if not Path(db_path).exists():
        print(f"\n❌ Database not found: {db_path}")
        print("   Run ETL first: python -m src.etl")
        return

    results = {}

    # Run tests
    results["database"] = test_database_connection(db_path)
    results["fts5"] = test_fts5_search(db_path)
    results["vector"] = test_vector_search(db_path)
    results["calculation"] = test_cost_calculation(db_path)
    results["mcp"] = test_mcp_tools()

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)
    total = len(results)

    for name, result in results.items():
        status = (
            "✅ PASS"
            if result is True
            else ("❌ FAIL" if result is False else "⚠️  SKIP")
        )
        print(f"{status:10} {name}")

    print(f"\nTotal: {passed}/{total} passed, {failed} failed, {skipped} skipped")

    if failed == 0 and passed > 0:
        print("\n🎉 All critical tests passed!")
    elif results.get("vector") is None:
        print("\n⚠️  Vector search not tested - run generate_embeddings.py")
    else:
        print("\n⚠️  Some tests failed - check logs above")


if __name__ == "__main__":
    main()
