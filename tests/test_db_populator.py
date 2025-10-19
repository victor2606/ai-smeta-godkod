"""
Unit Tests for DatabasePopulator Class

Comprehensive test suite covering:
- Rate population with batch processing and validation
- Resource population with foreign key validation
- Database clearing and truncation
- Error handling for duplicates and missing references
- Schema mapping and data transformation
- Progress tracking and statistics
- Edge cases and boundary conditions
"""

import pytest
import pandas as pd
import numpy as np
import sqlite3
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, call

from src.database.db_manager import DatabaseManager
from src.etl.db_populator import (
    DatabasePopulator,
    DatabasePopulatorError,
    DuplicateRateCodeError,
    MissingRateCodeError,
    ValidationError
)


# ============================================================================
# Pytest Fixtures
# ============================================================================

@pytest.fixture
def temp_database():
    """
    Fixture providing temporary SQLite database with schema initialized.
    Creates a fresh database for each test.
    """
    # Create temporary database file
    temp_fd, temp_path = tempfile.mkstemp(suffix='.db')
    os.close(temp_fd)

    # Initialize database with schema
    db = DatabaseManager(temp_path)
    db.connect()
    db.initialize_schema()
    db.disconnect()

    yield temp_path

    # Cleanup - remove database and WAL files
    try:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        # Clean up WAL files
        for suffix in ['-wal', '-shm']:
            wal_file = temp_path + suffix
            if os.path.exists(wal_file):
                os.unlink(wal_file)
    except OSError:
        pass


@pytest.fixture
def db_manager(temp_database):
    """
    Fixture providing DatabaseManager instance with active connection.
    """
    db = DatabaseManager(temp_database)
    db.connect()
    yield db
    db.disconnect()


@pytest.fixture
def populator(db_manager):
    """
    Fixture providing DatabasePopulator instance.
    """
    return DatabasePopulator(db_manager, batch_size=100)


@pytest.fixture
def sample_rates_df():
    """
    Fixture providing sample rates DataFrame matching DataAggregator output.
    """
    return pd.DataFrame({
        'rate_code': ['R001', 'R002', 'R003'],
        'rate_full_name': [
            'Устройство перегородок из гипсокартона',
            'Монтаж металлических конструкций',
            'Укладка бетонной смеси'
        ],
        'rate_short_name': ['Перегородки ГКЛ', 'Монтаж металл.', 'Бетон'],
        'unit_number': [100.0, 1.0, 10.0],
        'unit': ['м2', 'т', 'м3'],
        'rate_cost': [15000.50, 25000.00, 8500.75],
        'materials_cost': [10000.00, 20000.00, 7000.00],
        'resources_cost': [5000.50, 5000.00, 1500.75],
        'section_name': ['Отделочные работы', 'Монтажные работы', 'Бетонные работы'],
        'composition': [
            json.dumps([{'text': 'Установка каркаса', 'resource_code': 'C001'}], ensure_ascii=False),
            json.dumps([{'text': 'Сварка'}], ensure_ascii=False),
            None
        ],
        'search_text': [
            'R001 Устройство перегородок Перегородки ГКЛ',
            'R002 Монтаж металлических конструкций',
            'R003 Укладка бетонной смеси'
        ]
    })


@pytest.fixture
def sample_resources_df():
    """
    Fixture providing sample resources DataFrame matching DataAggregator output.
    """
    return pd.DataFrame({
        'rate_code': ['R001', 'R001', 'R002', 'R002', 'R003'],
        'resource_code': ['M001', 'M002', 'M003', 'L001', 'M004'],
        'row_type': ['Ресурс', 'Ресурс', 'Ресурс', 'Ресурс', 'Ресурс'],
        'resource_name': [
            'Гипсокартон ГКЛ',
            'Профиль металлический',
            'Металлопрокат',
            'Сварщик 4 разряда',
            'Бетон М300'
        ],
        'resource_quantity': [105.0, 50.0, 1.05, 8.0, 10.5],
        'unit': ['м2', 'м', 'т', 'чел-ч', 'м3'],
        'resource_cost': [150.50, 200.00, 24000.00, 500.00, 4500.00],
        'specifications': [None, None, 'ГОСТ 123', None, 'ГОСТ 456']
    })


@pytest.fixture
def large_rates_df():
    """
    Fixture providing large DataFrame to test batch processing.
    """
    num_records = 2500
    return pd.DataFrame({
        'rate_code': [f'R{i:06d}' for i in range(num_records)],
        'rate_full_name': [f'Rate {i}' for i in range(num_records)],
        'rate_short_name': [f'R{i}' for i in range(num_records)],
        'unit_number': [100.0] * num_records,
        'unit': ['м2'] * num_records,
        'rate_cost': [1000.0 + i for i in range(num_records)],
        'materials_cost': [500.0] * num_records,
        'resources_cost': [500.0] * num_records,
        'section_name': ['Section 1'] * num_records,
        'composition': [None] * num_records,
        'search_text': [f'Search text {i}' for i in range(num_records)]
    })


# ============================================================================
# Initialization Tests
# ============================================================================

class TestDatabasePopulatorInitialization:
    """Tests for DatabasePopulator initialization."""

    def test_init_success(self, db_manager):
        """Test successful initialization with valid DatabaseManager."""
        populator = DatabasePopulator(db_manager, batch_size=500)

        assert populator.db_manager == db_manager
        assert populator.batch_size == 500
        assert isinstance(populator._statistics, dict)

    def test_init_custom_batch_size(self, db_manager):
        """Test initialization with custom batch size."""
        populator = DatabasePopulator(db_manager, batch_size=2000)
        assert populator.batch_size == 2000

    def test_init_default_batch_size(self, db_manager):
        """Test initialization with default batch size."""
        populator = DatabasePopulator(db_manager)
        assert populator.batch_size == DatabasePopulator.DEFAULT_BATCH_SIZE

    def test_init_no_connection_raises_error(self):
        """Test initialization fails when DatabaseManager not connected."""
        db_manager = Mock()
        db_manager.connection = None

        with pytest.raises(ValueError, match="must have active connection"):
            DatabasePopulator(db_manager)

    def test_init_invalid_batch_size_raises_error(self, db_manager):
        """Test initialization fails with invalid batch size."""
        with pytest.raises(ValueError, match="batch_size must be positive"):
            DatabasePopulator(db_manager, batch_size=0)

        with pytest.raises(ValueError, match="batch_size must be positive"):
            DatabasePopulator(db_manager, batch_size=-100)


# ============================================================================
# Rates Population Tests
# ============================================================================

class TestPopulateRates:
    """Tests for populate_rates() method."""

    def test_populate_rates_success(self, populator, sample_rates_df):
        """Test successful rates population."""
        inserted = populator.populate_rates(sample_rates_df)

        assert inserted == len(sample_rates_df)
        assert populator._statistics['rates_inserted'] == len(sample_rates_df)

        # Verify data in database
        results = populator.db_manager.execute_query(
            "SELECT rate_code, rate_full_name FROM rates ORDER BY rate_code"
        )
        assert len(results) == 3
        assert results[0][0] == 'R001'
        assert results[0][1] == 'Устройство перегородок из гипсокартона'

    def test_populate_rates_schema_mapping(self, populator, sample_rates_df):
        """Test correct schema mapping from DataFrame to database."""
        populator.populate_rates(sample_rates_df)

        # Verify unit_number -> unit_quantity mapping
        result = populator.db_manager.execute_query(
            "SELECT unit_quantity, unit_type, category FROM rates WHERE rate_code = ?",
            ('R001',)
        )
        assert result[0][0] == 100.0  # unit_quantity
        assert result[0][1] == 'м2'   # unit_type
        assert result[0][2] == 'Отделочные работы'  # category

    def test_populate_rates_with_composition(self, populator, sample_rates_df):
        """Test rates population with JSON composition data."""
        populator.populate_rates(sample_rates_df)

        result = populator.db_manager.execute_query(
            "SELECT composition FROM rates WHERE rate_code = ?",
            ('R001',)
        )

        composition = result[0][0]
        assert composition is not None

        # Verify JSON is valid
        parsed = json.loads(composition)
        assert isinstance(parsed, list)
        assert parsed[0]['text'] == 'Установка каркаса'

    def test_populate_rates_fts_trigger(self, populator, sample_rates_df):
        """Test FTS index auto-populated via trigger."""
        populator.populate_rates(sample_rates_df)

        # Query FTS index
        fts_results = populator.db_manager.execute_query(
            "SELECT COUNT(*) FROM rates_fts"
        )
        assert fts_results[0][0] == len(sample_rates_df)

        # Test FTS search works
        search_results = populator.db_manager.execute_query(
            """
            SELECT r.rate_code FROM rates r
            JOIN rates_fts fts ON r.rowid = fts.rowid
            WHERE rates_fts MATCH ?
            """,
            ('гипсокартон',)
        )
        assert len(search_results) > 0
        assert search_results[0][0] == 'R001'

    def test_populate_rates_batch_processing(self, populator, large_rates_df):
        """Test batch processing with large dataset."""
        # Use smaller batch size to force multiple batches
        populator.batch_size = 1000

        inserted = populator.populate_rates(large_rates_df)

        assert inserted == len(large_rates_df)

        # Verify all records inserted
        result = populator.db_manager.execute_query("SELECT COUNT(*) FROM rates")
        assert result[0][0] == len(large_rates_df)

    def test_populate_rates_nan_to_null(self, populator):
        """Test NaN values converted to NULL in database."""
        df = pd.DataFrame({
            'rate_code': ['R001'],
            'rate_full_name': ['Test Rate'],
            'rate_short_name': [np.nan],  # NaN should become NULL
            'unit_number': [100.0],
            'unit': ['м2'],
            'rate_cost': [np.nan],  # NaN should become 0.0 (default)
            'materials_cost': [0.0],
            'resources_cost': [0.0],
            'section_name': [None],  # None should stay NULL
            'composition': [np.nan],
            'search_text': ['Test']
        })

        populator.populate_rates(df)

        result = populator.db_manager.execute_query(
            "SELECT rate_short_name, total_cost, category FROM rates WHERE rate_code = ?",
            ('R001',)
        )

        assert result[0][0] is None  # rate_short_name NULL
        assert result[0][1] == 0.0   # total_cost defaulted to 0.0
        assert result[0][2] is None  # category NULL

    def test_populate_rates_empty_df_raises_error(self, populator):
        """Test error raised for empty DataFrame."""
        empty_df = pd.DataFrame()

        with pytest.raises(ValueError, match="cannot be None or empty"):
            populator.populate_rates(empty_df)

    def test_populate_rates_missing_columns_raises_error(self, populator):
        """Test error raised when required columns missing."""
        df = pd.DataFrame({
            'rate_code': ['R001'],
            # Missing rate_full_name and unit
        })

        with pytest.raises(ValueError, match="Missing required columns"):
            populator.populate_rates(df)

    def test_populate_rates_duplicate_code_raises_error(self, populator, sample_rates_df):
        """Test error raised for duplicate rate_codes."""
        # Insert first batch
        populator.populate_rates(sample_rates_df)

        # Try to insert again (duplicates)
        with pytest.raises(DuplicateRateCodeError, match="Duplicate rate_code"):
            populator.populate_rates(sample_rates_df)

    def test_populate_rates_duplicate_in_input_raises_error(self, populator):
        """Test error raised when input DataFrame has duplicate rate_codes."""
        df = pd.DataFrame({
            'rate_code': ['R001', 'R001'],  # Duplicate
            'rate_full_name': ['Rate 1', 'Rate 1 Duplicate'],
            'rate_short_name': ['R1', 'R1'],
            'unit_number': [100.0, 100.0],
            'unit': ['м2', 'м2'],
            'rate_cost': [1000.0, 1000.0],
            'materials_cost': [500.0, 500.0],
            'resources_cost': [500.0, 500.0],
            'section_name': ['Section 1', 'Section 1'],
            'composition': [None, None],
            'search_text': ['Search 1', 'Search 2']
        })

        with pytest.raises(DuplicateRateCodeError, match="duplicate rate_codes"):
            populator.populate_rates(df)

    def test_populate_rates_validation_failure(self, populator, sample_rates_df):
        """Test validation error when count mismatch occurs."""
        # Mock execute_query to return wrong count
        with patch.object(populator.db_manager, 'execute_query') as mock_query:
            # First call for validation returns wrong count
            mock_query.return_value = [(999,)]

            with pytest.raises(ValidationError, match="Post-load validation failed"):
                populator.populate_rates(sample_rates_df)

    def test_populate_rates_statistics(self, populator, sample_rates_df):
        """Test statistics updated after population."""
        populator.populate_rates(sample_rates_df)

        stats = populator.get_statistics()

        assert stats['rates_inserted'] == len(sample_rates_df)
        assert 'rates_insert_time' in stats
        assert stats['rates_insert_time'] > 0
        assert stats['current_rates_count'] == len(sample_rates_df)


# ============================================================================
# Resources Population Tests
# ============================================================================

class TestPopulateResources:
    """Tests for populate_resources() method."""

    def test_populate_resources_success(self, populator, sample_rates_df, sample_resources_df):
        """Test successful resources population."""
        # First populate rates (parent table)
        populator.populate_rates(sample_rates_df)

        # Then populate resources
        inserted = populator.populate_resources(sample_resources_df)

        assert inserted == len(sample_resources_df)
        assert populator._statistics['resources_inserted'] == len(sample_resources_df)

        # Verify data in database
        results = populator.db_manager.execute_query(
            "SELECT rate_code, resource_code, resource_name FROM resources ORDER BY resource_id"
        )
        assert len(results) == 5
        assert results[0][1] == 'M001'
        assert results[0][2] == 'Гипсокартон ГКЛ'

    def test_populate_resources_schema_mapping(self, populator, sample_rates_df, sample_resources_df):
        """Test correct schema mapping from DataFrame to database."""
        populator.populate_rates(sample_rates_df)
        populator.populate_resources(sample_resources_df)

        # Verify row_type -> resource_type mapping
        result = populator.db_manager.execute_query(
            "SELECT resource_type, quantity, unit FROM resources WHERE resource_code = ?",
            ('M001',)
        )
        assert result[0][0] == 'Ресурс'
        assert result[0][1] == 105.0
        assert result[0][2] == 'м2'

    def test_populate_resources_cost_calculation(self, populator, sample_rates_df, sample_resources_df):
        """Test total_cost calculated from quantity * unit_cost."""
        populator.populate_rates(sample_rates_df)
        populator.populate_resources(sample_resources_df)

        result = populator.db_manager.execute_query(
            "SELECT quantity, unit_cost, total_cost FROM resources WHERE resource_code = ?",
            ('M001',)
        )

        quantity = result[0][0]
        unit_cost = result[0][1]
        total_cost = result[0][2]

        assert total_cost == quantity * unit_cost

    def test_populate_resources_foreign_key_validation(self, populator, sample_resources_df):
        """Test foreign key validation fails when rates not populated."""
        # Don't populate rates first

        with pytest.raises(MissingRateCodeError, match="non-existent rate_codes"):
            populator.populate_resources(sample_resources_df)

    def test_populate_resources_partial_fk_validation(self, populator, sample_rates_df, sample_resources_df):
        """Test validation catches missing rate_codes even with some valid ones."""
        # Only populate 2 out of 3 rates
        partial_rates = sample_rates_df[sample_rates_df['rate_code'].isin(['R001', 'R002'])].copy()
        populator.populate_rates(partial_rates)

        # Resources reference R003 which doesn't exist
        with pytest.raises(MissingRateCodeError, match="non-existent rate_codes"):
            populator.populate_resources(sample_resources_df)

    def test_populate_resources_empty_df(self, populator):
        """Test empty resources DataFrame handled gracefully."""
        empty_df = pd.DataFrame()

        inserted = populator.populate_resources(empty_df)
        assert inserted == 0

    def test_populate_resources_missing_columns_raises_error(self, populator, sample_rates_df):
        """Test error raised when required columns missing."""
        populator.populate_rates(sample_rates_df)

        df = pd.DataFrame({
            'rate_code': ['R001'],
            # Missing resource_code and resource_name
        })

        with pytest.raises(ValueError, match="Missing required columns"):
            populator.populate_resources(df)

    def test_populate_resources_autoincrement_id(self, populator, sample_rates_df, sample_resources_df):
        """Test resource_id auto-incremented by SQLite."""
        populator.populate_rates(sample_rates_df)
        populator.populate_resources(sample_resources_df)

        results = populator.db_manager.execute_query(
            "SELECT resource_id FROM resources ORDER BY resource_id"
        )

        # Verify IDs are sequential starting from 1
        assert results[0][0] == 1
        assert results[1][0] == 2
        assert results[4][0] == 5

    def test_populate_resources_with_specifications(self, populator, sample_rates_df, sample_resources_df):
        """Test resources with specifications field."""
        populator.populate_rates(sample_rates_df)
        populator.populate_resources(sample_resources_df)

        result = populator.db_manager.execute_query(
            "SELECT specifications FROM resources WHERE resource_code = ?",
            ('M003',)
        )

        assert result[0][0] == 'ГОСТ 123'


# ============================================================================
# Database Clearing Tests
# ============================================================================

class TestClearDatabase:
    """Tests for clear_database() method."""

    def test_clear_database_success(self, populator, sample_rates_df, sample_resources_df):
        """Test successful database truncation."""
        # Populate data
        populator.populate_rates(sample_rates_df)
        populator.populate_resources(sample_resources_df)

        # Verify data exists
        rates_count = populator.db_manager.execute_query("SELECT COUNT(*) FROM rates")[0][0]
        resources_count = populator.db_manager.execute_query("SELECT COUNT(*) FROM resources")[0][0]
        assert rates_count > 0
        assert resources_count > 0

        # Clear database
        populator.clear_database()

        # Verify all data deleted
        rates_count = populator.db_manager.execute_query("SELECT COUNT(*) FROM rates")[0][0]
        resources_count = populator.db_manager.execute_query("SELECT COUNT(*) FROM resources")[0][0]
        assert rates_count == 0
        assert resources_count == 0

    def test_clear_database_fts_cleared(self, populator, sample_rates_df):
        """Test FTS index cleared via CASCADE trigger."""
        populator.populate_rates(sample_rates_df)

        # Verify FTS populated
        fts_count = populator.db_manager.execute_query("SELECT COUNT(*) FROM rates_fts")[0][0]
        assert fts_count > 0

        # Clear database
        populator.clear_database()

        # Verify FTS cleared
        fts_count = populator.db_manager.execute_query("SELECT COUNT(*) FROM rates_fts")[0][0]
        assert fts_count == 0

    def test_clear_database_autoincrement_reset(self, populator, sample_rates_df, sample_resources_df):
        """Test AUTOINCREMENT sequence reset after clearing."""
        # Insert and clear
        populator.populate_rates(sample_rates_df)
        populator.populate_resources(sample_resources_df)
        populator.clear_database()

        # Insert again
        populator.populate_rates(sample_rates_df)
        populator.populate_resources(sample_resources_df)

        # Verify resource_id starts from 1 again
        result = populator.db_manager.execute_query(
            "SELECT MIN(resource_id) FROM resources"
        )
        assert result[0][0] == 1

    def test_clear_empty_database(self, populator):
        """Test clearing already empty database doesn't fail."""
        # Should not raise error
        populator.clear_database()

        # Verify still empty
        rates_count = populator.db_manager.execute_query("SELECT COUNT(*) FROM rates")[0][0]
        resources_count = populator.db_manager.execute_query("SELECT COUNT(*) FROM resources")[0][0]
        assert rates_count == 0
        assert resources_count == 0


# ============================================================================
# Statistics Tests
# ============================================================================

class TestGetStatistics:
    """Tests for get_statistics() method."""

    def test_get_statistics_empty(self, populator):
        """Test statistics for empty database."""
        stats = populator.get_statistics()

        assert stats['current_rates_count'] == 0
        assert stats['current_resources_count'] == 0
        assert stats['total_records'] == 0

    def test_get_statistics_after_population(self, populator, sample_rates_df, sample_resources_df):
        """Test statistics after populating data."""
        populator.populate_rates(sample_rates_df)
        populator.populate_resources(sample_resources_df)

        stats = populator.get_statistics()

        assert stats['rates_inserted'] == len(sample_rates_df)
        assert stats['resources_inserted'] == len(sample_resources_df)
        assert stats['current_rates_count'] == len(sample_rates_df)
        assert stats['current_resources_count'] == len(sample_resources_df)
        assert stats['total_records'] == len(sample_rates_df) + len(sample_resources_df)
        assert 'rates_insert_time' in stats
        assert 'resources_insert_time' in stats

    def test_get_statistics_fts_count(self, populator, sample_rates_df):
        """Test statistics includes FTS index count."""
        populator.populate_rates(sample_rates_df)

        stats = populator.get_statistics()

        assert 'fts_index_count' in stats
        assert stats['fts_index_count'] == len(sample_rates_df)


# ============================================================================
# Helper Methods Tests
# ============================================================================

class TestHelperMethods:
    """Tests for private helper methods."""

    def test_safe_value_none(self, populator):
        """Test _safe_value with None."""
        assert populator._safe_value(None) is None

    def test_safe_value_nan(self, populator):
        """Test _safe_value with NaN."""
        assert populator._safe_value(np.nan) is None

    def test_safe_value_string(self, populator):
        """Test _safe_value with string."""
        assert populator._safe_value('  test  ') == 'test'
        assert populator._safe_value('') is None
        assert populator._safe_value('   ') is None

    def test_safe_value_number(self, populator):
        """Test _safe_value with numbers."""
        assert populator._safe_value(123) == 123
        assert populator._safe_value(45.67) == 45.67

    def test_safe_numeric_valid(self, populator):
        """Test _safe_numeric with valid values."""
        assert populator._safe_numeric(123) == 123.0
        assert populator._safe_numeric('45.67') == 45.67
        assert populator._safe_numeric(0) == 0.0

    def test_safe_numeric_invalid(self, populator):
        """Test _safe_numeric with invalid values."""
        assert populator._safe_numeric(None) == 0.0
        assert populator._safe_numeric(np.nan) == 0.0
        assert populator._safe_numeric('invalid') == 0.0

    def test_safe_numeric_custom_default(self, populator):
        """Test _safe_numeric with custom default."""
        assert populator._safe_numeric(None, default=99.9) == 99.9
        assert populator._safe_numeric(np.nan, default=-1.0) == -1.0


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for complete ETL workflow."""

    def test_full_etl_workflow(self, populator, sample_rates_df, sample_resources_df):
        """Test complete ETL workflow: populate, query, clear."""
        # Populate rates
        rates_inserted = populator.populate_rates(sample_rates_df)
        assert rates_inserted == 3

        # Populate resources
        resources_inserted = populator.populate_resources(sample_resources_df)
        assert resources_inserted == 5

        # Query joined data
        results = populator.db_manager.execute_query(
            """
            SELECT r.rate_code, r.rate_full_name, res.resource_name
            FROM rates r
            JOIN resources res ON r.rate_code = res.rate_code
            WHERE r.rate_code = ?
            ORDER BY res.resource_id
            """,
            ('R001',)
        )

        assert len(results) == 2  # R001 has 2 resources
        assert results[0][2] == 'Гипсокартон ГКЛ'

        # Clear database
        populator.clear_database()

        # Verify empty
        rates_count = populator.db_manager.execute_query("SELECT COUNT(*) FROM rates")[0][0]
        assert rates_count == 0

    def test_multiple_populations(self, populator, sample_rates_df):
        """Test multiple sequential populations with clearing."""
        # First population
        populator.populate_rates(sample_rates_df)
        count1 = populator.db_manager.execute_query("SELECT COUNT(*) FROM rates")[0][0]
        assert count1 == 3

        # Clear and repopulate
        populator.clear_database()
        populator.populate_rates(sample_rates_df)
        count2 = populator.db_manager.execute_query("SELECT COUNT(*) FROM rates")[0][0]
        assert count2 == 3

    def test_fts_search_after_population(self, populator, sample_rates_df):
        """Test FTS search functionality after population."""
        populator.populate_rates(sample_rates_df)

        # Search for "гипсокартон"
        results = populator.db_manager.execute_query(
            """
            SELECT r.rate_code, r.rate_full_name
            FROM rates r
            JOIN rates_fts fts ON r.rowid = fts.rowid
            WHERE rates_fts MATCH ?
            """,
            ('гипсокартон',)
        )

        assert len(results) > 0
        assert 'гипсокартон' in results[0][1].lower()

    def test_cascade_delete_resources(self, populator, sample_rates_df, sample_resources_df):
        """Test CASCADE delete removes resources when rate deleted."""
        populator.populate_rates(sample_rates_df)
        populator.populate_resources(sample_resources_df)

        # Delete one rate
        populator.db_manager.execute_update("DELETE FROM rates WHERE rate_code = ?", ('R001',))

        # Verify associated resources deleted (CASCADE)
        results = populator.db_manager.execute_query(
            "SELECT COUNT(*) FROM resources WHERE rate_code = ?",
            ('R001',)
        )
        assert results[0][0] == 0


# ============================================================================
# Edge Cases and Error Handling Tests
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_very_long_strings(self, populator):
        """Test handling of very long text fields."""
        long_text = 'A' * 10000

        df = pd.DataFrame({
            'rate_code': ['R001'],
            'rate_full_name': [long_text],
            'rate_short_name': ['Short'],
            'unit_number': [100.0],
            'unit': ['м2'],
            'rate_cost': [1000.0],
            'materials_cost': [500.0],
            'resources_cost': [500.0],
            'section_name': ['Section'],
            'composition': [None],
            'search_text': [long_text]
        })

        inserted = populator.populate_rates(df)
        assert inserted == 1

        # Verify data retrieved correctly
        result = populator.db_manager.execute_query(
            "SELECT rate_full_name FROM rates WHERE rate_code = ?",
            ('R001',)
        )
        assert len(result[0][0]) == 10000

    def test_special_characters(self, populator):
        """Test handling of special characters in text fields."""
        special_text = "Test 'quotes\" and\nNewlines\tTabs & symbols <>!@#$%"

        df = pd.DataFrame({
            'rate_code': ['R001'],
            'rate_full_name': [special_text],
            'rate_short_name': ['Special'],
            'unit_number': [1.0],
            'unit': ['м2'],
            'rate_cost': [1000.0],
            'materials_cost': [0.0],
            'resources_cost': [0.0],
            'section_name': [special_text],
            'composition': [None],
            'search_text': [special_text]
        })

        inserted = populator.populate_rates(df)
        assert inserted == 1

    def test_unicode_cyrillic_characters(self, populator):
        """Test handling of Unicode Cyrillic text."""
        cyrillic_text = "Тестирование кириллицы: АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"

        df = pd.DataFrame({
            'rate_code': ['R001'],
            'rate_full_name': [cyrillic_text],
            'rate_short_name': ['Тест'],
            'unit_number': [100.0],
            'unit': ['м2'],
            'rate_cost': [1000.0],
            'materials_cost': [500.0],
            'resources_cost': [500.0],
            'section_name': ['Раздел'],
            'composition': [None],
            'search_text': [cyrillic_text]
        })

        inserted = populator.populate_rates(df)
        assert inserted == 1

        # Verify retrieval
        result = populator.db_manager.execute_query(
            "SELECT rate_full_name FROM rates WHERE rate_code = ?",
            ('R001',)
        )
        assert result[0][0] == cyrillic_text

    def test_extreme_numeric_values(self, populator):
        """Test handling of extreme numeric values."""
        df = pd.DataFrame({
            'rate_code': ['R001', 'R002'],
            'rate_full_name': ['Rate 1', 'Rate 2'],
            'rate_short_name': ['R1', 'R2'],
            'unit_number': [0.000001, 999999999.99],
            'unit': ['м2', 'т'],
            'rate_cost': [0.01, 99999999999.99],
            'materials_cost': [0.0, 50000000000.0],
            'resources_cost': [0.01, 49999999999.99],
            'section_name': ['S1', 'S2'],
            'composition': [None, None],
            'search_text': ['Search 1', 'Search 2']
        })

        inserted = populator.populate_rates(df)
        assert inserted == 2

    def test_zero_values(self, populator):
        """Test handling of zero values."""
        df = pd.DataFrame({
            'rate_code': ['R001'],
            'rate_full_name': ['Zero Cost Rate'],
            'rate_short_name': ['Zero'],
            'unit_number': [0.0],  # Edge case: zero quantity
            'unit': ['м2'],
            'rate_cost': [0.0],
            'materials_cost': [0.0],
            'resources_cost': [0.0],
            'section_name': ['Section'],
            'composition': [None],
            'search_text': ['Search']
        })

        # Should fail due to CHECK constraint (unit_quantity > 0)
        with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint"):
            populator.populate_rates(df)
