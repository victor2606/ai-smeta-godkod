"""
Unit Tests for CostCalculator Module

This module tests the CostCalculator class that calculates costs for construction
rates with detailed resource breakdown and proportional quantity adjustments.
"""

import pytest
import sqlite3
from unittest.mock import Mock, patch
from pathlib import Path

from src.search.cost_calculator import CostCalculator
from src.database.db_manager import DatabaseManager


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def db_path():
    """Provide path to the test database."""
    return "data/processed/estimates.db"


@pytest.fixture
def db_manager(db_path):
    """Create DatabaseManager instance for testing."""
    db = DatabaseManager(db_path)
    db.connect()
    yield db
    db.disconnect()


@pytest.fixture
def calculator(db_manager):
    """Create CostCalculator instance with DatabaseManager."""
    return CostCalculator(db_manager)


@pytest.fixture
def mock_db_manager():
    """Create mock DatabaseManager for isolated testing."""
    return Mock(spec=DatabaseManager)


@pytest.fixture
def mock_calculator(mock_db_manager):
    """Create CostCalculator with mocked DatabaseManager."""
    return CostCalculator(mock_db_manager)


@pytest.fixture
def sample_rate_data():
    """Sample rate data for mocking database responses."""
    return [
        (
            '10-05-001-01',  # rate_code
            'Устройство перегородок из гипсокартонных листов (ГКЛ) с одинарным металлическим каркасом и однослойной обшивкой с обеих сторон:',  # rate_full_name
            100,  # unit_quantity
            'м2',  # unit_type
            138320.182816,  # total_cost
            35118.804,  # materials_cost
            103201.378816  # resources_cost
        )
    ]


@pytest.fixture
def sample_resources_data():
    """Sample resources data for mocking."""
    return [
        (
            '01.6.01.02',  # resource_code
            'Листы гипсокартонные',  # resource_name
            'Материал',  # resource_type
            210,  # quantity
            'м2',  # unit
            167.2324,  # unit_cost
            35118.804  # total_cost
        ),
        (
            '02.1.01.01',  # resource_code
            'Монтажник',  # resource_name
            'Ресурс',  # resource_type
            50,  # quantity
            'чел-ч',  # unit
            250.5,  # unit_cost
            12525.0  # total_cost
        )
    ]


# ============================================================================
# Test Basic Calculation
# ============================================================================

class TestBasicCalculation:
    """Test basic calculation functionality."""

    def test_calculate_basic(self, mock_calculator, mock_db_manager, sample_rate_data):
        """Test basic calculation for known rate."""
        # Arrange
        mock_db_manager.execute_query.return_value = sample_rate_data

        # Act
        result = mock_calculator.calculate('10-05-001-01', 100)

        # Assert
        assert 'rate_info' in result
        assert 'base_cost' in result
        assert 'cost_per_unit' in result
        assert 'calculated_total' in result
        assert 'materials' in result
        assert 'resources' in result
        assert 'quantity' in result

        assert result['rate_info']['rate_code'] == '10-05-001-01'
        assert result['quantity'] == 100
        assert result['base_cost'] == 138320.18
        assert result['cost_per_unit'] == 1383.20
        assert result['calculated_total'] == 138320.18

    def test_calculate_gkl_150m2(self, calculator, db_path):
        """Test specific example: rate '10-05-001-01', quantity 150 м².

        Expected calculation:
        - Unit quantity in DB: 100
        - Total cost in DB: 138320.182816
        - Formula: (total_cost / unit_quantity) * user_quantity
        - Result: (138320.182816 / 100) * 150 = 207480.27
        """
        # Skip if database doesn't exist
        if not Path(db_path).exists():
            pytest.skip("Database not available for integration test")

        # Act
        result = calculator.calculate('10-05-001-01', 150)

        # Assert
        assert result['rate_info']['rate_code'] == '10-05-001-01'
        assert result['rate_info']['unit_type'] == 'м2'
        assert result['quantity'] == 150

        # Verify calculation accuracy
        # (138320.182816 / 100) * 150 = 207480.274224 -> rounds to 207480.27
        assert result['calculated_total'] == 207480.27

        # Verify materials cost: (35118.804 / 100) * 150 = 52678.206 -> rounds to 52678.21
        assert result['materials'] == 52678.21

        # Verify resources cost: (103201.378816 / 100) * 150 = 154802.068224 -> rounds to 154802.07
        assert result['resources'] == 154802.07

        # Verify cost_per_unit: 138320.182816 / 100 = 1383.20182816 -> rounds to 1383.20
        assert result['cost_per_unit'] == 1383.20


# ============================================================================
# Test Detailed Breakdown
# ============================================================================

class TestDetailedBreakdown:
    """Test detailed breakdown with resources."""

    def test_calculate_with_resources(self, mock_calculator, mock_db_manager,
                                      sample_rate_data, sample_resources_data):
        """Test detailed breakdown with resources using get_detailed_breakdown()."""
        # Arrange - setup mock to return rate data, then resources, then unit_quantity
        mock_db_manager.execute_query.side_effect = [
            sample_rate_data,  # First call for calculate()
            sample_resources_data,  # Second call for resources in get_detailed_breakdown()
            [(100,)]  # Third call for unit_quantity in get_detailed_breakdown()
        ]

        # Act
        result = mock_calculator.get_detailed_breakdown('10-05-001-01', 150)

        # Assert - verify basic fields
        assert 'breakdown' in result
        assert 'rate_info' in result
        assert 'calculated_total' in result

        # Verify breakdown structure
        assert len(result['breakdown']) == 2

        # Verify first resource (Гипсокартон)
        resource1 = result['breakdown'][0]
        assert resource1['resource_code'] == '01.6.01.02'
        assert resource1['resource_name'] == 'Листы гипсокартонные'
        assert resource1['resource_type'] == 'Материал'
        assert resource1['original_quantity'] == 210
        assert resource1['unit'] == 'м2'
        assert resource1['unit_cost'] == 167.23

        # Verify adjusted quantity: 210 * (150 / 100) = 315
        assert resource1['adjusted_quantity'] == 315.0

        # Verify adjusted cost: 35118.804 * (150 / 100) = 52678.206 -> rounds to 52678.21
        assert resource1['adjusted_cost'] == 52678.21

        # Verify second resource (Монтажник)
        resource2 = result['breakdown'][1]
        assert resource2['resource_code'] == '02.1.01.01'
        assert resource2['resource_type'] == 'Ресурс'
        assert resource2['original_quantity'] == 50

        # Verify adjusted quantity: 50 * (150 / 100) = 75
        assert resource2['adjusted_quantity'] == 75.0


# ============================================================================
# Test Error Handling
# ============================================================================

class TestErrorHandling:
    """Test error handling and validation."""

    def test_calculate_invalid_rate(self, mock_calculator, mock_db_manager):
        """Test non-existent rate should raise ValueError."""
        # Arrange - mock returns empty result (rate not found)
        mock_db_manager.execute_query.return_value = []

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            mock_calculator.calculate('INVALID-RATE-CODE', 100)

        assert "not found" in str(exc_info.value).lower()

    def test_calculate_zero_quantity(self, mock_calculator):
        """Test quantity=0 should raise ValueError."""
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            mock_calculator.calculate('10-05-001-01', 0)

        assert "greater than 0" in str(exc_info.value).lower()

    def test_calculate_negative_quantity(self, mock_calculator):
        """Test negative quantity should raise ValueError."""
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            mock_calculator.calculate('10-05-001-01', -50)

        assert "greater than 0" in str(exc_info.value).lower()

    def test_calculate_empty_rate_code(self, mock_calculator):
        """Test empty rate code should raise ValueError."""
        # Test with empty string
        with pytest.raises(ValueError) as exc_info:
            mock_calculator.calculate('', 100)

        assert "cannot be empty" in str(exc_info.value).lower()

        # Test with whitespace only
        with pytest.raises(ValueError) as exc_info:
            mock_calculator.calculate('   ', 100)

        assert "cannot be empty" in str(exc_info.value).lower()


# ============================================================================
# Test Rounding Behavior
# ============================================================================

class TestRounding:
    """Test monetary value rounding."""

    def test_rounding(self, mock_calculator, mock_db_manager):
        """Test monetary values rounded to 2 decimal places."""
        # Arrange - create data with precise decimal values
        precise_rate_data = [
            (
                'TEST-001',
                'Test Rate',
                100,
                'м2',
                12345.6789,  # total_cost with many decimals
                5432.1098,   # materials_cost
                6913.5691    # resources_cost
            )
        ]
        mock_db_manager.execute_query.return_value = precise_rate_data

        # Act
        result = mock_calculator.calculate('TEST-001', 150)

        # Assert - verify all monetary values are rounded to 2 decimal places
        # base_cost: 12345.6789 -> 12345.68
        assert result['base_cost'] == 12345.68
        assert isinstance(result['base_cost'], float)

        # cost_per_unit: 12345.6789 / 100 = 123.456789 -> 123.46
        assert result['cost_per_unit'] == 123.46

        # calculated_total: 12345.6789 * 1.5 = 18518.51835 -> 18518.52
        assert result['calculated_total'] == 18518.52

        # materials: 5432.1098 * 1.5 = 8148.1647 -> 8148.16
        assert result['materials'] == 8148.16

        # resources: 6913.5691 * 1.5 = 10370.35365 -> 10370.35
        assert result['resources'] == 10370.35

        # Verify no value has more than 2 decimal places
        for key in ['base_cost', 'cost_per_unit', 'calculated_total', 'materials', 'resources']:
            value_str = str(result[key])
            if '.' in value_str:
                decimal_places = len(value_str.split('.')[1])
                assert decimal_places <= 2, f"{key} has more than 2 decimal places: {result[key]}"


# ============================================================================
# Test Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_calculate_very_small_quantity(self, mock_calculator, mock_db_manager, sample_rate_data):
        """Test calculation with very small quantity."""
        # Arrange
        mock_db_manager.execute_query.return_value = sample_rate_data

        # Act
        result = mock_calculator.calculate('10-05-001-01', 0.01)

        # Assert
        assert result['quantity'] == 0.01
        # 138320.182816 * (0.01 / 100) = 13.832018... -> 13.83
        assert result['calculated_total'] == 13.83

    def test_calculate_very_large_quantity(self, mock_calculator, mock_db_manager, sample_rate_data):
        """Test calculation with very large quantity."""
        # Arrange
        mock_db_manager.execute_query.return_value = sample_rate_data

        # Act
        result = mock_calculator.calculate('10-05-001-01', 10000)

        # Assert
        assert result['quantity'] == 10000
        # 138320.182816 * (10000 / 100) = 13832018.2816 -> 13832018.28
        assert result['calculated_total'] == 13832018.28

    def test_calculate_fractional_quantity(self, mock_calculator, mock_db_manager, sample_rate_data):
        """Test calculation with fractional quantity."""
        # Arrange
        mock_db_manager.execute_query.return_value = sample_rate_data

        # Act
        result = mock_calculator.calculate('10-05-001-01', 123.45)

        # Assert
        assert result['quantity'] == 123.45
        # 138320.182816 * (123.45 / 100) = 170726.4056... -> rounds to 170726.41
        # Note: Due to Python's rounding behavior, let's verify the result is close
        expected = round(138320.182816 * (123.45 / 100), 2)
        assert result['calculated_total'] == expected

    def test_database_error_handling(self, mock_calculator, mock_db_manager):
        """Test handling of database errors."""
        # Arrange - mock raises sqlite3.Error
        mock_db_manager.execute_query.side_effect = sqlite3.Error("Database connection failed")

        # Act & Assert
        with pytest.raises(sqlite3.Error) as exc_info:
            mock_calculator.calculate('10-05-001-01', 100)

        assert "Database error" in str(exc_info.value)


# ============================================================================
# Integration Tests (require actual database)
# ============================================================================

@pytest.mark.integration
class TestIntegration:
    """Integration tests that require actual database."""

    def test_calculate_with_real_database(self, calculator, db_path):
        """Test calculation with real database data."""
        # Skip if database doesn't exist
        if not Path(db_path).exists():
            pytest.skip("Database not available for integration test")

        # Act
        result = calculator.calculate('10-05-001-01', 100)

        # Assert
        assert result['rate_info']['rate_code'] == '10-05-001-01'
        assert result['calculated_total'] > 0
        assert result['materials'] > 0
        assert result['resources'] > 0

    def test_detailed_breakdown_with_real_database(self, calculator, db_path):
        """Test detailed breakdown with real database data."""
        # Skip if database doesn't exist
        if not Path(db_path).exists():
            pytest.skip("Database not available for integration test")

        # Act
        result = calculator.get_detailed_breakdown('10-05-001-01', 150)

        # Assert
        assert 'breakdown' in result
        assert len(result['breakdown']) > 0

        # Verify at least one resource exists
        first_resource = result['breakdown'][0]
        assert 'resource_code' in first_resource
        assert 'resource_name' in first_resource
        assert 'adjusted_quantity' in first_resource
        assert 'adjusted_cost' in first_resource

    def test_multiple_rates_integration(self, calculator, db_path):
        """Test calculation for multiple different rates."""
        # Skip if database doesn't exist
        if not Path(db_path).exists():
            pytest.skip("Database not available for integration test")

        # Test multiple rates if they exist
        test_rates = ['10-05-001-01', '10-06-037-02']

        for rate_code in test_rates:
            try:
                result = calculator.calculate(rate_code, 100)
                assert result['calculated_total'] > 0
                assert result['rate_info']['rate_code'] == rate_code
            except ValueError:
                # Rate might not exist in database, skip
                pytest.skip(f"Rate {rate_code} not found in database")
