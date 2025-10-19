"""
Unit Tests for DataAggregator Class

Tests for construction rate data aggregation including:
- Rate aggregation with composition and unit parsing
- Resource aggregation and rate linkage
- Statistics generation
- Edge cases and validation
"""

import pytest
import pandas as pd
import numpy as np
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.etl.data_aggregator import DataAggregator


# ============================================================================
# Pytest Fixtures
# ============================================================================

@pytest.fixture
def sample_basic_dataframe():
    """
    Fixture providing basic DataFrame for rate aggregation tests.
    """
    return pd.DataFrame({
        'Расценка | Код': ['R001', 'R001', 'R002', 'R002'],
        'Расценка | Исходное наименование': [
            'Устройство перегородок из гипсокартона',
            'Устройство перегородок из гипсокартона',
            'Монтаж металлических конструкций',
            'Монтаж металлических конструкций'
        ],
        'Расценка | Краткое наименование': [
            'Перегородки ГКЛ',
            'Перегородки ГКЛ',
            'Монтаж металл.',
            'Монтаж металл.'
        ],
        'Расценка | Ед. изм.': ['100 м2', '100 м2', '1 т', '1 т'],
        'Раздел | Наименование': ['Отделочные работы', 'Отделочные работы', 'Монтажные работы', 'Монтажные работы'],
        'Тип строки': ['Расценка', 'Ресурс', 'Расценка', 'Ресурс'],
        'Ресурс | Код': [np.nan, 'M001', np.nan, 'M002'],
        'Ресурс | Исходное наименование': ['', 'Гипсокартон ГКЛ', '', 'Металлопрокат'],
        'Ресурс | Краткое наименование': ['', 'ГКЛ', '', 'Металл'],
        'Ресурс | Стоимость (руб.)': [0.0, 150.50, 0.0, 2500.00],
        'Ресурс | Количество': [0.0, 105.0, 0.0, 1.05],
        'Прайс | АбстРесурс | Сметная цена текущая_median': [100.0, 150.0, 200.0, 2400.0]
    })


@pytest.fixture
def sample_dataframe_with_composition():
    """
    Fixture providing DataFrame with composition rows ("Состав работ").
    """
    return pd.DataFrame({
        'Расценка | Код': ['R001', 'R001', 'R001', 'R001'],
        'Расценка | Исходное наименование': [
            'Устройство перегородок',
            'Устройство перегородок',
            'Устройство перегородок',
            'Устройство перегородок'
        ],
        'Расценка | Краткое наименование': ['Перегородки'] * 4,
        'Расценка | Ед. изм.': ['100 м2'] * 4,
        'Раздел | Наименование': ['Отделочные работы'] * 4,
        'Тип строки': ['Расценка', 'Состав работ', 'Состав работ', 'Ресурс'],
        'Ресурс | Код': [np.nan, 'C001', 'C002', 'M001'],
        'Ресурс | Исходное наименование': [
            '',
            'Установка каркаса',
            'Монтаж листов ГКЛ',
            'Гипсокартон'
        ],
        'Ресурс | Краткое наименование': ['', 'Каркас', 'Монтаж ГКЛ', 'ГКЛ'],
        'Ресурс | Стоимость (руб.)': [0.0, 0.0, 0.0, 150.50],
        'Ресурс | Количество': [0.0, 0.0, 0.0, 105.0],
        'Прайс | АбстРесурс | Сметная цена текущая_median': [100.0, 100.0, 100.0, 150.0]
    })


@pytest.fixture
def sample_dataframe_various_units():
    """
    Fixture providing DataFrame with various unit types.
    """
    return pd.DataFrame({
        'Расценка | Код': ['R001', 'R002', 'R003', 'R004', 'R005'],
        'Расценка | Исходное наименование': ['Работа 1', 'Работа 2', 'Работа 3', 'Работа 4', 'Работа 5'],
        'Расценка | Краткое наименование': ['Р1', 'Р2', 'Р3', 'Р4', 'Р5'],
        'Расценка | Ед. изм.': ['100 м2', '10 м3', '1 т', '1000 шт', '1 км'],
        'Раздел | Наименование': ['Раздел 1'] * 5,
        'Тип строки': ['Расценка'] * 5,
        'Ресурс | Код': [np.nan] * 5,
        'Ресурс | Исходное наименование': [''] * 5,
        'Ресурс | Краткое наименование': [''] * 5,
        'Ресурс | Стоимость (руб.)': [0.0] * 5,
        'Ресурс | Количество': [0.0] * 5,
        'Прайс | АбстРесурс | Сметная цена текущая_median': [100.0] * 5
    })


@pytest.fixture
def sample_dataframe_missing_composition():
    """
    Fixture providing DataFrame without composition rows.
    """
    return pd.DataFrame({
        'Расценка | Код': ['R001', 'R001'],
        'Расценка | Исходное наименование': ['Работа без состава'] * 2,
        'Расценка | Краткое наименование': ['Работа'] * 2,
        'Расценка | Ед. изм.': ['100 м2'] * 2,
        'Раздел | Наименование': ['Раздел 1'] * 2,
        'Тип строки': ['Расценка', 'Ресурс'],
        'Ресурс | Код': [np.nan, 'M001'],
        'Ресурс | Исходное наименование': ['', 'Материал 1'],
        'Ресурс | Краткое наименование': ['', 'Мат1'],
        'Ресурс | Стоимость (руб.)': [0.0, 100.0],
        'Ресурс | Количество': [0.0, 10.0],
        'Прайс | АбстРесурс | Сметная цена текущая_median': [100.0, 100.0]
    })


@pytest.fixture
def sample_dataframe_missing_units():
    """
    Fixture providing DataFrame with missing or invalid unit data.
    """
    return pd.DataFrame({
        'Расценка | Код': ['R001', 'R002', 'R003'],
        'Расценка | Исходное наименование': ['Работа 1', 'Работа 2', 'Работа 3'],
        'Расценка | Краткое наименование': ['Р1', 'Р2', 'Р3'],
        'Расценка | Ед. изм.': [np.nan, '', 'без числа м2'],
        'Раздел | Наименование': ['Раздел 1'] * 3,
        'Тип строки': ['Расценка'] * 3,
        'Ресурс | Код': [np.nan] * 3,
        'Ресурс | Исходное наименование': [''] * 3,
        'Ресурс | Краткое наименование': [''] * 3,
        'Ресурс | Стоимость (руб.)': [0.0] * 3,
        'Ресурс | Количество': [0.0] * 3,
        'Прайс | АбстРесурс | Сметная цена текущая_median': [100.0] * 3
    })


@pytest.fixture
def sample_dataframe_with_resources():
    """
    Fixture providing DataFrame with resource data for aggregation.
    """
    return pd.DataFrame({
        'Расценка | Код': ['R001', 'R001', 'R002', 'R002'],
        'Расценка | Исходное наименование': ['Работа 1'] * 2 + ['Работа 2'] * 2,
        'Расценка | Краткое наименование': ['Р1'] * 2 + ['Р2'] * 2,
        'Расценка | Ед. изм.': ['100 м2'] * 4,
        'Раздел | Наименование': ['Раздел 1'] * 4,
        'Тип строки': ['Расценка', 'Ресурс', 'Расценка', 'Ресурс'],
        'Ресурс | Код': [np.nan, 'M001', np.nan, 'M002'],
        'Ресурс | Исходное наименование': ['', 'Материал 1', '', 'Материал 2'],
        'Ресурс | Краткое наименование': ['', 'Мат1', '', 'Мат2'],
        'Ресурс | Стоимость (руб.)': [0.0, 150.50, 0.0, 200.75],
        'Ресурс | Количество': [0.0, 10.5, 0.0, 5.25],
        'Прайс | АбстРесурс | Сметная цена текущая_median': [100.0, 145.0, 200.0, 195.0]
    })


@pytest.fixture
def sample_dataframe_missing_required_columns():
    """
    Fixture providing DataFrame with missing required columns for validation.
    """
    return pd.DataFrame({
        'Расценка | Код': ['R001', 'R002'],
        'Расценка | Исходное наименование': ['Работа 1', 'Работа 2'],
        # Missing 'Расценка | Ед. изм.' and 'Тип строки'
    })


# ============================================================================
# Test: DataAggregator.__init__()
# ============================================================================

class TestDataAggregatorInit:
    """Test suite for DataAggregator initialization."""

    def test_init_with_dataframe(self, sample_basic_dataframe):
        """Test initialization with DataFrame."""
        aggregator = DataAggregator(sample_basic_dataframe)

        assert aggregator.df is not None
        pd.testing.assert_frame_equal(aggregator.df, sample_basic_dataframe)
        assert aggregator.rates_df is None
        assert aggregator.resources_df is None

    def test_init_sets_attributes_to_none(self, sample_basic_dataframe):
        """Test that rates_df and resources_df are initialized to None."""
        aggregator = DataAggregator(sample_basic_dataframe)

        assert aggregator.rates_df is None
        assert aggregator.resources_df is None


# ============================================================================
# Test: DataAggregator.aggregate_rates() - Basic
# ============================================================================

class TestDataAggregatorAggregateRatesBasic:
    """Test suite for aggregate_rates() basic functionality."""

    def test_aggregate_rates_basic(self, sample_basic_dataframe):
        """Test basic rate aggregation with sample data."""
        aggregator = DataAggregator(sample_basic_dataframe)
        rates_df = aggregator.aggregate_rates(sample_basic_dataframe)

        # Verify DataFrame structure
        assert isinstance(rates_df, pd.DataFrame)
        assert len(rates_df) == 2  # R001 and R002

        # Verify required columns exist
        required_cols = ['rate_code', 'rate_full_name', 'unit', 'search_text']
        for col in required_cols:
            assert col in rates_df.columns

        # Verify rate codes
        rate_codes = sorted(rates_df['rate_code'].tolist())
        assert rate_codes == ['R001', 'R002']

    def test_aggregate_rates_extracts_base_fields(self, sample_basic_dataframe):
        """Test that base fields are extracted correctly from first row."""
        aggregator = DataAggregator(sample_basic_dataframe)
        rates_df = aggregator.aggregate_rates(sample_basic_dataframe)

        # Check R001
        r001 = rates_df[rates_df['rate_code'] == 'R001'].iloc[0]
        assert r001['rate_full_name'] == 'Устройство перегородок из гипсокартона'
        assert r001['rate_short_name'] == 'Перегородки ГКЛ'
        assert r001['section_name'] == 'Отделочные работы'
        assert r001['unit_measure'] == '100 м2'

    def test_aggregate_rates_stores_in_attribute(self, sample_basic_dataframe):
        """Test that aggregated rates are stored in rates_df attribute."""
        aggregator = DataAggregator(sample_basic_dataframe)
        returned_df = aggregator.aggregate_rates(sample_basic_dataframe)

        assert aggregator.rates_df is not None
        pd.testing.assert_frame_equal(aggregator.rates_df, returned_df)

    def test_aggregate_rates_groups_by_rate_code(self, sample_basic_dataframe):
        """Test that rows are correctly grouped by rate code."""
        aggregator = DataAggregator(sample_basic_dataframe)
        rates_df = aggregator.aggregate_rates(sample_basic_dataframe)

        # Should have exactly 2 rates (R001 and R002)
        assert len(rates_df) == 2
        assert rates_df['rate_code'].nunique() == 2


# ============================================================================
# Test: DataAggregator.aggregate_rates() - With Composition
# ============================================================================

class TestDataAggregatorAggregateRatesComposition:
    """Test suite for aggregate_rates() with composition data."""

    def test_aggregate_rates_with_composition(self, sample_dataframe_with_composition):
        """Test aggregation includes 'Состав работ' rows in composition."""
        aggregator = DataAggregator(sample_dataframe_with_composition)
        rates_df = aggregator.aggregate_rates(sample_dataframe_with_composition)

        # Get the rate record
        rate = rates_df.iloc[0]

        # Verify composition exists
        assert rate['composition'] is not None
        assert pd.notna(rate['composition'])

        # Parse composition JSON
        composition = json.loads(rate['composition'])

        # Should have 2 composition items (C001 and C002)
        assert len(composition) == 2
        assert composition[0]['text'] == 'Установка каркаса'
        assert composition[0]['resource_code'] == 'C001'
        assert composition[1]['text'] == 'Монтаж листов ГКЛ'
        assert composition[1]['resource_code'] == 'C002'

    def test_aggregate_rates_composition_json_format(self, sample_dataframe_with_composition):
        """Test that composition is stored as valid JSON."""
        aggregator = DataAggregator(sample_dataframe_with_composition)
        rates_df = aggregator.aggregate_rates(sample_dataframe_with_composition)

        rate = rates_df.iloc[0]
        composition_json = rate['composition']

        # Should be valid JSON
        composition = json.loads(composition_json)
        assert isinstance(composition, list)
        assert all(isinstance(item, dict) for item in composition)

    def test_aggregate_rates_handles_missing_composition(self, sample_dataframe_missing_composition):
        """Test edge case: no composition rows."""
        aggregator = DataAggregator(sample_dataframe_missing_composition)
        rates_df = aggregator.aggregate_rates(sample_dataframe_missing_composition)

        rate = rates_df.iloc[0]

        # Composition should be None or empty
        assert rate['composition'] is None or rate['composition'] == 'null'


# ============================================================================
# Test: DataAggregator.aggregate_rates() - Unit Parsing
# ============================================================================

class TestDataAggregatorAggregateRatesUnitParsing:
    """Test suite for aggregate_rates() unit measure parsing."""

    def test_aggregate_rates_parses_units(self, sample_dataframe_various_units):
        """Test unit parsing (100 м2 -> 100.0, 'м2')."""
        aggregator = DataAggregator(sample_dataframe_various_units)
        rates_df = aggregator.aggregate_rates(sample_dataframe_various_units)

        # Check each unit type
        rates = {row['rate_code']: row for _, row in rates_df.iterrows()}

        # R001: 100 м2
        assert rates['R001']['unit_number'] == 100.0
        assert rates['R001']['unit'] == 'м2'

        # R002: 10 м3
        assert rates['R002']['unit_number'] == 10.0
        assert rates['R002']['unit'] == 'м3'

        # R003: 1 т
        assert rates['R003']['unit_number'] == 1.0
        assert rates['R003']['unit'] == 'т'

        # R004: 1000 шт
        assert rates['R004']['unit_number'] == 1000.0
        assert rates['R004']['unit'] == 'шт'

        # R005: 1 км
        assert rates['R005']['unit_number'] == 1.0
        assert rates['R005']['unit'] == 'км'

    def test_aggregate_rates_handles_missing_units(self, sample_dataframe_missing_units):
        """Test edge case: no unit data or invalid format."""
        aggregator = DataAggregator(sample_dataframe_missing_units)
        rates_df = aggregator.aggregate_rates(sample_dataframe_missing_units)

        rates = {row['rate_code']: row for _, row in rates_df.iterrows()}

        # R001: NaN unit measure
        assert pd.isna(rates['R001']['unit_number']) or rates['R001']['unit_number'] is None
        assert pd.isna(rates['R001']['unit']) or rates['R001']['unit'] is None

        # R002: Empty string
        assert pd.isna(rates['R002']['unit_number']) or rates['R002']['unit_number'] is None

    def test_aggregate_rates_unit_number_column_exists(self, sample_basic_dataframe):
        """Test that unit_number column is created."""
        aggregator = DataAggregator(sample_basic_dataframe)
        rates_df = aggregator.aggregate_rates(sample_basic_dataframe)

        assert 'unit_number' in rates_df.columns
        assert 'unit' in rates_df.columns


# ============================================================================
# Test: DataAggregator.aggregate_rates() - Search Text
# ============================================================================

class TestDataAggregatorAggregateRatesSearchText:
    """Test suite for aggregate_rates() search_text creation."""

    def test_aggregate_rates_creates_search_text(self, sample_basic_dataframe):
        """Test search_text concatenation."""
        aggregator = DataAggregator(sample_basic_dataframe)
        rates_df = aggregator.aggregate_rates(sample_basic_dataframe)

        # Check R001
        r001 = rates_df[rates_df['rate_code'] == 'R001'].iloc[0]
        search_text = r001['search_text']

        # Should contain rate_full_name
        assert 'Устройство перегородок из гипсокартона' in search_text
        # Should contain rate_short_name
        assert 'Перегородки ГКЛ' in search_text
        # Should contain section_name
        assert 'Отделочные работы' in search_text

    def test_aggregate_rates_search_text_includes_composition(self, sample_dataframe_with_composition):
        """Test that search_text includes composition text."""
        aggregator = DataAggregator(sample_dataframe_with_composition)
        rates_df = aggregator.aggregate_rates(sample_dataframe_with_composition)

        rate = rates_df.iloc[0]
        search_text = rate['search_text']

        # Should include composition text
        assert 'Установка каркаса' in search_text
        assert 'Монтаж листов ГКЛ' in search_text

    def test_aggregate_rates_search_text_not_empty(self, sample_basic_dataframe):
        """Test that search_text is not empty for valid rates."""
        aggregator = DataAggregator(sample_basic_dataframe)
        rates_df = aggregator.aggregate_rates(sample_basic_dataframe)

        # All rates should have non-empty search text
        assert all(rates_df['search_text'].str.len() > 0)


# ============================================================================
# Test: DataAggregator.aggregate_rates() - Validation
# ============================================================================

class TestDataAggregatorAggregateRatesValidation:
    """Test suite for aggregate_rates() validation."""

    def test_aggregate_rates_validates_required_fields(self, sample_basic_dataframe):
        """Test validation works for required fields."""
        aggregator = DataAggregator(sample_basic_dataframe)
        rates_df = aggregator.aggregate_rates(sample_basic_dataframe)

        # Check that all required fields exist
        for field in DataAggregator.REQUIRED_RATE_FIELDS:
            assert field in rates_df.columns
            # No empty values in required fields (for valid data)
            assert rates_df[field].notna().all()

    def test_aggregate_rates_missing_required_columns_raises_error(self, sample_dataframe_missing_required_columns):
        """Test that missing required columns raises ValueError."""
        aggregator = DataAggregator(sample_dataframe_missing_required_columns)

        with pytest.raises(ValueError) as exc_info:
            aggregator.aggregate_rates(sample_dataframe_missing_required_columns)

        assert "Missing required columns" in str(exc_info.value)

    def test_aggregate_rates_empty_result_raises_error(self):
        """Test that empty aggregation result raises ValueError."""
        # Create DataFrame with no valid rate codes
        df = pd.DataFrame({
            'Расценка | Код': [np.nan, np.nan],
            'Расценка | Исходное наименование': ['N1', 'N2'],
            'Расценка | Ед. изм.': ['м2', 'м2'],
            'Тип строки': ['Расценка', 'Расценка'],
        })

        aggregator = DataAggregator(df)

        with pytest.raises(ValueError) as exc_info:
            aggregator.aggregate_rates(df)

        assert "No rates were aggregated" in str(exc_info.value)


# ============================================================================
# Test: DataAggregator.aggregate_resources() - Basic
# ============================================================================

class TestDataAggregatorAggregateResourcesBasic:
    """Test suite for aggregate_resources() basic functionality."""

    def test_aggregate_resources_basic(self, sample_dataframe_with_resources):
        """Test basic resource aggregation extracts resources correctly."""
        aggregator = DataAggregator(sample_dataframe_with_resources)
        resources_df = aggregator.aggregate_resources(sample_dataframe_with_resources)

        # Verify DataFrame structure
        assert isinstance(resources_df, pd.DataFrame)
        assert len(resources_df) == 2  # M001 and M002

        # Verify required columns exist
        required_cols = ['rate_code', 'resource_code', 'resource_name']
        for col in required_cols:
            assert col in resources_df.columns

    def test_aggregate_resources_extracts_resource_fields(self, sample_dataframe_with_resources):
        """Test that resource fields are extracted correctly."""
        aggregator = DataAggregator(sample_dataframe_with_resources)
        resources_df = aggregator.aggregate_resources(sample_dataframe_with_resources)

        # Check M001
        m001 = resources_df[resources_df['resource_code'] == 'M001'].iloc[0]
        assert m001['resource_name'] == 'Материал 1'
        assert m001['resource_short_name'] == 'Мат1'
        assert m001['resource_cost'] == 150.50
        assert m001['resource_quantity'] == 10.5
        assert m001['row_type'] == 'Ресурс'

    def test_aggregate_resources_links_to_rates(self, sample_dataframe_with_resources):
        """Test that rate_code linkage works correctly."""
        aggregator = DataAggregator(sample_dataframe_with_resources)
        resources_df = aggregator.aggregate_resources(sample_dataframe_with_resources)

        # Check linkage
        m001 = resources_df[resources_df['resource_code'] == 'M001'].iloc[0]
        m002 = resources_df[resources_df['resource_code'] == 'M002'].iloc[0]

        assert m001['rate_code'] == 'R001'
        assert m002['rate_code'] == 'R002'

    def test_aggregate_resources_stores_in_attribute(self, sample_dataframe_with_resources):
        """Test that aggregated resources are stored in resources_df attribute."""
        aggregator = DataAggregator(sample_dataframe_with_resources)
        returned_df = aggregator.aggregate_resources(sample_dataframe_with_resources)

        assert aggregator.resources_df is not None
        pd.testing.assert_frame_equal(aggregator.resources_df, returned_df)

    def test_aggregate_resources_filters_non_resource_rows(self, sample_dataframe_with_resources):
        """Test that only rows with resource codes are included."""
        aggregator = DataAggregator(sample_dataframe_with_resources)
        resources_df = aggregator.aggregate_resources(sample_dataframe_with_resources)

        # Should have exactly 2 resources (M001 and M002)
        # Rate rows (with NaN resource codes) should be excluded
        assert len(resources_df) == 2
        assert all(resources_df['resource_code'].notna())


# ============================================================================
# Test: DataAggregator.aggregate_resources() - Edge Cases
# ============================================================================

class TestDataAggregatorAggregateResourcesEdgeCases:
    """Test suite for aggregate_resources() edge cases."""

    def test_aggregate_resources_no_resources_returns_empty(self):
        """Test that DataFrame with no resources returns empty DataFrame."""
        df = pd.DataFrame({
            'Расценка | Код': ['R001', 'R002'],
            'Расценка | Исходное наименование': ['Работа 1', 'Работа 2'],
            'Расценка | Ед. изм.': ['м2', 'м2'],
            'Тип строки': ['Расценка', 'Расценка'],
            'Ресурс | Код': [np.nan, np.nan],  # No resources
        })

        aggregator = DataAggregator(df)
        resources_df = aggregator.aggregate_resources(df)

        assert isinstance(resources_df, pd.DataFrame)
        assert len(resources_df) == 0

    def test_aggregate_resources_missing_required_columns_raises_error(self):
        """Test that missing required columns raises ValueError."""
        df = pd.DataFrame({
            'Расценка | Код': ['R001', 'R002'],
            # Missing 'Ресурс | Код'
        })

        aggregator = DataAggregator(df)

        with pytest.raises(ValueError) as exc_info:
            aggregator.aggregate_resources(df)

        assert "Missing required columns" in str(exc_info.value)

    def test_aggregate_resources_handles_missing_optional_fields(self):
        """Test that missing optional numeric fields are handled gracefully."""
        df = pd.DataFrame({
            'Расценка | Код': ['R001', 'R002'],
            'Ресурс | Код': ['M001', 'M002'],
            'Ресурс | Исходное наименование': ['Материал 1', 'Материал 2'],
            'Ресурс | Краткое наименование': ['Мат1', 'Мат2'],
            'Тип строки': ['Ресурс', 'Ресурс'],
            # Missing cost and quantity fields
        })

        aggregator = DataAggregator(df)
        resources_df = aggregator.aggregate_resources(df)

        # Should still create resources, just without optional fields
        assert len(resources_df) == 2


# ============================================================================
# Test: DataAggregator.get_statistics()
# ============================================================================

class TestDataAggregatorGetStatistics:
    """Test suite for get_statistics() method."""

    def test_get_statistics_returns_dict(self, sample_basic_dataframe):
        """Test that get_statistics() returns correct counts."""
        aggregator = DataAggregator(sample_basic_dataframe)
        aggregator.aggregate_rates(sample_basic_dataframe)
        aggregator.aggregate_resources(sample_basic_dataframe)

        stats = aggregator.get_statistics()

        assert isinstance(stats, dict)
        assert 'rates' in stats
        assert 'resources' in stats

    def test_get_statistics_rates_section(self, sample_dataframe_with_composition):
        """Test rates statistics section."""
        aggregator = DataAggregator(sample_dataframe_with_composition)
        aggregator.aggregate_rates(sample_dataframe_with_composition)

        stats = aggregator.get_statistics()

        assert 'rates' in stats
        assert stats['rates']['total'] == 1
        assert stats['rates']['with_composition'] == 1
        assert stats['rates']['with_unit_number'] == 1
        assert stats['rates']['unique_sections'] >= 0

    def test_get_statistics_resources_section(self, sample_dataframe_with_resources):
        """Test resources statistics section."""
        aggregator = DataAggregator(sample_dataframe_with_resources)
        aggregator.aggregate_resources(sample_dataframe_with_resources)

        stats = aggregator.get_statistics()

        assert 'resources' in stats
        assert stats['resources']['total'] == 2
        assert stats['resources']['unique_resources'] == 2
        assert stats['resources']['linked_rates'] == 2

    def test_get_statistics_before_aggregation(self, sample_basic_dataframe):
        """Test get_statistics() when no aggregation performed yet."""
        aggregator = DataAggregator(sample_basic_dataframe)

        stats = aggregator.get_statistics()

        # Should return empty dict or not crash
        assert isinstance(stats, dict)

    def test_get_statistics_with_only_rates(self, sample_basic_dataframe):
        """Test statistics with only rates aggregated."""
        aggregator = DataAggregator(sample_basic_dataframe)
        aggregator.aggregate_rates(sample_basic_dataframe)

        stats = aggregator.get_statistics()

        assert 'rates' in stats
        assert stats['rates']['total'] > 0

    def test_get_statistics_with_only_resources(self, sample_dataframe_with_resources):
        """Test statistics with only resources aggregated."""
        aggregator = DataAggregator(sample_dataframe_with_resources)
        aggregator.aggregate_resources(sample_dataframe_with_resources)

        stats = aggregator.get_statistics()

        assert 'resources' in stats
        assert stats['resources']['total'] > 0


# ============================================================================
# Test: DataAggregator Helper Methods
# ============================================================================

class TestDataAggregatorHelperMethods:
    """Test suite for DataAggregator helper methods."""

    def test_safe_str_handles_none(self):
        """Test _safe_str() handles None values."""
        result = DataAggregator._safe_str(None)
        assert result == ''

    def test_safe_str_handles_nan(self):
        """Test _safe_str() handles NaN values."""
        result = DataAggregator._safe_str(np.nan)
        assert result == ''

    def test_safe_str_converts_to_string(self):
        """Test _safe_str() converts values to string."""
        result = DataAggregator._safe_str('  test  ')
        assert result == 'test'

        result = DataAggregator._safe_str(123)
        assert result == '123'

    def test_parse_unit_measure_standard(self):
        """Test _parse_unit_measure() with standard format."""
        aggregator = DataAggregator(pd.DataFrame())

        number, unit = aggregator._parse_unit_measure('100 м2')
        assert number == 100.0
        assert unit == 'м2'

    def test_parse_unit_measure_different_units(self):
        """Test _parse_unit_measure() with different unit types."""
        aggregator = DataAggregator(pd.DataFrame())

        test_cases = [
            ('10 м3', 10.0, 'м3'),
            ('1 т', 1.0, 'т'),
            ('1000 шт', 1000.0, 'шт'),
            ('5.5 кг', 5.5, 'кг'),
        ]

        for input_str, expected_num, expected_unit in test_cases:
            number, unit = aggregator._parse_unit_measure(input_str)
            assert number == expected_num
            assert unit == expected_unit

    def test_parse_unit_measure_invalid_returns_none(self):
        """Test _parse_unit_measure() with invalid input."""
        aggregator = DataAggregator(pd.DataFrame())

        number, unit = aggregator._parse_unit_measure('invalid')
        assert unit == 'invalid'
        assert number is None

    def test_create_search_text_concatenates_fields(self):
        """Test _create_search_text() concatenates multiple fields."""
        aggregator = DataAggregator(pd.DataFrame())

        result = aggregator._create_search_text('Монтаж', 'конструкций', 'металлических')
        assert 'Монтаж' in result
        assert 'конструкций' in result
        assert 'металлических' in result

    def test_create_search_text_filters_empty(self):
        """Test _create_search_text() filters out empty and None values."""
        aggregator = DataAggregator(pd.DataFrame())

        result = aggregator._create_search_text('Valid', None, '', '  ', 'Text')
        assert 'Valid' in result
        assert 'Text' in result
        assert result == 'Valid Text'


# ============================================================================
# Test: DataAggregator Integration
# ============================================================================

class TestDataAggregatorIntegration:
    """Integration tests for complete workflows."""

    def test_complete_workflow_rates_and_resources(self, sample_dataframe_with_resources):
        """Test complete workflow: aggregate rates and resources."""
        aggregator = DataAggregator(sample_dataframe_with_resources)

        # Aggregate rates
        rates_df = aggregator.aggregate_rates(sample_dataframe_with_resources)
        assert len(rates_df) == 2

        # Aggregate resources
        resources_df = aggregator.aggregate_resources(sample_dataframe_with_resources)
        assert len(resources_df) == 2

        # Get statistics
        stats = aggregator.get_statistics()
        assert stats['rates']['total'] == 2
        assert stats['resources']['total'] == 2

    def test_workflow_with_composition(self, sample_dataframe_with_composition):
        """Test workflow with composition data."""
        aggregator = DataAggregator(sample_dataframe_with_composition)

        rates_df = aggregator.aggregate_rates(sample_dataframe_with_composition)

        # Verify composition was extracted
        rate = rates_df.iloc[0]
        composition = json.loads(rate['composition'])
        assert len(composition) == 2

        # Verify search text includes composition
        assert 'Установка каркаса' in rate['search_text']

    def test_workflow_preserves_data_integrity(self, sample_basic_dataframe):
        """Test that aggregation preserves data integrity."""
        aggregator = DataAggregator(sample_basic_dataframe)

        # Count unique rates in source
        source_rates = sample_basic_dataframe['Расценка | Код'].nunique()

        # Aggregate
        rates_df = aggregator.aggregate_rates(sample_basic_dataframe)

        # Should have same number of unique rates
        assert len(rates_df) == source_rates


# ============================================================================
# Test: DataAggregator Constants
# ============================================================================

class TestDataAggregatorConstants:
    """Test suite for DataAggregator class constants."""

    def test_composition_row_types_constant(self):
        """Test COMPOSITION_ROW_TYPES contains expected types."""
        assert 'Состав работ' in DataAggregator.COMPOSITION_ROW_TYPES

    def test_required_rate_fields_constant(self):
        """Test REQUIRED_RATE_FIELDS contains expected fields."""
        expected_fields = ['rate_code', 'rate_full_name', 'unit']

        for field in expected_fields:
            assert field in DataAggregator.REQUIRED_RATE_FIELDS


# ============================================================================
# Test: DataAggregator Error Handling
# ============================================================================

class TestDataAggregatorErrorHandling:
    """Test suite for error handling and logging."""

    def test_aggregate_rates_logs_progress(self, sample_basic_dataframe, caplog):
        """Test that aggregate_rates() logs progress messages."""
        import logging

        with caplog.at_level(logging.INFO):
            aggregator = DataAggregator(sample_basic_dataframe)
            aggregator.aggregate_rates(sample_basic_dataframe)

        assert any("Starting rate aggregation" in record.message for record in caplog.records)
        assert any("Successfully aggregated" in record.message for record in caplog.records)

    def test_aggregate_resources_logs_progress(self, sample_dataframe_with_resources, caplog):
        """Test that aggregate_resources() logs progress messages."""
        import logging

        with caplog.at_level(logging.INFO):
            aggregator = DataAggregator(sample_dataframe_with_resources)
            aggregator.aggregate_resources(sample_dataframe_with_resources)

        assert any("Starting resource aggregation" in record.message for record in caplog.records)
        assert any("Successfully aggregated" in record.message for record in caplog.records)

    def test_get_statistics_logs_info(self, sample_basic_dataframe, caplog):
        """Test that get_statistics() logs statistics."""
        import logging

        aggregator = DataAggregator(sample_basic_dataframe)
        aggregator.aggregate_rates(sample_basic_dataframe)

        with caplog.at_level(logging.INFO):
            aggregator.get_statistics()

        assert any("statistics" in record.message.lower() for record in caplog.records)
