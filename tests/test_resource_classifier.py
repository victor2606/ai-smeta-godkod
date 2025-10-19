"""
Unit Tests for Resource Classifier Utility

Tests for construction resource type classification including:
- Labor classification ('Состав работ')
- Material classification (resource_code starting with 'M')
- Machinery classification (resource_code starting with '1-')
- Equipment classification (default fallback)
- Edge cases: None values, empty strings, whitespace handling
"""

import pytest
from src.utils.resource_classifier import classify_resource_type, _safe_str


# ============================================================================
# Pytest Fixtures
# ============================================================================

@pytest.fixture
def sample_labor_data():
    """
    Fixture providing sample data for labor classification.

    Returns:
        tuple: (row_type, resource_code, resource_name) for labor resource
    """
    return ('Состав работ', 'R001', 'Монтажник')


@pytest.fixture
def sample_material_data():
    """
    Fixture providing sample data for material classification.

    Returns:
        tuple: (row_type, resource_code, resource_name) for material resource
    """
    return ('Ресурс', 'M123', 'Цемент')


@pytest.fixture
def sample_machinery_data():
    """
    Fixture providing sample data for machinery classification.

    Returns:
        tuple: (row_type, resource_code, resource_name) for machinery resource
    """
    return ('Ресурс', '1-001', 'Экскаватор')


@pytest.fixture
def sample_equipment_data():
    """
    Fixture providing sample data for equipment classification.

    Returns:
        tuple: (row_type, resource_code, resource_name) for equipment resource
    """
    return ('Ресурс', 'E456', 'Инструмент')


# ============================================================================
# Test: classify_resource_type() - Labor Classification
# ============================================================================

class TestClassifyResourceTypeLabor:
    """Test suite for labor resource classification."""

    def test_classify_labor_basic(self, sample_labor_data):
        """Test basic labor classification with 'Состав работ'."""
        row_type, resource_code, resource_name = sample_labor_data
        result = classify_resource_type(row_type, resource_code, resource_name)

        assert result == 'labor'

    def test_classify_labor_with_different_codes(self):
        """Test labor classification with various resource codes."""
        test_cases = [
            ('Состав работ', 'R001', 'Монтажник'),
            ('Состав работ', 'L123', 'Сварщик'),
            ('Состав работ', 'W999', 'Маляр'),
            ('Состав работ', '', 'Работник'),
        ]

        for row_type, resource_code, resource_name in test_cases:
            result = classify_resource_type(row_type, resource_code, resource_name)
            assert result == 'labor', f"Failed for code: {resource_code}"

    def test_classify_labor_ignores_resource_code(self):
        """Test that labor classification does not depend on resource_code."""
        # Even with material-like code 'M123', should still be labor
        result = classify_resource_type('Состав работ', 'M123', 'Рабочий')
        assert result == 'labor'

        # Even with machinery-like code '1-001', should still be labor
        result = classify_resource_type('Состав работ', '1-001', 'Рабочий')
        assert result == 'labor'

    def test_classify_labor_with_empty_resource_code(self):
        """Test labor classification with empty resource code."""
        result = classify_resource_type('Состав работ', '', 'Рабочий')
        assert result == 'labor'

    def test_classify_labor_with_none_resource_code(self):
        """Test labor classification with None resource code."""
        result = classify_resource_type('Состав работ', None, 'Рабочий')
        assert result == 'labor'


# ============================================================================
# Test: classify_resource_type() - Material Classification
# ============================================================================

class TestClassifyResourceTypeMaterial:
    """Test suite for material resource classification."""

    def test_classify_material_basic(self, sample_material_data):
        """Test basic material classification with 'M' prefix."""
        row_type, resource_code, resource_name = sample_material_data
        result = classify_resource_type(row_type, resource_code, resource_name)

        assert result == 'material'

    def test_classify_material_various_m_codes(self):
        """Test material classification with various 'M' prefixed codes."""
        test_cases = [
            ('Ресурс', 'M001', 'Цемент'),
            ('Ресурс', 'M999', 'Бетон'),
            ('Ресурс', 'M123-456', 'Арматура'),
            ('Ресурс', 'MATERIAL', 'Песок'),
            ('Ресурс', 'Mat123', 'Щебень'),
        ]

        for row_type, resource_code, resource_name in test_cases:
            result = classify_resource_type(row_type, resource_code, resource_name)
            assert result == 'material', f"Failed for code: {resource_code}"

    def test_classify_material_case_sensitive(self):
        """Test that material classification is case-sensitive ('M' not 'm')."""
        # Uppercase 'M' should be material
        result = classify_resource_type('Ресурс', 'M123', 'Цемент')
        assert result == 'material'

        # Lowercase 'm' should NOT be material (should be equipment)
        result = classify_resource_type('Ресурс', 'm123', 'Материал')
        assert result == 'equipment'

    def test_classify_material_m_in_middle_not_matched(self):
        """Test that 'M' in middle of code does not classify as material."""
        result = classify_resource_type('Ресурс', 'RM123', 'Ресурс')
        assert result == 'equipment'

        result = classify_resource_type('Ресурс', '1M23', 'Ресурс')
        assert result == 'equipment'

    def test_classify_material_requires_resource_row_type(self):
        """Test that material classification requires row_type 'Ресурс'."""
        # With 'Расценка' row type, should return equipment
        result = classify_resource_type('Расценка', 'M123', 'Материал')
        assert result == 'equipment'

        # With unknown row type, should return equipment
        result = classify_resource_type('Неизвестно', 'M123', 'Материал')
        assert result == 'equipment'


# ============================================================================
# Test: classify_resource_type() - Machinery Classification
# ============================================================================

class TestClassifyResourceTypeMachinery:
    """Test suite for machinery resource classification."""

    def test_classify_machinery_basic(self, sample_machinery_data):
        """Test basic machinery classification with '1-' prefix."""
        row_type, resource_code, resource_name = sample_machinery_data
        result = classify_resource_type(row_type, resource_code, resource_name)

        assert result == 'machinery'

    def test_classify_machinery_various_1_dash_codes(self):
        """Test machinery classification with various '1-' prefixed codes."""
        test_cases = [
            ('Ресурс', '1-001', 'Экскаватор'),
            ('Ресурс', '1-999', 'Кран'),
            ('Ресурс', '1-123-456', 'Бульдозер'),
            ('Ресурс', '1-A', 'Погрузчик'),
        ]

        for row_type, resource_code, resource_name in test_cases:
            result = classify_resource_type(row_type, resource_code, resource_name)
            assert result == 'machinery', f"Failed for code: {resource_code}"

    def test_classify_machinery_exact_prefix_match(self):
        """Test that machinery classification requires exact '1-' prefix."""
        # Should match '1-'
        result = classify_resource_type('Ресурс', '1-001', 'Машина')
        assert result == 'machinery'

        # Should NOT match '1' without dash
        result = classify_resource_type('Ресурс', '1001', 'Машина')
        assert result == 'equipment'

        # Should NOT match '11-' (extra digit)
        result = classify_resource_type('Ресурс', '11-001', 'Машина')
        assert result == 'equipment'

        # Should NOT match '2-'
        result = classify_resource_type('Ресурс', '2-001', 'Машина')
        assert result == 'equipment'

    def test_classify_machinery_requires_resource_row_type(self):
        """Test that machinery classification requires row_type 'Ресурс'."""
        # With 'Расценка' row type, should return equipment
        result = classify_resource_type('Расценка', '1-001', 'Экскаватор')
        assert result == 'equipment'

        # With unknown row type, should return equipment
        result = classify_resource_type('Неизвестно', '1-001', 'Экскаватор')
        assert result == 'equipment'

    def test_classify_machinery_1_dash_in_middle_not_matched(self):
        """Test that '1-' in middle of code does not classify as machinery."""
        result = classify_resource_type('Ресурс', 'A1-001', 'Ресурс')
        assert result == 'equipment'


# ============================================================================
# Test: classify_resource_type() - Equipment Classification
# ============================================================================

class TestClassifyResourceTypeEquipment:
    """Test suite for equipment resource classification (default fallback)."""

    def test_classify_equipment_basic(self, sample_equipment_data):
        """Test basic equipment classification with non-matching code."""
        row_type, resource_code, resource_name = sample_equipment_data
        result = classify_resource_type(row_type, resource_code, resource_name)

        assert result == 'equipment'

    def test_classify_equipment_various_codes(self):
        """Test equipment classification with various resource codes."""
        test_cases = [
            ('Ресурс', 'E456', 'Инструмент'),
            ('Ресурс', 'T123', 'Оборудование'),
            ('Ресурс', 'ABC', 'Приспособление'),
            ('Ресурс', '2-001', 'Устройство'),
            ('Ресурс', '999', 'Инвентарь'),
        ]

        for row_type, resource_code, resource_name in test_cases:
            result = classify_resource_type(row_type, resource_code, resource_name)
            assert result == 'equipment', f"Failed for code: {resource_code}"

    def test_classify_equipment_unknown_row_type(self):
        """Test that unknown row types default to equipment."""
        unknown_row_types = [
            'Расценка',
            'Неизвестно',
            'Unknown',
            'Other',
            'Test',
        ]

        for row_type in unknown_row_types:
            result = classify_resource_type(row_type, 'CODE', 'Name')
            assert result == 'equipment', f"Failed for row_type: {row_type}"

    def test_classify_equipment_empty_row_type(self):
        """Test that empty row_type defaults to equipment."""
        result = classify_resource_type('', 'CODE', 'Name')
        assert result == 'equipment'

    def test_classify_equipment_empty_resource_code(self):
        """Test equipment classification with empty resource code."""
        result = classify_resource_type('Ресурс', '', 'Оборудование')
        assert result == 'equipment'


# ============================================================================
# Test: classify_resource_type() - Edge Cases: None Values
# ============================================================================

class TestClassifyResourceTypeNoneValues:
    """Test suite for handling None values in classification."""

    def test_classify_all_none_values(self):
        """Test classification with all None values."""
        result = classify_resource_type(None, None, None)
        assert result == 'equipment'

    def test_classify_none_row_type(self):
        """Test classification with None row_type."""
        result = classify_resource_type(None, 'M123', 'Материал')
        assert result == 'equipment'

    def test_classify_none_resource_code(self):
        """Test classification with None resource_code."""
        result = classify_resource_type('Ресурс', None, 'Ресурс')
        assert result == 'equipment'

    def test_classify_none_resource_name(self):
        """Test that None resource_name does not affect classification."""
        # Labor should still work
        result = classify_resource_type('Состав работ', 'R001', None)
        assert result == 'labor'

        # Material should still work
        result = classify_resource_type('Ресурс', 'M123', None)
        assert result == 'material'

        # Machinery should still work
        result = classify_resource_type('Ресурс', '1-001', None)
        assert result == 'machinery'

    def test_classify_none_combinations(self):
        """Test various combinations of None values."""
        test_cases = [
            (None, None, 'Name'),
            (None, 'CODE', None),
            ('Ресурс', None, None),
            (None, 'M123', 'Material'),
            ('Состав работ', None, 'Worker'),
        ]

        for row_type, resource_code, resource_name in test_cases:
            # Should not raise exception
            result = classify_resource_type(row_type, resource_code, resource_name)
            assert isinstance(result, str)


# ============================================================================
# Test: classify_resource_type() - Edge Cases: Empty Strings
# ============================================================================

class TestClassifyResourceTypeEmptyStrings:
    """Test suite for handling empty strings in classification."""

    def test_classify_all_empty_strings(self):
        """Test classification with all empty strings."""
        result = classify_resource_type('', '', '')
        assert result == 'equipment'

    def test_classify_empty_row_type_with_material_code(self):
        """Test that empty row_type with 'M' code returns equipment."""
        result = classify_resource_type('', 'M123', 'Материал')
        assert result == 'equipment'

    def test_classify_empty_row_type_with_machinery_code(self):
        """Test that empty row_type with '1-' code returns equipment."""
        result = classify_resource_type('', '1-001', 'Машина')
        assert result == 'equipment'

    def test_classify_empty_resource_code_with_resource_row_type(self):
        """Test that empty resource_code with 'Ресурс' returns equipment."""
        result = classify_resource_type('Ресурс', '', 'Ресурс')
        assert result == 'equipment'

    def test_classify_empty_combinations(self):
        """Test various combinations of empty strings."""
        test_cases = [
            ('', '', 'Name'),
            ('', 'CODE', ''),
            ('Ресурс', '', ''),
            ('', 'M123', 'Material'),
            ('Состав работ', '', 'Worker'),
        ]

        for row_type, resource_code, resource_name in test_cases:
            # Should not raise exception
            result = classify_resource_type(row_type, resource_code, resource_name)
            assert isinstance(result, str)


# ============================================================================
# Test: classify_resource_type() - Edge Cases: Whitespace Handling
# ============================================================================

class TestClassifyResourceTypeWhitespace:
    """Test suite for whitespace handling in classification."""

    def test_classify_labor_with_whitespace(self):
        """Test labor classification with whitespace in row_type."""
        test_cases = [
            ('  Состав работ  ', 'R001', 'Рабочий'),
            ('Состав работ\n', 'R001', 'Рабочий'),
            ('\tСостав работ', 'R001', 'Рабочий'),
        ]

        for row_type, resource_code, resource_name in test_cases:
            result = classify_resource_type(row_type, resource_code, resource_name)
            assert result == 'labor', f"Failed for row_type: '{row_type}'"

    def test_classify_resource_with_whitespace(self):
        """Test resource classification with whitespace in row_type."""
        test_cases = [
            ('  Ресурс  ', 'M123', 'Материал'),
            ('Ресурс\n', '1-001', 'Машина'),
            ('\tРесурс', 'E456', 'Оборудование'),
        ]

        for row_type, resource_code, resource_name in test_cases:
            result = classify_resource_type(row_type, resource_code, resource_name)
            assert result in ['material', 'machinery', 'equipment'], \
                f"Failed for row_type: '{row_type}'"

    def test_classify_material_with_whitespace_in_code(self):
        """Test material classification with whitespace in resource_code."""
        test_cases = [
            ('Ресурс', '  M123  ', 'Материал'),
            ('Ресурс', 'M123\n', 'Материал'),
            ('Ресурс', '\tM123', 'Материал'),
        ]

        for row_type, resource_code, resource_name in test_cases:
            result = classify_resource_type(row_type, resource_code, resource_name)
            assert result == 'material', f"Failed for code: '{resource_code}'"

    def test_classify_machinery_with_whitespace_in_code(self):
        """Test machinery classification with whitespace in resource_code."""
        test_cases = [
            ('Ресурс', '  1-001  ', 'Машина'),
            ('Ресурс', '1-001\n', 'Машина'),
            ('Ресурс', '\t1-001', 'Машина'),
        ]

        for row_type, resource_code, resource_name in test_cases:
            result = classify_resource_type(row_type, resource_code, resource_name)
            assert result == 'machinery', f"Failed for code: '{resource_code}'"

    def test_classify_whitespace_only_strings(self):
        """Test classification with whitespace-only strings."""
        test_cases = [
            ('   ', '   ', '   '),
            ('\t\t', '\n\n', '  '),
            ('  ', 'M123', 'Material'),
            ('Ресурс', '   ', 'Resource'),
        ]

        for row_type, resource_code, resource_name in test_cases:
            # Should not raise exception
            result = classify_resource_type(row_type, resource_code, resource_name)
            assert isinstance(result, str)


# ============================================================================
# Test: classify_resource_type() - Return Type Validation
# ============================================================================

class TestClassifyResourceTypeReturnTypes:
    """Test suite for validating return types."""

    def test_classify_always_returns_string(self):
        """Test that classification always returns a string."""
        test_cases = [
            ('Состав работ', 'R001', 'Рабочий'),
            ('Ресурс', 'M123', 'Материал'),
            ('Ресурс', '1-001', 'Машина'),
            ('Ресурс', 'E456', 'Оборудование'),
            (None, None, None),
            ('', '', ''),
        ]

        for row_type, resource_code, resource_name in test_cases:
            result = classify_resource_type(row_type, resource_code, resource_name)
            assert isinstance(result, str)

    def test_classify_returns_valid_resource_types(self):
        """Test that classification only returns valid resource types."""
        valid_types = {'labor', 'material', 'machinery', 'equipment'}

        test_cases = [
            ('Состав работ', 'R001', 'Рабочий'),
            ('Ресурс', 'M123', 'Материал'),
            ('Ресурс', '1-001', 'Машина'),
            ('Ресурс', 'E456', 'Оборудование'),
            ('Расценка', 'R001', 'Расценка'),
            (None, None, None),
        ]

        for row_type, resource_code, resource_name in test_cases:
            result = classify_resource_type(row_type, resource_code, resource_name)
            assert result in valid_types, f"Invalid type returned: {result}"


# ============================================================================
# Test: _safe_str() Helper Function
# ============================================================================

class TestSafeStrHelper:
    """Test suite for _safe_str() helper function."""

    def test_safe_str_none_returns_empty(self):
        """Test that None returns empty string."""
        result = _safe_str(None)
        assert result == ''
        assert isinstance(result, str)

    def test_safe_str_empty_string_returns_empty(self):
        """Test that empty string returns empty string."""
        result = _safe_str('')
        assert result == ''

    def test_safe_str_whitespace_returns_empty(self):
        """Test that whitespace-only strings are stripped to empty."""
        test_cases = ['   ', '\t', '\n', '  \t\n  ']

        for value in test_cases:
            result = _safe_str(value)
            assert result == '', f"Failed for: '{value}'"

    def test_safe_str_strips_whitespace(self):
        """Test that leading/trailing whitespace is stripped."""
        test_cases = [
            ('  test  ', 'test'),
            ('\ttest\n', 'test'),
            ('  M123  ', 'M123'),
            ('  Состав работ  ', 'Состав работ'),
        ]

        for input_val, expected in test_cases:
            result = _safe_str(input_val)
            assert result == expected

    def test_safe_str_converts_to_string(self):
        """Test that non-string values are converted to strings."""
        test_cases = [
            (123, '123'),
            (45.67, '45.67'),
            (True, 'True'),
            (False, 'False'),
        ]

        for input_val, expected in test_cases:
            result = _safe_str(input_val)
            assert result == expected
            assert isinstance(result, str)

    def test_safe_str_handles_unicode(self):
        """Test that Unicode strings are handled correctly."""
        test_cases = [
            ('Состав работ', 'Состав работ'),
            ('Ресурс', 'Ресурс'),
            ('  Цемент  ', 'Цемент'),
            ('Экскаватор', 'Экскаватор'),
        ]

        for input_val, expected in test_cases:
            result = _safe_str(input_val)
            assert result == expected

    def test_safe_str_handles_numeric_strings(self):
        """Test that numeric strings are handled correctly."""
        test_cases = [
            ('123', '123'),
            ('  456  ', '456'),
            ('1-001', '1-001'),
            ('M123', 'M123'),
        ]

        for input_val, expected in test_cases:
            result = _safe_str(input_val)
            assert result == expected


# ============================================================================
# Test: Integration and Real-World Scenarios
# ============================================================================

class TestClassifyResourceTypeIntegration:
    """Integration tests for real-world classification scenarios."""

    def test_classify_multiple_resources_from_same_rate(self):
        """Test classification of multiple resources from the same construction rate."""
        resources = [
            ('Состав работ', 'C001', 'Установка каркаса'),
            ('Состав работ', 'C002', 'Монтаж листов'),
            ('Ресурс', 'M001', 'Гипсокартон'),
            ('Ресурс', 'M002', 'Профиль металлический'),
            ('Ресурс', '1-001', 'Шуруповерт'),
            ('Ресурс', 'E123', 'Уровень строительный'),
        ]

        expected_types = ['labor', 'labor', 'material', 'material', 'machinery', 'equipment']

        for (row_type, code, name), expected_type in zip(resources, expected_types):
            result = classify_resource_type(row_type, code, name)
            assert result == expected_type, \
                f"Failed for {code}: expected {expected_type}, got {result}"

    def test_classify_real_world_examples_from_docstring(self):
        """Test real-world examples from function docstring."""
        # Examples from classify_resource_type docstring
        test_cases = [
            (('Состав работ', 'R001', 'Монтажник'), 'labor'),
            (('Ресурс', 'M123', 'Цемент'), 'material'),
            (('Ресурс', '1-001', 'Экскаватор'), 'machinery'),
            (('Ресурс', 'E456', 'Инструмент'), 'equipment'),
            (('Расценка', '', ''), 'equipment'),
            ((None, None, None), 'equipment'),
        ]

        for (row_type, code, name), expected in test_cases:
            result = classify_resource_type(row_type, code, name)
            assert result == expected, \
                f"Docstring example failed: {row_type}, {code} -> expected {expected}, got {result}"

    def test_classify_mixed_case_scenarios(self):
        """Test classification with mixed valid and edge case data."""
        test_cases = [
            # Valid labor
            (('Состав работ', 'L001', 'Каменщик'), 'labor'),
            # Valid material with extra whitespace
            (('  Ресурс  ', '  M999  ', 'Бетон'), 'material'),
            # Valid machinery with trailing newline
            (('Ресурс', '1-123\n', 'Кран'), 'machinery'),
            # Equipment with empty code
            (('Ресурс', '', 'Инвентарь'), 'equipment'),
            # Unknown row type with material code
            (('Unknown', 'M123', 'Material'), 'equipment'),
            # Empty row type with machinery code
            (('', '1-001', 'Машина'), 'equipment'),
        ]

        for (row_type, code, name), expected in test_cases:
            result = classify_resource_type(row_type, code, name)
            assert result == expected

    def test_classify_preserves_classification_logic_order(self):
        """Test that classification logic follows priority: labor -> material -> machinery -> equipment."""
        # Labor has highest priority (ignores resource code)
        assert classify_resource_type('Состав работ', 'M123', 'Worker') == 'labor'
        assert classify_resource_type('Состав работ', '1-001', 'Worker') == 'labor'

        # Material has priority over machinery and equipment
        assert classify_resource_type('Ресурс', 'M123', 'Material') == 'material'
        assert classify_resource_type('Ресурс', 'M1-001', 'Material') == 'material'

        # Machinery has priority over equipment
        assert classify_resource_type('Ресурс', '1-001', 'Machine') == 'machinery'

        # Equipment is default fallback
        assert classify_resource_type('Ресурс', 'E123', 'Equipment') == 'equipment'
        assert classify_resource_type('Unknown', 'CODE', 'Resource') == 'equipment'
