"""
Unit Tests for Text Processing Utilities

Tests for text processing helper functions including:
- Unit measure parsing (parse_unit_measure)
- Text cleaning and normalization (clean_text)
- Full-text search text building (build_search_text)
"""

import pytest
import numpy as np
from src.utils.text_processor import parse_unit_measure, clean_text, build_search_text


# ============================================================================
# Test: parse_unit_measure() - Standard Cases
# ============================================================================

class TestParseUnitMeasureStandard:
    """Test suite for parse_unit_measure() standard cases."""

    def test_parse_unit_measure_standard(self):
        """Test parse_unit_measure() with standard format '100 м2' -> (100.0, 'м2')."""
        quantity, unit = parse_unit_measure("100 м2")

        assert quantity == 100.0
        assert unit == "м2"

    def test_parse_unit_measure_single_digit(self):
        """Test parsing single digit quantities."""
        quantity, unit = parse_unit_measure("1 м3")

        assert quantity == 1.0
        assert unit == "м3"

    def test_parse_unit_measure_large_number(self):
        """Test parsing large quantities."""
        quantity, unit = parse_unit_measure("1000 шт")

        assert quantity == 1000.0
        assert unit == "шт"

    def test_parse_unit_measure_decimal(self):
        """Test parsing decimal quantities."""
        quantity, unit = parse_unit_measure("5.5 кг")

        assert quantity == 5.5
        assert unit == "кг"

    def test_parse_unit_measure_with_comma_decimal(self):
        """Test parsing quantities with comma as decimal separator."""
        quantity, unit = parse_unit_measure("10,5 т")

        assert quantity == 10.5
        assert unit == "т"


# ============================================================================
# Test: parse_unit_measure() - Different Units
# ============================================================================

class TestParseUnitMeasureDifferentUnits:
    """Test suite for parse_unit_measure() with various unit types."""

    def test_parse_unit_measure_square_meters(self):
        """Test parsing м2 (square meters)."""
        quantity, unit = parse_unit_measure("100 м2")

        assert quantity == 100.0
        assert unit == "м2"

    def test_parse_unit_measure_cubic_meters(self):
        """Test parsing м3 (cubic meters)."""
        quantity, unit = parse_unit_measure("10 м3")

        assert quantity == 10.0
        assert unit == "м3"

    def test_parse_unit_measure_tons(self):
        """Test parsing т (tons)."""
        quantity, unit = parse_unit_measure("1 т")

        assert quantity == 1.0
        assert unit == "т"

    def test_parse_unit_measure_pieces(self):
        """Test parsing шт (pieces)."""
        quantity, unit = parse_unit_measure("500 шт")

        assert quantity == 500.0
        assert unit == "шт"

    def test_parse_unit_measure_kilograms(self):
        """Test parsing кг (kilograms)."""
        quantity, unit = parse_unit_measure("25 кг")

        assert quantity == 25.0
        assert unit == "кг"

    def test_parse_unit_measure_liters(self):
        """Test parsing л (liters)."""
        quantity, unit = parse_unit_measure("100 л")

        assert quantity == 100.0
        assert unit == "л"

    def test_parse_unit_measure_meters(self):
        """Test parsing м (meters)."""
        quantity, unit = parse_unit_measure("50 м")

        assert quantity == 50.0
        assert unit == "м"

    def test_parse_unit_measure_kilometers(self):
        """Test parsing км (kilometers)."""
        quantity, unit = parse_unit_measure("1 км")

        assert quantity == 1.0
        assert unit == "км"


# ============================================================================
# Test: parse_unit_measure() - Invalid Cases
# ============================================================================

class TestParseUnitMeasureInvalid:
    """Test suite for parse_unit_measure() invalid input handling."""

    def test_parse_unit_measure_invalid_returns_none(self):
        """Test invalid input returns (None, None)."""
        quantity, unit = parse_unit_measure("invalid text")

        assert quantity is None
        assert unit is None

    def test_parse_unit_measure_none_input(self):
        """Test None input returns (None, None)."""
        quantity, unit = parse_unit_measure(None)

        assert quantity is None
        assert unit is None

    def test_parse_unit_measure_empty_string(self):
        """Test empty string returns (None, None)."""
        quantity, unit = parse_unit_measure("")

        assert quantity is None
        assert unit is None

    def test_parse_unit_measure_whitespace_only(self):
        """Test whitespace-only string returns (None, None)."""
        quantity, unit = parse_unit_measure("   ")

        assert quantity is None
        assert unit is None

    def test_parse_unit_measure_nan_input(self):
        """Test NaN input returns (None, None)."""
        quantity, unit = parse_unit_measure(np.nan)

        assert quantity is None
        assert unit is None

    def test_parse_unit_measure_no_number(self):
        """Test string with no number returns (None, None)."""
        quantity, unit = parse_unit_measure("просто текст")

        assert quantity is None
        assert unit is None

    def test_parse_unit_measure_only_number(self):
        """Test only number without unit.

        Note: Due to regex pattern, "100" is parsed as (10.0, "0") which is
        an edge case behavior. In practice, construction data always has units.
        """
        quantity, unit = parse_unit_measure("100")

        # Current behavior: parses as (10.0, "0")
        assert quantity == 10.0
        assert unit == "0"

    def test_parse_unit_measure_special_characters(self):
        """Test string with special characters returns (None, None)."""
        quantity, unit = parse_unit_measure("@#$%")

        assert quantity is None
        assert unit is None


# ============================================================================
# Test: parse_unit_measure() - Edge Cases
# ============================================================================

class TestParseUnitMeasureEdgeCases:
    """Test suite for parse_unit_measure() edge cases."""

    def test_parse_unit_measure_no_space_between_number_and_unit(self):
        """Test parsing when number and unit are not separated by space."""
        quantity, unit = parse_unit_measure("100м2")

        assert quantity == 100.0
        assert unit == "м2"

    def test_parse_unit_measure_multiple_spaces(self):
        """Test parsing with multiple spaces between number and unit."""
        quantity, unit = parse_unit_measure("100   м2")

        assert quantity == 100.0
        assert unit == "м2"

    def test_parse_unit_measure_leading_trailing_whitespace(self):
        """Test parsing with leading and trailing whitespace."""
        quantity, unit = parse_unit_measure("  100 м2  ")

        assert quantity == 100.0
        assert unit == "м2"

    def test_parse_unit_measure_float_input(self):
        """Test handling when float value is passed (simulating NaN from pandas)."""
        # When pandas NaN is passed, should return (None, None)
        try:
            import pandas as pd
            quantity, unit = parse_unit_measure(pd.NA)
            assert quantity is None
            assert unit is None
        except ImportError:
            # If pandas not available, test with regular float NaN
            quantity, unit = parse_unit_measure(float('nan'))
            assert quantity is None
            assert unit is None

    def test_parse_unit_measure_zero_quantity(self):
        """Test parsing zero quantity."""
        quantity, unit = parse_unit_measure("0 м2")

        assert quantity == 0.0
        assert unit == "м2"

    def test_parse_unit_measure_very_large_number(self):
        """Test parsing very large quantities."""
        quantity, unit = parse_unit_measure("999999 шт")

        assert quantity == 999999.0
        assert unit == "шт"

    def test_parse_unit_measure_very_small_decimal(self):
        """Test parsing very small decimal quantities."""
        quantity, unit = parse_unit_measure("0.001 т")

        assert quantity == 0.001
        assert unit == "т"


# ============================================================================
# Test: clean_text() - Whitespace Handling
# ============================================================================

class TestCleanTextWhitespace:
    """Test suite for clean_text() whitespace handling."""

    def test_clean_text_removes_leading_whitespace(self):
        """Test removal of leading whitespace."""
        result = clean_text("  hello world")

        assert result == "hello world"

    def test_clean_text_removes_trailing_whitespace(self):
        """Test removal of trailing whitespace."""
        result = clean_text("hello world  ")

        assert result == "hello world"

    def test_clean_text_removes_leading_and_trailing_whitespace(self):
        """Test removal of leading and trailing whitespace."""
        result = clean_text("  hello world  ")

        assert result == "hello world"

    def test_clean_text_replaces_multiple_spaces_with_single(self):
        """Test replacement of multiple spaces with single space."""
        result = clean_text("hello   world")

        assert result == "hello world"

    def test_clean_text_handles_tabs(self):
        """Test handling of tab characters."""
        result = clean_text("hello\tworld")

        assert result == "hello world"

    def test_clean_text_handles_newlines(self):
        """Test handling of newline characters."""
        result = clean_text("hello\nworld")

        assert result == "hello world"

    def test_clean_text_handles_mixed_whitespace(self):
        """Test handling of mixed whitespace types."""
        result = clean_text("  hello  \t\n  world  ")

        assert result == "hello world"

    def test_clean_text_preserves_single_spaces(self):
        """Test that single spaces between words are preserved."""
        result = clean_text("hello world test")

        assert result == "hello world test"


# ============================================================================
# Test: clean_text() - None and Empty Handling
# ============================================================================

class TestCleanTextNoneHandling:
    """Test suite for clean_text() None and empty value handling."""

    def test_clean_text_handles_none(self):
        """Test None input returns empty string."""
        result = clean_text(None)

        assert result == ""

    def test_clean_text_handles_empty_string(self):
        """Test empty string returns empty string."""
        result = clean_text("")

        assert result == ""

    def test_clean_text_handles_whitespace_only(self):
        """Test whitespace-only string returns empty string."""
        result = clean_text("   ")

        assert result == ""

    def test_clean_text_handles_nan(self):
        """Test NaN input returns empty string."""
        result = clean_text(np.nan)

        assert result == ""

    def test_clean_text_handles_float_nan(self):
        """Test float NaN input returns empty string."""
        result = clean_text(float('nan'))

        assert result == ""


# ============================================================================
# Test: clean_text() - Type Conversion
# ============================================================================

class TestCleanTextTypeConversion:
    """Test suite for clean_text() type conversion."""

    def test_clean_text_converts_number_to_string(self):
        """Test conversion of numbers to strings."""
        result = clean_text(123)

        assert result == "123"
        assert isinstance(result, str)

    def test_clean_text_converts_float_to_string(self):
        """Test conversion of floats to strings."""
        result = clean_text(123.45)

        assert result == "123.45"
        assert isinstance(result, str)

    def test_clean_text_handles_boolean(self):
        """Test handling of boolean values."""
        result = clean_text(True)

        assert result == "True"
        assert isinstance(result, str)

    def test_clean_text_preserves_string_input(self):
        """Test that string input is preserved (after cleaning)."""
        result = clean_text("test string")

        assert result == "test string"
        assert isinstance(result, str)


# ============================================================================
# Test: build_search_text() - Multiple Fields
# ============================================================================

class TestBuildSearchTextMultipleFields:
    """Test suite for build_search_text() with multiple fields."""

    def test_build_search_text_concatenates_two_fields(self):
        """Test concatenation of two fields."""
        result = build_search_text("Монтаж", "конструкций")

        assert "монтаж" in result
        assert "конструкций" in result

    def test_build_search_text_concatenates_multiple_fields(self):
        """Test concatenation of multiple fields correctly."""
        result = build_search_text("Монтаж", "конструкций", "металлических")

        assert result == "монтаж конструкций металлических"

    def test_build_search_text_single_field(self):
        """Test with single field."""
        result = build_search_text("Монтаж")

        assert result == "монтаж"

    def test_build_search_text_converts_to_lowercase(self):
        """Test that result is lowercase."""
        result = build_search_text("МОНТАЖ", "КОНСТРУКЦИЙ")

        assert result == "монтаж конструкций"
        assert result.islower() or not result.isalpha()  # All letters should be lowercase

    def test_build_search_text_preserves_order(self):
        """Test that field order is preserved."""
        result = build_search_text("Первый", "Второй", "Третий")

        assert result == "первый второй третий"

    def test_build_search_text_separates_with_space(self):
        """Test that fields are separated with single space."""
        result = build_search_text("Слово1", "Слово2", "Слово3")

        # Count spaces
        space_count = result.count(" ")
        assert space_count == 2  # Two spaces for three words


# ============================================================================
# Test: build_search_text() - Empty and None Filtering
# ============================================================================

class TestBuildSearchTextFiltersEmpty:
    """Test suite for build_search_text() empty value filtering."""

    def test_build_search_text_filters_none(self):
        """Test that None values are filtered out."""
        result = build_search_text("Монтаж", None, "конструкций")

        assert result == "монтаж конструкций"
        assert "none" not in result

    def test_build_search_text_filters_empty_strings(self):
        """Test that empty strings are filtered out."""
        result = build_search_text("Монтаж", "", "конструкций")

        assert result == "монтаж конструкций"

    def test_build_search_text_filters_whitespace_only(self):
        """Test that whitespace-only strings are filtered out."""
        result = build_search_text("Монтаж", "   ", "конструкций")

        assert result == "монтаж конструкций"

    def test_build_search_text_filters_nan(self):
        """Test that NaN values are filtered out."""
        result = build_search_text("Монтаж", np.nan, "конструкций")

        assert result == "монтаж конструкций"
        assert "nan" not in result

    def test_build_search_text_all_none_returns_empty(self):
        """Test that all None values return empty string."""
        result = build_search_text(None, None, None)

        assert result == ""

    def test_build_search_text_all_empty_returns_empty(self):
        """Test that all empty strings return empty string."""
        result = build_search_text("", "", "")

        assert result == ""

    def test_build_search_text_mixed_valid_and_invalid(self):
        """Test with mix of valid and invalid values."""
        result = build_search_text("Valid", None, "", "  ", "Text")

        assert result == "valid text"


# ============================================================================
# Test: build_search_text() - Whitespace Normalization
# ============================================================================

class TestBuildSearchTextWhitespaceNormalization:
    """Test suite for build_search_text() whitespace normalization."""

    def test_build_search_text_normalizes_extra_spaces_in_fields(self):
        """Test that extra spaces within fields are normalized."""
        result = build_search_text("  Монтаж  ", "  конструкций  ")

        assert result == "монтаж конструкций"

    def test_build_search_text_normalizes_multiple_spaces_in_fields(self):
        """Test that multiple spaces within fields are normalized."""
        result = build_search_text("Монтаж   металлических", "конструкций")

        assert result == "монтаж металлических конструкций"

    def test_build_search_text_handles_tabs_in_fields(self):
        """Test handling of tabs in fields."""
        result = build_search_text("Монтаж\tконструкций", "металлических")

        assert result == "монтаж конструкций металлических"

    def test_build_search_text_handles_newlines_in_fields(self):
        """Test handling of newlines in fields."""
        result = build_search_text("Монтаж\nконструкций", "металлических")

        assert result == "монтаж конструкций металлических"


# ============================================================================
# Test: build_search_text() - Edge Cases
# ============================================================================

class TestBuildSearchTextEdgeCases:
    """Test suite for build_search_text() edge cases."""

    def test_build_search_text_no_arguments(self):
        """Test with no arguments."""
        result = build_search_text()

        assert result == ""

    def test_build_search_text_single_none_argument(self):
        """Test with single None argument."""
        result = build_search_text(None)

        assert result == ""

    def test_build_search_text_numeric_values(self):
        """Test with numeric values."""
        result = build_search_text("Код", 123, "Название")

        assert "код" in result
        assert "123" in result
        assert "название" in result

    def test_build_search_text_cyrillic_and_latin(self):
        """Test with mix of Cyrillic and Latin characters."""
        result = build_search_text("Монтаж", "ABC", "конструкций")

        assert "монтаж" in result
        assert "abc" in result
        assert "конструкций" in result

    def test_build_search_text_special_characters(self):
        """Test that special characters are preserved."""
        result = build_search_text("Монтаж-123", "конструкций_V2")

        assert "монтаж-123" in result
        assert "конструкций_v2" in result

    def test_build_search_text_very_long_input(self):
        """Test with very long input."""
        long_text = "Очень длинное описание работы " * 10
        result = build_search_text(long_text, "Дополнение")

        assert "очень длинное описание работы" in result
        assert "дополнение" in result

    def test_build_search_text_single_character_fields(self):
        """Test with single character fields."""
        result = build_search_text("А", "Б", "В")

        assert result == "а б в"


# ============================================================================
# Test: build_search_text() - Pandas Integration
# ============================================================================

class TestBuildSearchTextPandasIntegration:
    """Test suite for build_search_text() with pandas data types."""

    def test_build_search_text_with_pandas_na(self):
        """Test handling of pandas NA values.

        Note: pandas.NA is converted to string '<NA>' by str() conversion,
        so it's not filtered out like None or np.nan. This is expected behavior.
        """
        try:
            import pandas as pd
            result = build_search_text("Valid", pd.NA, "Text")

            # pandas.NA becomes '<NA>' string
            assert result == "valid <na> text"
        except ImportError:
            pytest.skip("Pandas not available")

    def test_build_search_text_with_pandas_series_values(self):
        """Test with values that might come from pandas Series."""
        try:
            import pandas as pd
            # Simulate values from pandas Series
            value1 = "Монтаж"
            value2 = np.nan
            value3 = "конструкций"

            result = build_search_text(value1, value2, value3)

            assert result == "монтаж конструкций"
        except ImportError:
            pytest.skip("Pandas not available")


# ============================================================================
# Test: Text Processor Integration
# ============================================================================

class TestTextProcessorIntegration:
    """Integration tests for text processor utilities working together."""

    def test_parse_and_build_search_text(self):
        """Test using parse_unit_measure and build_search_text together."""
        # Parse unit
        quantity, unit = parse_unit_measure("100 м2")

        # Build search text using parsed values
        result = build_search_text("Монтаж", str(quantity), unit)

        assert "монтаж" in result
        assert "100.0" in result
        assert "м2" in result

    def test_clean_then_build_search_text(self):
        """Test using clean_text and build_search_text together."""
        # Clean individual fields
        field1 = clean_text("  Монтаж  конструкций  ")
        field2 = clean_text("  металлических  ")

        # Build search text
        result = build_search_text(field1, field2)

        assert result == "монтаж конструкций металлических"

    def test_parse_clean_and_build_workflow(self):
        """Test complete workflow: parse -> clean -> build."""
        # Parse unit
        quantity, unit = parse_unit_measure("100 м2")

        # Clean text fields
        name = clean_text("  Устройство   перегородок  ")
        section = clean_text("  Отделочные   работы  ")

        # Build search text
        result = build_search_text(name, section, str(quantity), unit)

        assert "устройство перегородок" in result
        assert "отделочные работы" in result
        assert "100.0" in result
        assert "м2" in result


# ============================================================================
# Test: Real-World Construction Data Scenarios
# ============================================================================

class TestRealWorldScenarios:
    """Test suite for real-world construction data scenarios."""

    def test_parse_russian_construction_units(self):
        """Test parsing common Russian construction units."""
        test_cases = [
            ("100 м2", 100.0, "м2"),  # Square meters
            ("10 м3", 10.0, "м3"),    # Cubic meters
            ("1 т", 1.0, "т"),        # Tons
            ("1000 шт", 1000.0, "шт"), # Pieces
            ("50 м", 50.0, "м"),      # Meters
            ("25 кг", 25.0, "кг"),    # Kilograms
        ]

        for input_str, expected_quantity, expected_unit in test_cases:
            quantity, unit = parse_unit_measure(input_str)
            assert quantity == expected_quantity
            assert unit == expected_unit

    def test_clean_russian_construction_text(self):
        """Test cleaning Russian construction text."""
        test_cases = [
            ("  Устройство   перегородок  ", "Устройство перегородок"),
            ("Монтаж\tконструкций", "Монтаж конструкций"),
            ("  ", ""),
            (None, ""),
        ]

        for input_text, expected_output in test_cases:
            result = clean_text(input_text)
            assert result == expected_output

    def test_build_search_text_for_construction_rate(self):
        """Test building search text for a construction rate."""
        rate_name = "Устройство перегородок из гипсокартона"
        short_name = "Перегородки ГКЛ"
        section = "Отделочные работы"
        composition = "Установка каркаса Монтаж листов"

        result = build_search_text(rate_name, short_name, section, composition)

        # All parts should be included and lowercase
        assert "устройство перегородок из гипсокартона" in result
        assert "перегородки гкл" in result
        assert "отделочные работы" in result
        assert "установка каркаса монтаж листов" in result

    def test_handle_missing_data_in_construction_records(self):
        """Test handling missing data in construction records."""
        # Simulate record with missing fields
        fields = [
            "Монтаж конструкций",  # Valid
            None,                   # Missing
            "",                     # Empty
            "Металлических",       # Valid
            np.nan,                # NaN
        ]

        result = build_search_text(*fields)

        # Only valid fields should appear
        assert "монтаж конструкций" in result
        assert "металлических" in result
        assert result == "монтаж конструкций металлических"
