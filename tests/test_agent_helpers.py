"""
Unit Tests for AI Agent Helper Functions

This module tests the agent_helpers utility functions that provide
formatted wrapper interfaces for AI agent dialog interactions.
"""

import pytest
import pandas as pd
from pathlib import Path
from unittest.mock import Mock, patch

from src.utils.agent_helpers import (
    natural_search,
    quick_calculate,
    show_rate_details,
    compare_variants,
    find_similar_rates,
    _is_rate_code,
    _get_cached,
    _set_cached,
    CACHE_FILE
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def mock_db_path():
    """Provide test database path."""
    return "data/processed/estimates.db"


@pytest.fixture
def sample_rate_data():
    """Sample rate data for mocking."""
    return {
        'rate_code': 'ГЭСНп81-01-001-01',
        'rate_full_name': 'Устройство перегородок из гипсокартона',
        'rate_short_name': 'Перегородки ГКЛ',
        'unit_measure_full': '100 м2',
        'cost_per_unit': 1383.20,
        'total_cost': 138320.18,
        'rank': -1.5
    }


@pytest.fixture
def sample_calculation():
    """Sample calculation result for mocking."""
    return {
        'rate_info': {
            'rate_code': 'ГЭСНп81-01-001-01',
            'rate_full_name': 'Устройство перегородок из гипсокартона',
            'unit_type': 'м2'
        },
        'base_cost': 138320.18,
        'cost_per_unit': 1383.20,
        'calculated_total': 207480.27,
        'materials': 95000.00,
        'resources': 112480.27,
        'quantity': 150
    }


@pytest.fixture
def cleanup_cache():
    """Cleanup cache file after tests."""
    yield
    if CACHE_FILE.exists():
        CACHE_FILE.unlink()


# ============================================================================
# Test Helper Functions
# ============================================================================

class TestHelperFunctions:
    """Test internal helper functions."""

    def test_is_rate_code_valid_patterns(self):
        """Test rate code detection with valid patterns."""
        valid_codes = [
            'ГЭСНп81-01-001-01',
            'ТСН-01-15-001',
            '10-05-001-01',
            'ФСС2020-01-001',
        ]

        for code in valid_codes:
            assert _is_rate_code(code), f"Should recognize '{code}' as rate code"

    def test_is_rate_code_invalid_patterns(self):
        """Test rate code detection with invalid patterns."""
        invalid_codes = [
            'бетон монолитный',
            'устройство перегородок',
            'hello world',
            '   ',
            '',
        ]

        for code in invalid_codes:
            assert not _is_rate_code(code), f"Should NOT recognize '{code}' as rate code"

    def test_cache_operations(self, cleanup_cache):
        """Test cache get/set operations."""
        test_key = "test:key:123"
        test_data = {'result': 'test_value', 'count': 42}

        # Initially no cache
        assert _get_cached(test_key) is None

        # Set cache
        _set_cached(test_key, test_data)

        # Retrieve cache
        cached = _get_cached(test_key)
        assert cached == test_data

    def test_cache_expiration(self, cleanup_cache):
        """Test cache expiration logic."""
        import json
        from datetime import datetime, timedelta

        # Create expired cache entry
        test_key = "expired:key"
        expired_time = (datetime.now() - timedelta(hours=25)).isoformat()

        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        cache_data = {
            test_key: {
                'timestamp': expired_time,
                'data': {'value': 'old'}
            }
        }

        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f)

        # Should return None for expired cache
        assert _get_cached(test_key) is None


# ============================================================================
# Test natural_search Function
# ============================================================================

class TestNaturalSearch:
    """Test natural_search function."""

    @patch('src.utils.agent_helpers.DatabaseManager')
    @patch('src.utils.agent_helpers.SearchEngine')
    def test_natural_search_success(self, mock_search_engine, mock_db_manager, sample_rate_data, cleanup_cache):
        """Test successful natural search."""
        # Setup mocks
        mock_engine_instance = Mock()
        mock_engine_instance.search.return_value = [sample_rate_data]
        mock_search_engine.return_value = mock_engine_instance

        # Execute search
        result = natural_search("бетон монолитный", limit=5)

        # Verify results
        assert 'results' in result
        assert 'formatted_text' in result
        assert 'query_info' in result
        assert len(result['results']) == 1
        assert result['results'][0]['rate_code'] == 'ГЭСНп81-01-001-01'
        assert result['query_info']['result_count'] == 1

    def test_natural_search_empty_query(self):
        """Test natural search with empty query."""
        result = natural_search("", limit=5)

        assert 'error' in result['query_info']
        assert result['results'] == []
        assert "Error" in result['formatted_text']

    @patch('src.utils.agent_helpers.DatabaseManager')
    @patch('src.utils.agent_helpers.SearchEngine')
    def test_natural_search_with_filters(self, mock_search_engine, mock_db_manager, sample_rate_data):
        """Test natural search with filters."""
        mock_engine_instance = Mock()
        mock_engine_instance.search.return_value = [sample_rate_data]
        mock_search_engine.return_value = mock_engine_instance

        filters = {
            'unit_type': 'м2',
            'min_cost': 1000,
            'max_cost': 5000
        }

        result = natural_search("перегородки", filters=filters, limit=10)

        # Verify search was called with filters
        mock_engine_instance.search.assert_called_once()
        call_args = mock_engine_instance.search.call_args
        assert call_args[1]['filters'] == filters

    @patch('src.utils.agent_helpers.DatabaseManager')
    @patch('src.utils.agent_helpers.SearchEngine')
    def test_natural_search_limit_cap(self, mock_search_engine, mock_db_manager, sample_rate_data):
        """Test that search limit is capped at 100."""
        mock_engine_instance = Mock()
        mock_engine_instance.search.return_value = []
        mock_search_engine.return_value = mock_engine_instance

        result = natural_search("test", limit=500)

        # Verify limit was capped
        call_args = mock_engine_instance.search.call_args
        assert call_args[1]['limit'] == 100


# ============================================================================
# Test quick_calculate Function
# ============================================================================

class TestQuickCalculate:
    """Test quick_calculate function."""

    @patch('src.utils.agent_helpers.DatabaseManager')
    @patch('src.utils.agent_helpers.CostCalculator')
    def test_quick_calculate_with_rate_code(self, mock_calculator, mock_db_manager, sample_calculation):
        """Test quick calculation using direct rate code."""
        # Setup mocks
        mock_calc_instance = Mock()
        mock_calc_instance.calculate.return_value = sample_calculation
        mock_calculator.return_value = mock_calc_instance

        # Execute calculation
        result = quick_calculate("ГЭСНп81-01-001-01", 150)

        # Verify results
        assert 'calculation' in result
        assert 'formatted_text' in result
        assert result['rate_used'] == 'ГЭСНп81-01-001-01'
        assert result['search_performed'] is False
        assert result['calculation']['calculated_total'] == 207480.27

    @patch('src.utils.agent_helpers.DatabaseManager')
    @patch('src.utils.agent_helpers.SearchEngine')
    @patch('src.utils.agent_helpers.CostCalculator')
    def test_quick_calculate_with_description(self, mock_calculator, mock_search_engine,
                                               mock_db_manager, sample_rate_data, sample_calculation):
        """Test quick calculation using description (auto-search)."""
        # Setup search mock
        mock_engine_instance = Mock()
        mock_engine_instance.search.return_value = [sample_rate_data]
        mock_search_engine.return_value = mock_engine_instance

        # Setup calculator mock
        mock_calc_instance = Mock()
        mock_calc_instance.calculate.return_value = sample_calculation
        mock_calculator.return_value = mock_calc_instance

        # Execute calculation
        result = quick_calculate("бетон монолитный", 50)

        # Verify search was performed
        assert result['search_performed'] is True
        assert result['rate_used'] == 'ГЭСНп81-01-001-01'

    def test_quick_calculate_invalid_quantity(self):
        """Test quick calculation with invalid quantity."""
        result = quick_calculate("ГЭСНп81-01-001-01", -10)

        assert 'error' in result['formatted_text'].lower()
        assert result['calculation'] == {}

    @patch('src.utils.agent_helpers.DatabaseManager')
    @patch('src.utils.agent_helpers.SearchEngine')
    def test_quick_calculate_no_search_results(self, mock_search_engine, mock_db_manager):
        """Test quick calculation when search returns no results."""
        mock_engine_instance = Mock()
        mock_engine_instance.search.return_value = []
        mock_search_engine.return_value = mock_engine_instance

        result = quick_calculate("несуществующий материал", 10)

        assert 'error' in result['formatted_text'].lower()
        assert result['search_performed'] is True
        assert result['rate_used'] == ''


# ============================================================================
# Test show_rate_details Function
# ============================================================================

class TestShowRateDetails:
    """Test show_rate_details function."""

    @patch('src.utils.agent_helpers.DatabaseManager')
    @patch('src.utils.agent_helpers.CostCalculator')
    def test_show_rate_details_success(self, mock_calculator, mock_db_manager):
        """Test successful rate details retrieval."""
        # Setup mock
        breakdown = {
            'rate_info': {
                'rate_code': 'ГЭСНп81-01-001-01',
                'rate_full_name': 'Устройство перегородок',
                'unit_type': 'м2'
            },
            'base_cost': 138320.18,
            'materials': 95000.00,
            'resources': 43320.18,
            'breakdown': [
                {
                    'resource_code': 'М-001',
                    'resource_type': 'Материал',
                    'resource_name': 'Гипсокартон ГКЛ 12.5мм',
                    'original_quantity': 200,
                    'unit': 'м2',
                    'unit_cost': 150.50,
                    'adjusted_cost': 30100.00
                }
            ]
        }

        mock_calc_instance = Mock()
        mock_calc_instance.get_detailed_breakdown.return_value = breakdown
        mock_calculator.return_value = mock_calc_instance

        # Execute
        result = show_rate_details("ГЭСНп81-01-001-01")

        # Verify
        assert 'rate' in result
        assert 'resources' in result
        assert 'formatted_text' in result
        assert result['rate']['rate_code'] == 'ГЭСНп81-01-001-01'
        assert len(result['resources']) == 1

    def test_show_rate_details_empty_code(self):
        """Test show_rate_details with empty rate code."""
        result = show_rate_details("")

        assert 'error' in result['formatted_text'].lower()
        assert result['rate'] == {}
        assert result['resources'] == []


# ============================================================================
# Test compare_variants Function
# ============================================================================

class TestCompareVariants:
    """Test compare_variants function."""

    @patch('src.utils.agent_helpers.natural_search')
    @patch('src.utils.agent_helpers.RateComparator')
    def test_compare_variants_success(self, mock_comparator, mock_natural_search):
        """Test successful variant comparison."""
        # Setup search mock - return search results
        mock_natural_search.side_effect = [
            {
                'results': [{'rate_code': 'RATE-001', 'rate_full_name': 'Test Rate 1'}],
                'formatted_text': 'search output',
                'query_info': {'result_count': 1}
            },
            {
                'results': [{'rate_code': 'RATE-002', 'rate_full_name': 'Test Rate 2'}],
                'formatted_text': 'search output',
                'query_info': {'result_count': 1}
            }
        ]

        # Setup comparator mock
        comparison_df = pd.DataFrame([
            {
                'rate_code': 'RATE-001',
                'rate_full_name': 'Test Rate 1',
                'unit_type': 'м2',
                'cost_per_unit': 1000,
                'total_for_quantity': 100000,
                'materials_for_quantity': 50000,
                'difference_from_cheapest': 0,
                'difference_percent': 0
            },
            {
                'rate_code': 'RATE-002',
                'rate_full_name': 'Test Rate 2',
                'unit_type': 'м2',
                'cost_per_unit': 1200,
                'total_for_quantity': 120000,
                'materials_for_quantity': 60000,
                'difference_from_cheapest': 20000,
                'difference_percent': 20.0
            }
        ])

        mock_comp_instance = Mock()
        mock_comp_instance.compare.return_value = comparison_df
        mock_comparator.return_value = mock_comp_instance

        # Execute
        result = compare_variants(["бетон B25", "бетон B30"], quantity=100)

        # Verify
        assert 'comparison' in result
        assert 'formatted_text' in result
        assert len(result['rates_found']) == 2
        assert not result['comparison'].empty

    def test_compare_variants_insufficient_descriptions(self):
        """Test compare_variants with less than 2 descriptions."""
        result = compare_variants(["single item"], quantity=100)

        assert 'error' in result['formatted_text'].lower()
        assert result['comparison'].empty

    def test_compare_variants_invalid_quantity(self):
        """Test compare_variants with invalid quantity."""
        result = compare_variants(["item1", "item2"], quantity=0)

        assert 'error' in result['formatted_text'].lower()
        assert result['comparison'].empty


# ============================================================================
# Test find_similar_rates Function
# ============================================================================

class TestFindSimilarRates:
    """Test find_similar_rates function."""

    @patch('src.utils.agent_helpers.RateComparator')
    def test_find_similar_rates_success(self, mock_comparator):
        """Test successful alternative rate discovery."""
        # Setup mock
        alternatives_df = pd.DataFrame([
            {
                'rate_code': 'SOURCE-001',
                'rate_full_name': 'Source Rate',
                'unit_type': 'м2',
                'cost_per_unit': 1000,
                'total_for_quantity': 100000,
                'materials_for_quantity': 50000,
                'difference_from_cheapest': 0,
                'difference_percent': 0
            },
            {
                'rate_code': 'ALT-001',
                'rate_full_name': 'Alternative Rate 1',
                'unit_type': 'м2',
                'cost_per_unit': 950,
                'total_for_quantity': 95000,
                'materials_for_quantity': 47500,
                'difference_from_cheapest': 5000,
                'difference_percent': 5.0
            }
        ])

        mock_comp_instance = Mock()
        mock_comp_instance.find_alternatives.return_value = alternatives_df
        mock_comparator.return_value = mock_comp_instance

        # Execute
        result = find_similar_rates("SOURCE-001", max_results=5)

        # Verify
        assert 'alternatives' in result
        assert 'formatted_text' in result
        assert result['source_rate'] == 'SOURCE-001'
        assert result['alternatives_count'] == 1  # Excluding source rate

    def test_find_similar_rates_empty_code(self):
        """Test find_similar_rates with empty rate code."""
        result = find_similar_rates("")

        assert 'error' in result['formatted_text'].lower()
        assert result['alternatives'].empty

    def test_find_similar_rates_invalid_max_results(self):
        """Test find_similar_rates with invalid max_results."""
        result = find_similar_rates("RATE-001", max_results=0)

        assert 'error' in result['formatted_text'].lower()
        assert result['alternatives'].empty

    @patch('src.utils.agent_helpers.RateComparator')
    def test_find_similar_rates_no_alternatives(self, mock_comparator):
        """Test find_similar_rates when no alternatives found."""
        mock_comp_instance = Mock()
        mock_comp_instance.find_alternatives.return_value = pd.DataFrame()
        mock_comparator.return_value = mock_comp_instance

        result = find_similar_rates("RATE-001")

        assert 'warning' in result['formatted_text'].lower()
        assert result['alternatives_count'] == 0


# ============================================================================
# Integration Tests (require actual database)
# ============================================================================

@pytest.mark.integration
class TestIntegration:
    """Integration tests that require actual database."""

    def test_full_workflow_integration(self):
        """Test complete workflow from search to comparison."""
        db_path = "data/processed/estimates.db"

        # Skip if database doesn't exist
        if not Path(db_path).exists():
            pytest.skip("Database not available for integration test")

        # 1. Search for rates
        search_result = natural_search("бетон", limit=3, db_path=db_path)
        assert len(search_result['results']) > 0

        # 2. Calculate cost for first result
        rate_code = search_result['results'][0]['rate_code']
        calc_result = quick_calculate(rate_code, 100, db_path=db_path)
        assert calc_result['calculation']['calculated_total'] > 0

        # 3. Show details
        details_result = show_rate_details(rate_code, db_path=db_path)
        assert details_result['rate']['rate_code'] == rate_code

        # 4. Find alternatives
        alt_result = find_similar_rates(rate_code, max_results=3, db_path=db_path)
        assert not alt_result['alternatives'].empty
