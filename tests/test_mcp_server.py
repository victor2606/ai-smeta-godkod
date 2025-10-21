"""
Test Suite for MCP Server Implementation

Tests all 5 MCP tools with various scenarios including:
- Happy path scenarios
- Error handling
- Edge cases
- JSON serialization
- Auto-detection logic
"""

import json
import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import after adding to path
import mcp_server


class TestNaturalSearch:
    """Test suite for natural_search tool."""

    def test_natural_search_basic(self):
        """Test basic search functionality."""
        result_json = mcp_server.natural_search.fn("перегородки", limit=5)
        result = json.loads(result_json)

        assert result["success"] is True
        assert "results" in result
        assert isinstance(result["results"], list)
        assert result["count"] > 0
        assert result["count"] <= 5

        # Check result structure
        if result["results"]:
            first_result = result["results"][0]
            assert "rate_code" in first_result
            assert "rate_full_name" in first_result
            assert "cost_per_unit" in first_result
            assert "unit_measure_full" in first_result

    def test_natural_search_with_unit_filter(self):
        """Test search with unit type filter."""
        result_json = mcp_server.natural_search.fn("бетон", unit_type="м3", limit=10)
        result = json.loads(result_json)

        assert result["success"] is True
        assert "results" in result

        # All results should have м3 in unit description
        for item in result["results"]:
            assert "м3" in item["unit_measure_full"]

    def test_natural_search_empty_query(self):
        """Test search with empty query."""
        result_json = mcp_server.natural_search.fn("", limit=5)
        result = json.loads(result_json)

        assert "error" in result
        assert result["error"] == "Invalid input"

    def test_natural_search_no_results(self):
        """Test search that returns no results."""
        result_json = mcp_server.natural_search.fn("абракадабра123456", limit=5)
        result = json.loads(result_json)

        # Should succeed but with zero results
        assert result["success"] is True
        assert result["count"] == 0
        assert result["results"] == []

    def test_natural_search_limit_enforcement(self):
        """Test that limit is properly enforced."""
        result_json = mcp_server.natural_search.fn("бетон", limit=3)
        result = json.loads(result_json)

        assert result["success"] is True
        assert len(result["results"]) <= 3

    def test_natural_search_cost_formatting(self):
        """Test that costs are properly formatted to 2 decimals."""
        result_json = mcp_server.natural_search.fn("бетон", limit=1)
        result = json.loads(result_json)

        if result["results"]:
            item = result["results"][0]
            # Check that costs are numbers with max 2 decimal places
            cost_str = str(item["cost_per_unit"])
            if "." in cost_str:
                decimals = len(cost_str.split(".")[1])
                assert decimals <= 2


class TestQuickCalculate:
    """Test suite for quick_calculate tool."""

    def test_quick_calculate_with_rate_code(self):
        """Test calculation with direct rate code."""
        # First get a valid rate code
        search_result = json.loads(mcp_server.natural_search.fn("перегородки", limit=1))
        rate_code = search_result["results"][0]["rate_code"]

        result_json = mcp_server.quick_calculate.fn(rate_code, 100)
        result = json.loads(result_json)

        assert result["success"] is True
        assert result["search_used"] is False
        assert "rate_info" in result
        assert result["rate_info"]["rate_code"] == rate_code
        assert "calculated_total" in result
        assert "cost_per_unit" in result
        assert "materials" in result
        assert "resources" in result
        assert result["quantity"] == 100

    def test_quick_calculate_with_search_query(self):
        """Test calculation with search query (auto-detection)."""
        result_json = mcp_server.quick_calculate.fn("перегородки гипсокартон", 50)
        result = json.loads(result_json)

        assert result["success"] is True
        assert result["search_used"] is True
        assert "rate_info" in result
        assert result["quantity"] == 50

    def test_quick_calculate_invalid_quantity(self):
        """Test calculation with invalid quantity."""
        result_json = mcp_server.quick_calculate.fn("10-05-001-01", -10)
        result = json.loads(result_json)

        assert "error" in result
        assert result["error"] == "Invalid input"

    def test_quick_calculate_zero_quantity(self):
        """Test calculation with zero quantity."""
        result_json = mcp_server.quick_calculate.fn("10-05-001-01", 0)
        result = json.loads(result_json)

        assert "error" in result

    def test_quick_calculate_nonexistent_rate(self):
        """Test calculation with non-existent rate code."""
        result_json = mcp_server.quick_calculate.fn("INVALID-CODE-999", 10)
        result = json.loads(result_json)

        assert "error" in result

    def test_quick_calculate_cost_proportionality(self):
        """Test that costs scale proportionally with quantity."""
        search_result = json.loads(mcp_server.natural_search.fn("бетон", limit=1))
        rate_code = search_result["results"][0]["rate_code"]

        # Calculate for quantity 10
        result1_json = mcp_server.quick_calculate.fn(rate_code, 10)
        result1 = json.loads(result1_json)

        # Calculate for quantity 20
        result2_json = mcp_server.quick_calculate.fn(rate_code, 20)
        result2 = json.loads(result2_json)

        # Total should be approximately double (allowing for rounding)
        ratio = result2["calculated_total"] / result1["calculated_total"]
        assert 1.95 < ratio < 2.05


class TestShowRateDetails:
    """Test suite for show_rate_details tool."""

    def test_show_rate_details_basic(self):
        """Test basic rate details retrieval."""
        search_result = json.loads(mcp_server.natural_search.fn("бетон", limit=1))
        rate_code = search_result["results"][0]["rate_code"]

        result_json = mcp_server.show_rate_details.fn(rate_code, 100)
        result = json.loads(result_json)

        assert result["success"] is True
        assert "rate_info" in result
        assert "total_cost" in result
        assert "breakdown" in result
        assert isinstance(result["breakdown"], list)

    def test_show_rate_details_breakdown_structure(self):
        """Test that breakdown has correct structure."""
        search_result = json.loads(mcp_server.natural_search.fn("перегородки", limit=1))
        rate_code = search_result["results"][0]["rate_code"]

        result_json = mcp_server.show_rate_details.fn(rate_code, 50)
        result = json.loads(result_json)

        if result["breakdown"]:
            item = result["breakdown"][0]
            assert "resource_code" in item
            assert "resource_name" in item
            assert "resource_type" in item
            assert "adjusted_quantity" in item
            assert "unit" in item
            assert "unit_cost" in item
            assert "adjusted_cost" in item

    def test_show_rate_details_default_quantity(self):
        """Test rate details with default quantity."""
        search_result = json.loads(mcp_server.natural_search.fn("бетон", limit=1))
        rate_code = search_result["results"][0]["rate_code"]

        result_json = mcp_server.show_rate_details.fn(rate_code)
        result = json.loads(result_json)

        assert result["success"] is True
        assert result["quantity"] == 1.0

    def test_show_rate_details_invalid_rate(self):
        """Test details for non-existent rate."""
        result_json = mcp_server.show_rate_details.fn("INVALID-999", 10)
        result = json.loads(result_json)

        assert "error" in result


class TestCompareVariants:
    """Test suite for compare_variants tool."""

    def test_compare_variants_basic(self):
        """Test basic comparison of multiple rates."""
        # Get two different rate codes
        search_result = json.loads(mcp_server.natural_search.fn("перегородки", limit=2))
        rate_codes = [r["rate_code"] for r in search_result["results"][:2]]

        result_json = mcp_server.compare_variants.fn(rate_codes, 100)
        result = json.loads(result_json)

        assert result["success"] is True
        assert result["count"] == len(rate_codes)
        assert "comparison" in result
        assert len(result["comparison"]) == len(rate_codes)

    def test_compare_variants_sorting(self):
        """Test that results are sorted by cost."""
        search_result = json.loads(mcp_server.natural_search.fn("бетон", limit=3))
        rate_codes = [r["rate_code"] for r in search_result["results"][:3]]

        result_json = mcp_server.compare_variants.fn(rate_codes, 50)
        result = json.loads(result_json)

        # Check that results are sorted by total_for_quantity
        costs = [item["total_for_quantity"] for item in result["comparison"]]
        assert costs == sorted(costs)

    def test_compare_variants_difference_calculation(self):
        """Test that differences are calculated correctly."""
        search_result = json.loads(mcp_server.natural_search.fn("перегородки", limit=3))
        rate_codes = [r["rate_code"] for r in search_result["results"][:3]]

        result_json = mcp_server.compare_variants.fn(rate_codes, 100)
        result = json.loads(result_json)

        # Cheapest should have zero difference
        cheapest = result["comparison"][0]
        assert cheapest["difference_from_cheapest"] == 0.0
        assert cheapest["difference_percent"] == 0.0

        # Others should have positive differences
        for item in result["comparison"][1:]:
            assert item["difference_from_cheapest"] >= 0
            assert item["difference_percent"] >= 0

    def test_compare_variants_empty_list(self):
        """Test comparison with empty rate codes list."""
        result_json = mcp_server.compare_variants.fn([], 100)
        result = json.loads(result_json)

        assert "error" in result

    def test_compare_variants_invalid_quantity(self):
        """Test comparison with invalid quantity."""
        search_result = json.loads(mcp_server.natural_search.fn("бетон", limit=2))
        rate_codes = [r["rate_code"] for r in search_result["results"][:2]]

        result_json = mcp_server.compare_variants.fn(rate_codes, -10)
        result = json.loads(result_json)

        assert "error" in result


class TestFindSimilarRates:
    """Test suite for find_similar_rates tool."""

    def test_find_similar_rates_basic(self):
        """Test basic similarity search."""
        search_result = json.loads(mcp_server.natural_search.fn("перегородки", limit=1))
        rate_code = search_result["results"][0]["rate_code"]

        result_json = mcp_server.find_similar_rates.fn(rate_code, max_results=5)
        result = json.loads(result_json)

        assert result["success"] is True
        assert result["source_rate"] == rate_code
        assert "alternatives" in result
        assert isinstance(result["alternatives"], list)
        # Should include source rate plus alternatives
        assert len(result["alternatives"]) >= 1

    def test_find_similar_rates_includes_source(self):
        """Test that source rate is included in results."""
        search_result = json.loads(mcp_server.natural_search.fn("бетон", limit=1))
        rate_code = search_result["results"][0]["rate_code"]

        result_json = mcp_server.find_similar_rates.fn(rate_code, max_results=3)
        result = json.loads(result_json)

        # Source rate should be in alternatives
        rate_codes = [item["rate_code"] for item in result["alternatives"]]
        assert rate_code in rate_codes

    def test_find_similar_rates_max_results_limit(self):
        """Test that max_results is respected."""
        search_result = json.loads(mcp_server.natural_search.fn("перегородки", limit=1))
        rate_code = search_result["results"][0]["rate_code"]

        result_json = mcp_server.find_similar_rates.fn(rate_code, max_results=3)
        result = json.loads(result_json)

        # Should have source + up to 3 alternatives (4 total max)
        assert len(result["alternatives"]) <= 4

    def test_find_similar_rates_invalid_rate(self):
        """Test similarity search with invalid rate."""
        result_json = mcp_server.find_similar_rates.fn("INVALID-999", max_results=5)
        result = json.loads(result_json)

        assert "error" in result

    def test_find_similar_rates_structure(self):
        """Test that results have correct structure."""
        search_result = json.loads(mcp_server.natural_search.fn("бетон", limit=1))
        rate_code = search_result["results"][0]["rate_code"]

        result_json = mcp_server.find_similar_rates.fn(rate_code, max_results=2)
        result = json.loads(result_json)

        if result["alternatives"]:
            item = result["alternatives"][0]
            assert "rate_code" in item
            assert "rate_full_name" in item
            assert "cost_per_unit" in item
            assert "total_for_quantity" in item
            assert "difference_from_cheapest" in item
            assert "difference_percent" in item


class TestUtilityFunctions:
    """Test suite for utility functions."""

    def test_is_rate_code_detection(self):
        """Test rate code vs search query detection."""
        # Rate codes
        assert mcp_server.is_rate_code("10-05-001-01") is True
        assert mcp_server.is_rate_code("ГЭСНп81-01-001") is True
        assert mcp_server.is_rate_code("12-34-567-89") is True

        # Search queries
        assert mcp_server.is_rate_code("перегородки гипсокартон") is False
        assert mcp_server.is_rate_code("бетон монолитный класс В25") is False
        assert mcp_server.is_rate_code("устройство перегородок") is False

    def test_format_cost(self):
        """Test cost formatting function."""
        assert mcp_server.format_cost(123.456789) == 123.46
        assert mcp_server.format_cost(100.0) == 100.0
        assert mcp_server.format_cost(99.999) == 100.0

    def test_safe_json_serialize(self):
        """Test JSON serialization with special values."""
        import pandas as pd
        import numpy as np

        # Test with DataFrame
        df = pd.DataFrame({"a": [1, 2], "b": [3.5, np.nan]})
        result = mcp_server.safe_json_serialize(df)
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert isinstance(parsed, list)

        # Test with NaN
        data = {"value": np.nan}
        result = mcp_server.safe_json_serialize(data)
        parsed = json.loads(result)
        assert parsed["value"] is None

        # Test with Infinity
        data = {"value": np.inf}
        result = mcp_server.safe_json_serialize(data)
        parsed = json.loads(result)
        assert parsed["value"] is None


class TestIntegrationScenarios:
    """Integration tests for real-world scenarios."""

    def test_search_and_calculate_workflow(self):
        """Test complete workflow: search -> calculate."""
        # Step 1: Search for rates
        search_result = json.loads(mcp_server.natural_search.fn("перегородки", limit=3))
        assert search_result["success"] is True

        # Step 2: Calculate cost for first result
        rate_code = search_result["results"][0]["rate_code"]
        calc_result = json.loads(mcp_server.quick_calculate.fn(rate_code, 100))
        assert calc_result["success"] is True
        assert calc_result["quantity"] == 100

        # Step 3: Get detailed breakdown
        details_result = json.loads(mcp_server.show_rate_details.fn(rate_code, 100))
        assert details_result["success"] is True
        assert details_result["total_cost"] == calc_result["calculated_total"]

    def test_compare_and_alternatives_workflow(self):
        """Test comparison workflow: search -> compare -> find alternatives."""
        # Step 1: Search for rates
        search_result = json.loads(mcp_server.natural_search.fn("бетон", limit=3))
        rate_codes = [r["rate_code"] for r in search_result["results"][:3]]

        # Step 2: Compare rates
        compare_result = json.loads(mcp_server.compare_variants.fn(rate_codes, 50))
        assert compare_result["success"] is True

        # Step 3: Find alternatives for cheapest
        cheapest_code = compare_result["comparison"][0]["rate_code"]
        alternatives_result = json.loads(mcp_server.find_similar_rates.fn(cheapest_code, 5))
        assert alternatives_result["success"] is True

    def test_auto_calculate_with_description(self):
        """Test automatic calculation from description."""
        result = json.loads(mcp_server.quick_calculate.fn("устройство перегородок", 75))

        assert result["success"] is True
        assert result["search_used"] is True
        assert result["quantity"] == 75
        assert result["calculated_total"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
