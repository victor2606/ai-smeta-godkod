"""
Unit Tests for Search Engine Module

Tests for full-text search and code-based search functionality including:
- SearchEngine initialization
- Full-text search with FTS5
- Search filters (unit_type, cost range, category)
- Code-based prefix search
- Edge cases and error handling
"""

import pytest
import sqlite3
from unittest.mock import Mock
from src.search.search_engine import SearchEngine
from src.database.db_manager import DatabaseManager


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db_manager():
    """Create mock DatabaseManager instance."""
    mock = Mock(spec=DatabaseManager)
    return mock


@pytest.fixture
def search_engine(mock_db_manager):
    """Create SearchEngine instance with mock database manager."""
    return SearchEngine(mock_db_manager)


# ============================================================================
# Test: SearchEngine Initialization
# ============================================================================

class TestSearchEngineInit:
    """Test suite for SearchEngine initialization."""

    def test_initialization_with_valid_db_manager(self, mock_db_manager):
        """Test that SearchEngine initializes with valid DatabaseManager."""
        engine = SearchEngine(mock_db_manager)
        assert engine is not None
        assert isinstance(engine, SearchEngine)

    def test_stores_db_manager_reference(self, mock_db_manager):
        """Test that SearchEngine stores database manager reference."""
        engine = SearchEngine(mock_db_manager)
        assert engine.db_manager is mock_db_manager


# ============================================================================
# Test: search() method
# ============================================================================

class TestSearch:
    """Test suite for full-text search functionality."""

    def test_search_with_simple_query(self, search_engine, mock_db_manager, mocker):
        """Test basic full-text search with simple query."""
        # Mock prepare_fts_query
        mocker.patch('src.search.search_engine.prepare_fts_query', return_value='бетон*')

        # Mock database results
        mock_db_manager.execute_query.return_value = [
            ('RATE-001', 'Бетон монолитный', 'Бетон', 100, 'м3', 15000.0, -0.5)
        ]

        results = search_engine.search('бетон')

        assert len(results) == 1
        assert results[0]['rate_code'] == 'RATE-001'
        assert results[0]['rate_full_name'] == 'Бетон монолитный'
        assert results[0]['rate_short_name'] == 'Бетон'

    def test_search_with_empty_query_raises_valueerror(self, search_engine):
        """Test that empty query raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            search_engine.search('')

        with pytest.raises(ValueError, match="cannot be empty"):
            search_engine.search('   ')

    def test_search_with_filters_unit_type(self, search_engine, mock_db_manager, mocker):
        """Test search with unit_type filter."""
        mocker.patch('src.search.search_engine.prepare_fts_query', return_value='бетон*')

        mock_db_manager.execute_query.return_value = [
            ('RATE-001', 'Бетон монолитный', 'Бетон', 100, 'м3', 15000.0, -0.5)
        ]

        results = search_engine.search('бетон', filters={'unit_type': 'м3'})

        # Verify SQL was called with unit_type filter
        call_args = mock_db_manager.execute_query.call_args
        sql = call_args[0][0]
        params = call_args[0][1]

        assert 'r.unit_type = ?' in sql
        assert 'м3' in params

    def test_search_with_filters_min_cost(self, search_engine, mock_db_manager, mocker):
        """Test search with min_cost filter."""
        mocker.patch('src.search.search_engine.prepare_fts_query', return_value='бетон*')

        mock_db_manager.execute_query.return_value = []

        search_engine.search('бетон', filters={'min_cost': 1000})

        # Verify SQL was called with min_cost filter
        call_args = mock_db_manager.execute_query.call_args
        sql = call_args[0][0]
        params = call_args[0][1]

        assert 'r.total_cost >= ?' in sql
        assert 1000 in params

    def test_search_with_filters_max_cost(self, search_engine, mock_db_manager, mocker):
        """Test search with max_cost filter."""
        mocker.patch('src.search.search_engine.prepare_fts_query', return_value='бетон*')

        mock_db_manager.execute_query.return_value = []

        search_engine.search('бетон', filters={'max_cost': 5000})

        # Verify SQL was called with max_cost filter
        call_args = mock_db_manager.execute_query.call_args
        sql = call_args[0][0]
        params = call_args[0][1]

        assert 'r.total_cost <= ?' in sql
        assert 5000 in params

    def test_search_with_filters_category(self, search_engine, mock_db_manager, mocker):
        """Test search with category filter."""
        mocker.patch('src.search.search_engine.prepare_fts_query', return_value='бетон*')

        mock_db_manager.execute_query.return_value = []

        search_engine.search('бетон', filters={'category': 'ГЭСНп81-01'})

        # Verify SQL was called with category filter
        call_args = mock_db_manager.execute_query.call_args
        sql = call_args[0][0]
        params = call_args[0][1]

        assert 'r.category = ?' in sql
        assert 'ГЭСНп81-01' in params

    def test_search_with_multiple_filters(self, search_engine, mock_db_manager, mocker):
        """Test search with multiple filters applied simultaneously."""
        mocker.patch('src.search.search_engine.prepare_fts_query', return_value='бетон*')

        mock_db_manager.execute_query.return_value = [
            ('RATE-001', 'Бетон монолитный', 'Бетон', 100, 'м3', 3500.0, -0.5)
        ]

        results = search_engine.search('бетон', filters={
            'unit_type': 'м3',
            'min_cost': 1000,
            'max_cost': 5000,
            'category': 'ГЭСНп81-01'
        })

        # Verify all filters were applied
        call_args = mock_db_manager.execute_query.call_args
        sql = call_args[0][0]
        params = call_args[0][1]

        assert 'r.unit_type = ?' in sql
        assert 'r.total_cost >= ?' in sql
        assert 'r.total_cost <= ?' in sql
        assert 'r.category = ?' in sql
        assert len(results) == 1

    def test_search_returns_correct_fields(self, search_engine, mock_db_manager, mocker):
        """Test that search returns all required fields."""
        mocker.patch('src.search.search_engine.prepare_fts_query', return_value='бетон*')

        mock_db_manager.execute_query.return_value = [
            ('RATE-001', 'Бетон монолитный', 'Бетон', 100, 'м3', 15000.0, -0.5)
        ]

        results = search_engine.search('бетон')

        assert len(results) == 1
        result = results[0]

        # Check all required fields are present
        assert 'rate_code' in result
        assert 'rate_full_name' in result
        assert 'rate_short_name' in result
        assert 'unit_measure_full' in result
        assert 'cost_per_unit' in result
        assert 'total_cost' in result
        assert 'rank' in result

    def test_search_calculates_cost_per_unit_correctly(self, search_engine, mock_db_manager, mocker):
        """Test that cost_per_unit is calculated correctly."""
        mocker.patch('src.search.search_engine.prepare_fts_query', return_value='бетон*')

        mock_db_manager.execute_query.return_value = [
            ('RATE-001', 'Бетон монолитный', 'Бетон', 100, 'м3', 15000.0, -0.5),
            ('RATE-002', 'Бетон тяжелый', 'Бетон Т', 50, 'м3', 10000.0, -0.3)
        ]

        results = search_engine.search('бетон')

        assert results[0]['cost_per_unit'] == 150.0  # 15000 / 100
        assert results[1]['cost_per_unit'] == 200.0  # 10000 / 50

    def test_search_handles_no_results(self, search_engine, mock_db_manager, mocker):
        """Test that search handles empty result set."""
        mocker.patch('src.search.search_engine.prepare_fts_query', return_value='несуществующий*')

        mock_db_manager.execute_query.return_value = []

        results = search_engine.search('несуществующий запрос')

        assert results == []
        assert isinstance(results, list)

    def test_search_respects_limit(self, search_engine, mock_db_manager, mocker):
        """Test that search respects the limit parameter."""
        mocker.patch('src.search.search_engine.prepare_fts_query', return_value='бетон*')

        # Mock 50 results
        mock_results = [
            (f'RATE-{i:03d}', f'Бетон {i}', f'Б{i}', 100, 'м3', 15000.0, -0.5)
            for i in range(50)
        ]
        mock_db_manager.execute_query.return_value = mock_results

        results = search_engine.search('бетон', limit=50)

        # Verify limit was passed to SQL query
        call_args = mock_db_manager.execute_query.call_args
        params = call_args[0][1]
        assert 50 in params

    def test_search_caps_limit_at_1000(self, search_engine, mock_db_manager, mocker):
        """Test that search caps limit at maximum of 1000."""
        mocker.patch('src.search.search_engine.prepare_fts_query', return_value='бетон*')

        mock_db_manager.execute_query.return_value = []

        search_engine.search('бетон', limit=5000)

        # Verify limit was capped at 1000
        call_args = mock_db_manager.execute_query.call_args
        params = call_args[0][1]
        assert 1000 in params
        assert 5000 not in params

    def test_search_handles_database_error(self, search_engine, mock_db_manager, mocker):
        """Test that search handles database errors properly."""
        mocker.patch('src.search.search_engine.prepare_fts_query', return_value='бетон*')

        mock_db_manager.execute_query.side_effect = sqlite3.Error("Database error")

        with pytest.raises(sqlite3.Error, match="Database error"):
            search_engine.search('бетон')

    def test_search_builds_unit_measure_full(self, search_engine, mock_db_manager, mocker):
        """Test that unit_measure_full is formatted correctly."""
        mocker.patch('src.search.search_engine.prepare_fts_query', return_value='бетон*')

        mock_db_manager.execute_query.return_value = [
            ('RATE-001', 'Бетон монолитный', 'Бетон', 100, 'м3', 15000.0, -0.5)
        ]

        results = search_engine.search('бетон')

        assert results[0]['unit_measure_full'] == '100 м3'


# ============================================================================
# Test: search_by_code() method
# ============================================================================

class TestSearchByCode:
    """Test suite for code-based prefix search functionality."""

    def test_search_by_code_with_valid_prefix(self, search_engine, mock_db_manager):
        """Test search by rate code with valid prefix."""
        mock_db_manager.execute_query.return_value = [
            ('ГЭСНп81-01-001-01', 'Устройство перегородок', 'Перегородки', 100, 'м2', 13832.0)
        ]

        results = search_engine.search_by_code('ГЭСНп81-01')

        assert len(results) == 1
        assert results[0]['rate_code'] == 'ГЭСНп81-01-001-01'

        # Verify LIKE pattern was used
        call_args = mock_db_manager.execute_query.call_args
        sql = call_args[0][0]
        params = call_args[0][1]

        assert 'LIKE ?' in sql
        assert params[0] == 'ГЭСНп81-01%'

    def test_search_by_code_with_empty_code_raises_valueerror(self, search_engine):
        """Test that empty rate code raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            search_engine.search_by_code('')

        with pytest.raises(ValueError, match="cannot be empty"):
            search_engine.search_by_code('   ')

    def test_search_by_code_returns_correct_fields(self, search_engine, mock_db_manager):
        """Test that search_by_code returns all required fields."""
        mock_db_manager.execute_query.return_value = [
            ('ГЭСНп81-01-001-01', 'Устройство перегородок', 'Перегородки', 100, 'м2', 13832.0)
        ]

        results = search_engine.search_by_code('ГЭСНп81-01')

        assert len(results) == 1
        result = results[0]

        # Check all required fields are present
        assert 'rate_code' in result
        assert 'rate_full_name' in result
        assert 'rate_short_name' in result
        assert 'unit_measure_full' in result
        assert 'cost_per_unit' in result
        assert 'total_cost' in result
        assert 'rank' in result

    def test_search_by_code_handles_no_results(self, search_engine, mock_db_manager):
        """Test that search_by_code handles empty result set."""
        mock_db_manager.execute_query.return_value = []

        results = search_engine.search_by_code('NONEXISTENT')

        assert results == []
        assert isinstance(results, list)

    def test_search_by_code_exact_match(self, search_engine, mock_db_manager):
        """Test exact match when full rate code is provided."""
        mock_db_manager.execute_query.return_value = [
            ('ГЭСНп81-01-001-01', 'Устройство перегородок', 'Перегородки', 100, 'м2', 13832.0)
        ]

        results = search_engine.search_by_code('ГЭСНп81-01-001-01')

        assert len(results) == 1
        assert results[0]['rate_code'] == 'ГЭСНп81-01-001-01'

    def test_search_by_code_rank_is_zero(self, search_engine, mock_db_manager):
        """Test that rank is set to 0 for code-based searches."""
        mock_db_manager.execute_query.return_value = [
            ('ГЭСНп81-01-001-01', 'Устройство перегородок', 'Перегородки', 100, 'м2', 13832.0)
        ]

        results = search_engine.search_by_code('ГЭСНп81-01')

        assert results[0]['rank'] == 0

    def test_search_by_code_multiple_matches(self, search_engine, mock_db_manager):
        """Test prefix search that returns multiple matches."""
        mock_db_manager.execute_query.return_value = [
            ('ГЭСНп81-01-001-01', 'Устройство перегородок', 'Перегородки', 100, 'м2', 13832.0),
            ('ГЭСНп81-01-002-01', 'Установка дверей', 'Двери', 10, 'шт', 5000.0),
            ('ГЭСНп81-01-003-01', 'Облицовка стен', 'Облицовка', 100, 'м2', 8500.0)
        ]

        results = search_engine.search_by_code('ГЭСНп81-01')

        assert len(results) == 3
        assert all(r['rate_code'].startswith('ГЭСНп81-01') for r in results)

    def test_search_by_code_calculates_cost_per_unit(self, search_engine, mock_db_manager):
        """Test that cost_per_unit is calculated correctly in code search."""
        mock_db_manager.execute_query.return_value = [
            ('RATE-001', 'Бетон монолитный', 'Бетон', 100, 'м3', 15000.0),
            ('RATE-002', 'Бетон тяжелый', 'Бетон Т', 50, 'м3', 10000.0)
        ]

        results = search_engine.search_by_code('RATE')

        assert results[0]['cost_per_unit'] == 150.0  # 15000 / 100
        assert results[1]['cost_per_unit'] == 200.0  # 10000 / 50

    def test_search_by_code_handles_database_error(self, search_engine, mock_db_manager):
        """Test that search_by_code handles database errors properly."""
        mock_db_manager.execute_query.side_effect = sqlite3.Error("Database error")

        with pytest.raises(sqlite3.Error, match="Database error"):
            search_engine.search_by_code('ГЭСНп81-01')

    def test_search_by_code_strips_whitespace(self, search_engine, mock_db_manager):
        """Test that search_by_code strips leading/trailing whitespace."""
        mock_db_manager.execute_query.return_value = [
            ('RATE-001', 'Test Rate', 'Test', 100, 'м3', 15000.0)
        ]

        results = search_engine.search_by_code('  RATE-001  ')

        # Verify whitespace was stripped
        call_args = mock_db_manager.execute_query.call_args
        params = call_args[0][1]
        assert params[0] == 'RATE-001%'
