"""
Unit Tests for ExcelLoader Class

Tests for Excel file loading, validation, and statistics generation including:
- File loading with valid and invalid paths
- DataFrame validation with required columns
- Critical column NaN validation
- Numeric column type conversion
- Statistics generation
- Real data file processing
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.etl.excel_loader import ExcelLoader


# ============================================================================
# Pytest Fixtures
# ============================================================================

@pytest.fixture
def sample_valid_dataframe():
    """
    Fixture providing a valid DataFrame matching ExcelLoader requirements.
    """
    return pd.DataFrame({
        'Расценка | Код': ['R001', 'R001', 'R002', 'R002', 'R003'],
        'Расценка | Исходное наименование': [
            'Устройство перегородок',
            'Устройство перегородок',
            'Монтаж конструкций',
            'Монтаж конструкций',
            'Укладка плитки'
        ],
        'Расценка | Ед. изм.': ['м2', 'м2', 'м2', 'м2', 'м2'],
        'Тип строки': ['Расценка', 'Ресурс', 'Расценка', 'Ресурс', 'Расценка'],
        'Ресурс | Код': ['', 'M001', '', 'M002', ''],
        'Ресурс | Стоимость (руб.)': [0.0, 150.50, 0.0, 200.75, 0.0],
        'Прайс | АбстРесурс | Сметная цена текущая_median': [100.0, 150.0, 200.0, 220.0, 300.0]
    })


@pytest.fixture
def sample_dataframe_with_nan_in_critical():
    """
    Fixture providing DataFrame with NaN values in critical columns.
    """
    return pd.DataFrame({
        'Расценка | Код': ['R001', None, 'R002'],
        'Расценка | Исходное наименование': ['Name1', 'Name2', 'Name3'],
        'Расценка | Ед. изм.': ['м2', 'м2', 'м2'],
        'Тип строки': ['Расценка', 'Ресурс', None],
        'Ресурс | Код': ['', 'M001', ''],
        'Ресурс | Стоимость (руб.)': [0.0, 150.50, 0.0],
        'Прайс | АбстРесурс | Сметная цена текущая_median': [100.0, 150.0, 200.0]
    })


@pytest.fixture
def sample_dataframe_missing_columns():
    """
    Fixture providing DataFrame with missing required columns.
    """
    return pd.DataFrame({
        'Расценка | Код': ['R001', 'R002'],
        'Расценка | Исходное наименование': ['Name1', 'Name2'],
        # Missing other required columns
    })


@pytest.fixture
def sample_dataframe_non_numeric_cost():
    """
    Fixture providing DataFrame with non-numeric cost column.
    """
    return pd.DataFrame({
        'Расценка | Код': ['R001', 'R002'],
        'Расценка | Исходное наименование': ['Name1', 'Name2'],
        'Расценка | Ед. изм.': ['м2', 'м2'],
        'Тип строки': ['Расценка', 'Ресурс'],
        'Ресурс | Код': ['', 'M001'],
        'Ресурс | Стоимость (руб.)': ['150.50', '200.75'],  # String values
        'Прайс | АбстРесурс | Сметная цена текущая_median': [100.0, 150.0]
    })


@pytest.fixture
def temp_excel_file(tmp_path, sample_valid_dataframe):
    """
    Fixture creating a temporary Excel file with valid data.
    """
    file_path = tmp_path / "test_data.xlsx"
    sample_valid_dataframe.to_excel(file_path, index=False, engine='openpyxl')
    return file_path


@pytest.fixture
def real_data_file_path():
    """
    Fixture providing path to real data file.
    """
    return Path("/Users/vic/git/n8npiplines-bim/data/raw/Сonstruction_Works_Rate_Schedule_Some_groups_17102025.xlsx")


# ============================================================================
# Test: ExcelLoader.__init__()
# ============================================================================

class TestExcelLoaderInit:
    """Test suite for ExcelLoader initialization."""

    def test_init_with_string_path(self):
        """Test initialization with string file path."""
        loader = ExcelLoader("/path/to/file.xlsx")
        assert loader.file_path == Path("/path/to/file.xlsx")
        assert loader.df is None

    def test_init_with_path_object(self):
        """Test initialization with Path object."""
        path = Path("/path/to/file.xlsx")
        loader = ExcelLoader(str(path))
        assert loader.file_path == path
        assert loader.df is None

    def test_init_sets_df_to_none(self):
        """Test that df attribute is initialized to None."""
        loader = ExcelLoader("test.xlsx")
        assert loader.df is None


# ============================================================================
# Test: ExcelLoader.load()
# ============================================================================

class TestExcelLoaderLoad:
    """Test suite for load() method."""

    def test_load_valid_file(self, temp_excel_file, sample_valid_dataframe):
        """Test successfully loading a valid Excel file."""
        loader = ExcelLoader(str(temp_excel_file))
        result_df = loader.load()

        assert isinstance(result_df, pd.DataFrame)
        assert loader.df is not None
        assert len(result_df) == len(sample_valid_dataframe)
        assert list(result_df.columns) == list(sample_valid_dataframe.columns)

    def test_load_file_not_found(self):
        """Test that FileNotFoundError is raised for missing file."""
        loader = ExcelLoader("/nonexistent/path/file.xlsx")

        with pytest.raises(FileNotFoundError) as exc_info:
            loader.load()

        assert "File not found" in str(exc_info.value)
        assert "/nonexistent/path/file.xlsx" in str(exc_info.value)

    def test_load_invalid_excel_file(self, tmp_path):
        """Test that ValueError is raised for invalid Excel file."""
        # Create a text file with .xlsx extension
        invalid_file = tmp_path / "invalid.xlsx"
        invalid_file.write_text("This is not an Excel file")

        loader = ExcelLoader(str(invalid_file))

        with pytest.raises(ValueError) as exc_info:
            loader.load()

        assert "Failed to load Excel" in str(exc_info.value)

    def test_load_returns_dataframe(self, temp_excel_file):
        """Test that load() returns a DataFrame."""
        loader = ExcelLoader(str(temp_excel_file))
        result = loader.load()

        assert isinstance(result, pd.DataFrame)

    def test_load_stores_dataframe_in_df_attribute(self, temp_excel_file):
        """Test that loaded data is stored in df attribute."""
        loader = ExcelLoader(str(temp_excel_file))
        returned_df = loader.load()

        assert loader.df is not None
        assert loader.df is returned_df
        pd.testing.assert_frame_equal(loader.df, returned_df)

    def test_load_with_tqdm_progress(self, temp_excel_file):
        """Test that load uses tqdm progress bar."""
        loader = ExcelLoader(str(temp_excel_file))

        with patch('src.etl.excel_loader.tqdm') as mock_tqdm:
            mock_pbar = MagicMock()
            mock_tqdm.return_value.__enter__.return_value = mock_pbar

            loader.load()

            # Verify tqdm was called
            mock_tqdm.assert_called_once()
            mock_pbar.update.assert_called_once_with(1)

    def test_load_logs_info_messages(self, temp_excel_file, caplog):
        """Test that load() logs informational messages."""
        import logging

        with caplog.at_level(logging.INFO):
            loader = ExcelLoader(str(temp_excel_file))
            loader.load()

        assert any("Loading Excel file" in record.message for record in caplog.records)
        assert any("Loaded" in record.message and "rows" in record.message for record in caplog.records)

    def test_load_correct_shape(self, temp_excel_file, sample_valid_dataframe):
        """Test that loaded DataFrame has correct shape."""
        loader = ExcelLoader(str(temp_excel_file))
        df = loader.load()

        assert df.shape == sample_valid_dataframe.shape
        assert len(df) == 5
        assert len(df.columns) == 7


# ============================================================================
# Test: ExcelLoader.validate()
# ============================================================================

class TestExcelLoaderValidate:
    """Test suite for validate() method."""

    def test_validate_before_load_raises_error(self):
        """Test that validate() raises ValueError when called before load()."""
        loader = ExcelLoader("test.xlsx")

        with pytest.raises(ValueError) as exc_info:
            loader.validate()

        assert "No data loaded" in str(exc_info.value)
        assert "Call load() first" in str(exc_info.value)

    def test_validate_with_all_required_columns(self, sample_valid_dataframe):
        """Test validation passes when all required columns are present."""
        loader = ExcelLoader("test.xlsx")
        loader.df = sample_valid_dataframe

        result = loader.validate()

        assert result is True

    def test_validate_missing_required_columns(self, sample_dataframe_missing_columns):
        """Test that ValueError is raised when required columns are missing."""
        loader = ExcelLoader("test.xlsx")
        loader.df = sample_dataframe_missing_columns

        with pytest.raises(ValueError) as exc_info:
            loader.validate()

        assert "Missing required columns" in str(exc_info.value)
        # Check that specific missing columns are mentioned
        error_msg = str(exc_info.value)
        assert "Расценка | Ед. изм." in error_msg or "Тип строки" in error_msg

    def test_validate_nan_in_critical_columns(self, sample_dataframe_with_nan_in_critical):
        """Test that ValueError is raised when critical columns have NaN values."""
        loader = ExcelLoader("test.xlsx")
        loader.df = sample_dataframe_with_nan_in_critical

        with pytest.raises(ValueError) as exc_info:
            loader.validate()

        error_msg = str(exc_info.value)
        assert "NaN values" in error_msg
        # Should mention the column with NaN
        assert "Расценка | Код" in error_msg or "Тип строки" in error_msg

    def test_validate_converts_numeric_columns(self, sample_dataframe_non_numeric_cost, caplog):
        """Test that non-numeric cost column is converted to numeric."""
        import logging

        loader = ExcelLoader("test.xlsx")
        loader.df = sample_dataframe_non_numeric_cost.copy()

        # Verify initial type is not numeric
        assert not pd.api.types.is_numeric_dtype(loader.df['Ресурс | Стоимость (руб.)'])

        with caplog.at_level(logging.WARNING):
            loader.validate()

        # Verify conversion happened
        assert pd.api.types.is_numeric_dtype(loader.df['Ресурс | Стоимость (руб.)'])

        # Verify warning was logged
        assert any("Converting" in record.message and "Ресурс | Стоимость (руб.)" in record.message
                   for record in caplog.records)

    def test_validate_numeric_conversion_with_errors_coerce(self):
        """Test that numeric conversion uses errors='coerce'."""
        df = pd.DataFrame({
            'Расценка | Код': ['R001', 'R002'],
            'Расценка | Исходное наименование': ['Name1', 'Name2'],
            'Расценка | Ед. изм.': ['м2', 'м2'],
            'Тип строки': ['Расценка', 'Ресурс'],
            'Ресурс | Код': ['', 'M001'],
            'Ресурс | Стоимость (руб.)': ['150.50', 'invalid'],  # One invalid value
            'Прайс | АбстРесурс | Сметная цена текущая_median': [100.0, 150.0]
        })

        loader = ExcelLoader("test.xlsx")
        loader.df = df
        loader.validate()

        # First value should be converted, second should be NaN
        assert loader.df['Ресурс | Стоимость (руб.)'].iloc[0] == 150.50
        assert pd.isna(loader.df['Ресурс | Стоимость (руб.)'].iloc[1])

    def test_validate_returns_true(self, sample_valid_dataframe):
        """Test that validate() returns True on success."""
        loader = ExcelLoader("test.xlsx")
        loader.df = sample_valid_dataframe

        result = loader.validate()

        assert result is True

    def test_validate_logs_success_message(self, sample_valid_dataframe, caplog):
        """Test that validate() logs success message."""
        import logging

        loader = ExcelLoader("test.xlsx")
        loader.df = sample_valid_dataframe

        with caplog.at_level(logging.INFO):
            loader.validate()

        assert any("Validation passed" in record.message for record in caplog.records)

    def test_validate_checks_all_critical_columns(self):
        """Test that validation checks all columns in CRITICAL_COLUMNS."""
        # Verify the critical columns constant
        assert 'Расценка | Код' in ExcelLoader.CRITICAL_COLUMNS
        assert 'Тип строки' in ExcelLoader.CRITICAL_COLUMNS

    def test_validate_with_empty_dataframe(self):
        """Test validation with empty DataFrame that has correct columns."""
        df = pd.DataFrame(columns=ExcelLoader.REQUIRED_COLUMNS)
        loader = ExcelLoader("test.xlsx")
        loader.df = df

        # Should pass validation as there are no NaN values in empty DataFrame
        result = loader.validate()
        assert result is True


# ============================================================================
# Test: ExcelLoader.get_statistics()
# ============================================================================

class TestExcelLoaderGetStatistics:
    """Test suite for get_statistics() method."""

    def test_get_statistics_before_load_raises_error(self):
        """Test that get_statistics() raises ValueError when called before load()."""
        loader = ExcelLoader("test.xlsx")

        with pytest.raises(ValueError) as exc_info:
            loader.get_statistics()

        assert "No data loaded" in str(exc_info.value)
        assert "Call load() first" in str(exc_info.value)

    def test_get_statistics_returns_dict(self, sample_valid_dataframe):
        """Test that get_statistics() returns a dictionary."""
        loader = ExcelLoader("test.xlsx")
        loader.df = sample_valid_dataframe

        stats = loader.get_statistics()

        assert isinstance(stats, dict)

    def test_get_statistics_contains_total_rows(self, sample_valid_dataframe):
        """Test that statistics contain correct total_rows count."""
        loader = ExcelLoader("test.xlsx")
        loader.df = sample_valid_dataframe

        stats = loader.get_statistics()

        assert 'total_rows' in stats
        assert stats['total_rows'] == len(sample_valid_dataframe)
        assert stats['total_rows'] == 5

    def test_get_statistics_contains_unique_rates(self, sample_valid_dataframe):
        """Test that statistics contain correct unique_rates count."""
        loader = ExcelLoader("test.xlsx")
        loader.df = sample_valid_dataframe

        stats = loader.get_statistics()

        assert 'unique_rates' in stats
        # Should have 3 unique rates: R001, R002, R003
        assert stats['unique_rates'] == 3

    def test_get_statistics_contains_row_types(self, sample_valid_dataframe):
        """Test that statistics contain row_types dictionary."""
        loader = ExcelLoader("test.xlsx")
        loader.df = sample_valid_dataframe

        stats = loader.get_statistics()

        assert 'row_types' in stats
        assert isinstance(stats['row_types'], dict)
        # Should have 3 'Расценка' and 2 'Ресурс' rows
        assert stats['row_types']['Расценка'] == 3
        assert stats['row_types']['Ресурс'] == 2

    def test_get_statistics_row_types_counts(self):
        """Test row_types counts with different distribution."""
        df = pd.DataFrame({
            'Расценка | Код': ['R001', 'R001', 'R001', 'R002'],
            'Расценка | Исходное наименование': ['N1', 'N1', 'N1', 'N2'],
            'Расценка | Ед. изм.': ['м2', 'м2', 'м2', 'м2'],
            'Тип строки': ['Расценка', 'Ресурс', 'Ресурс', 'Расценка'],
            'Ресурс | Код': ['', 'M001', 'M002', ''],
            'Ресурс | Стоимость (руб.)': [0.0, 100.0, 200.0, 0.0],
            'Прайс | АбстРесурс | Сметная цена текущая_median': [100.0, 100.0, 100.0, 200.0]
        })

        loader = ExcelLoader("test.xlsx")
        loader.df = df
        stats = loader.get_statistics()

        assert stats['row_types']['Расценка'] == 2
        assert stats['row_types']['Ресурс'] == 2

    def test_get_statistics_logs_info(self, sample_valid_dataframe, caplog):
        """Test that get_statistics() logs statistics."""
        import logging

        loader = ExcelLoader("test.xlsx")
        loader.df = sample_valid_dataframe

        with caplog.at_level(logging.INFO):
            stats = loader.get_statistics()

        assert any("Statistics" in record.message for record in caplog.records)

    def test_get_statistics_structure(self, sample_valid_dataframe):
        """Test complete structure of statistics dictionary."""
        loader = ExcelLoader("test.xlsx")
        loader.df = sample_valid_dataframe

        stats = loader.get_statistics()

        # Verify all expected keys are present
        assert set(stats.keys()) == {'total_rows', 'unique_rates', 'row_types'}

        # Verify types
        assert isinstance(stats['total_rows'], (int, np.integer))
        assert isinstance(stats['unique_rates'], (int, np.integer))
        assert isinstance(stats['row_types'], dict)


# ============================================================================
# Test: ExcelLoader with Real Data File
# ============================================================================

class TestExcelLoaderRealData:
    """Test suite using real data file."""

    def test_load_real_data_file(self, real_data_file_path):
        """Test loading the actual Excel file from data/raw/."""
        if not real_data_file_path.exists():
            pytest.skip(f"Real data file not found: {real_data_file_path}")

        loader = ExcelLoader(str(real_data_file_path))
        df = loader.load()

        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        assert len(df.columns) > 0

    def test_validate_real_data_file(self, real_data_file_path):
        """Test that real data file passes validation."""
        if not real_data_file_path.exists():
            pytest.skip(f"Real data file not found: {real_data_file_path}")

        loader = ExcelLoader(str(real_data_file_path))
        loader.load()

        # Should not raise exception
        result = loader.validate()
        assert result is True

    def test_real_data_has_required_columns(self, real_data_file_path):
        """Test that real data file has all required columns."""
        if not real_data_file_path.exists():
            pytest.skip(f"Real data file not found: {real_data_file_path}")

        loader = ExcelLoader(str(real_data_file_path))
        loader.load()

        for col in ExcelLoader.REQUIRED_COLUMNS:
            assert col in loader.df.columns, f"Missing required column: {col}"

    def test_get_statistics_real_data(self, real_data_file_path):
        """Test get_statistics() with real data and verify structure."""
        if not real_data_file_path.exists():
            pytest.skip(f"Real data file not found: {real_data_file_path}")

        loader = ExcelLoader(str(real_data_file_path))
        loader.load()
        loader.validate()

        stats = loader.get_statistics()

        # Verify structure
        assert 'total_rows' in stats
        assert 'unique_rates' in stats
        assert 'row_types' in stats

        # Verify reasonable values
        assert stats['total_rows'] > 0
        assert stats['unique_rates'] > 0
        assert stats['unique_rates'] <= stats['total_rows']
        assert isinstance(stats['row_types'], dict)
        assert len(stats['row_types']) > 0

    def test_real_data_statistics_values(self, real_data_file_path):
        """Test that statistics from real data have valid values."""
        if not real_data_file_path.exists():
            pytest.skip(f"Real data file not found: {real_data_file_path}")

        loader = ExcelLoader(str(real_data_file_path))
        loader.load()
        stats = loader.get_statistics()

        # total_rows should match DataFrame length
        assert stats['total_rows'] == len(loader.df)

        # unique_rates should match nunique()
        assert stats['unique_rates'] == loader.df['Расценка | Код'].nunique()

        # row_types total should equal total_rows
        assert sum(stats['row_types'].values()) == stats['total_rows']


# ============================================================================
# Test: ExcelLoader Constants
# ============================================================================

class TestExcelLoaderConstants:
    """Test suite for ExcelLoader class constants."""

    def test_required_columns_constant(self):
        """Test that REQUIRED_COLUMNS contains all expected columns."""
        expected_columns = [
            'Расценка | Код',
            'Расценка | Исходное наименование',
            'Расценка | Ед. изм.',
            'Тип строки',
            'Ресурс | Код',
            'Ресурс | Стоимость (руб.)',
            'Прайс | АбстРесурс | Сметная цена текущая_median'
        ]

        assert ExcelLoader.REQUIRED_COLUMNS == expected_columns

    def test_critical_columns_constant(self):
        """Test that CRITICAL_COLUMNS contains expected columns."""
        expected_critical = ['Расценка | Код', 'Тип строки']

        assert ExcelLoader.CRITICAL_COLUMNS == expected_critical

    def test_critical_columns_subset_of_required(self):
        """Test that all critical columns are in required columns."""
        for col in ExcelLoader.CRITICAL_COLUMNS:
            assert col in ExcelLoader.REQUIRED_COLUMNS


# ============================================================================
# Test: Edge Cases
# ============================================================================

class TestExcelLoaderEdgeCases:
    """Test suite for edge cases and boundary conditions."""

    def test_load_excel_with_multiple_sheets(self, tmp_path):
        """Test loading Excel file with multiple sheets (should load first sheet)."""
        file_path = tmp_path / "multi_sheet.xlsx"

        # Create Excel with multiple sheets
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            pd.DataFrame({'A': [1, 2]}).to_excel(writer, sheet_name='Sheet1', index=False)
            pd.DataFrame({'B': [3, 4]}).to_excel(writer, sheet_name='Sheet2', index=False)

        loader = ExcelLoader(str(file_path))
        df = loader.load()

        # Should load first sheet by default
        assert 'A' in df.columns

    def test_load_excel_with_empty_rows(self, tmp_path, sample_valid_dataframe):
        """Test handling Excel file with empty rows."""
        file_path = tmp_path / "with_empty.xlsx"

        # Add empty row
        df_with_empty = pd.concat([
            sample_valid_dataframe.iloc[:2],
            pd.DataFrame([{col: None for col in sample_valid_dataframe.columns}]),
            sample_valid_dataframe.iloc[2:]
        ], ignore_index=True)

        df_with_empty.to_excel(file_path, index=False, engine='openpyxl')

        loader = ExcelLoader(str(file_path))
        df = loader.load()

        assert len(df) == 6  # 5 original + 1 empty row

    def test_validate_with_all_nan_optional_column(self):
        """Test validation when non-critical column has all NaN values."""
        df = pd.DataFrame({
            'Расценка | Код': ['R001', 'R002'],
            'Расценка | Исходное наименование': ['Name1', 'Name2'],
            'Расценка | Ед. изм.': ['м2', 'м2'],
            'Тип строки': ['Расценка', 'Ресурс'],
            'Ресурс | Код': [np.nan, np.nan],  # All NaN in non-critical column
            'Ресурс | Стоимость (руб.)': [100.0, 200.0],
            'Прайс | АбстРесурс | Сметная цена текущая_median': [100.0, 150.0]
        })

        loader = ExcelLoader("test.xlsx")
        loader.df = df

        # Should not raise error for non-critical columns
        result = loader.validate()
        assert result is True

    def test_get_statistics_single_row(self):
        """Test get_statistics() with single row DataFrame."""
        df = pd.DataFrame({
            'Расценка | Код': ['R001'],
            'Расценка | Исходное наименование': ['Name1'],
            'Расценка | Ед. изм.': ['м2'],
            'Тип строки': ['Расценка'],
            'Ресурс | Код': [''],
            'Ресурс | Стоимость (руб.)': [100.0],
            'Прайс | АбстРесурс | Сметная цена текущая_median': [100.0]
        })

        loader = ExcelLoader("test.xlsx")
        loader.df = df
        stats = loader.get_statistics()

        assert stats['total_rows'] == 1
        assert stats['unique_rates'] == 1
        assert stats['row_types']['Расценка'] == 1

    def test_get_statistics_with_duplicate_rates(self):
        """Test unique_rates count with many duplicates."""
        df = pd.DataFrame({
            'Расценка | Код': ['R001'] * 10,  # Same rate 10 times
            'Расценка | Исходное наименование': ['Name1'] * 10,
            'Расценка | Ед. изм.': ['м2'] * 10,
            'Тип строки': ['Расценка'] * 10,
            'Ресурс | Код': [''] * 10,
            'Ресурс | Стоимость (руб.)': [100.0] * 10,
            'Прайс | АбстРесурс | Сметная цена текущая_median': [100.0] * 10
        })

        loader = ExcelLoader("test.xlsx")
        loader.df = df
        stats = loader.get_statistics()

        assert stats['total_rows'] == 10
        assert stats['unique_rates'] == 1  # Only 1 unique rate


# ============================================================================
# Test: Integration Tests
# ============================================================================

class TestExcelLoaderIntegration:
    """Integration tests for complete workflows."""

    def test_complete_workflow_valid_file(self, temp_excel_file):
        """Test complete workflow: load -> validate -> get_statistics."""
        loader = ExcelLoader(str(temp_excel_file))

        # Load
        df = loader.load()
        assert df is not None

        # Validate
        is_valid = loader.validate()
        assert is_valid is True

        # Get statistics
        stats = loader.get_statistics()
        assert stats['total_rows'] > 0
        assert stats['unique_rates'] > 0

    def test_workflow_fails_on_invalid_data(self, tmp_path):
        """Test that workflow properly fails with invalid data."""
        # Create file with missing columns
        file_path = tmp_path / "invalid.xlsx"
        pd.DataFrame({'A': [1, 2], 'B': [3, 4]}).to_excel(file_path, index=False)

        loader = ExcelLoader(str(file_path))
        loader.load()

        # Validation should fail
        with pytest.raises(ValueError, match="Missing required columns"):
            loader.validate()

    def test_cannot_validate_without_load(self):
        """Test that validate() cannot be called before load()."""
        loader = ExcelLoader("test.xlsx")

        with pytest.raises(ValueError, match="No data loaded"):
            loader.validate()

    def test_cannot_get_statistics_without_load(self):
        """Test that get_statistics() cannot be called before load()."""
        loader = ExcelLoader("test.xlsx")

        with pytest.raises(ValueError, match="No data loaded"):
            loader.get_statistics()

    def test_can_get_statistics_without_validate(self, temp_excel_file):
        """Test that get_statistics() can be called without validate()."""
        loader = ExcelLoader(str(temp_excel_file))
        loader.load()

        # Should work without calling validate()
        stats = loader.get_statistics()
        assert stats is not None


# ============================================================================
# Test: Error Messages
# ============================================================================

class TestExcelLoaderErrorMessages:
    """Test suite for error message clarity."""

    def test_file_not_found_error_message(self):
        """Test FileNotFoundError has clear message with path."""
        loader = ExcelLoader("/path/to/missing.xlsx")

        with pytest.raises(FileNotFoundError) as exc_info:
            loader.load()

        error_msg = str(exc_info.value)
        assert "File not found" in error_msg
        assert "/path/to/missing.xlsx" in error_msg

    def test_missing_columns_error_lists_columns(self):
        """Test that missing columns error lists the missing columns."""
        df = pd.DataFrame({'Column1': [1, 2]})
        loader = ExcelLoader("test.xlsx")
        loader.df = df

        with pytest.raises(ValueError) as exc_info:
            loader.validate()

        error_msg = str(exc_info.value)
        assert "Missing required columns" in error_msg
        # Should contain at least one missing column name
        assert any(col in error_msg for col in ExcelLoader.REQUIRED_COLUMNS)

    def test_nan_error_specifies_column_and_count(self):
        """Test that NaN error specifies which column and how many NaNs."""
        df = pd.DataFrame({
            'Расценка | Код': ['R001', None, None],
            'Расценка | Исходное наименование': ['N1', 'N2', 'N3'],
            'Расценка | Ед. изм.': ['м2', 'м2', 'м2'],
            'Тип строки': ['Расценка', 'Ресурс', 'Расценка'],
            'Ресурс | Код': ['', '', ''],
            'Ресурс | Стоимость (руб.)': [100.0, 100.0, 100.0],
            'Прайс | АбстРесурс | Сметная цена текущая_median': [100.0, 100.0, 100.0]
        })

        loader = ExcelLoader("test.xlsx")
        loader.df = df

        with pytest.raises(ValueError) as exc_info:
            loader.validate()

        error_msg = str(exc_info.value)
        assert "Расценка | Код" in error_msg
        assert "NaN values" in error_msg
        assert "2" in error_msg  # Number of NaN values

    def test_no_data_loaded_error_message(self):
        """Test clear error message when methods called before load()."""
        loader = ExcelLoader("test.xlsx")

        with pytest.raises(ValueError) as exc_info:
            loader.validate()

        error_msg = str(exc_info.value)
        assert "No data loaded" in error_msg
        assert "Call load() first" in error_msg
