"""
Cost Calculator Module for Construction Rates

This module provides the CostCalculator class that calculates costs for construction
rates with detailed resource breakdown and proportional quantity adjustments.
"""

import sqlite3
import logging
from typing import Dict, List, Any, Optional

from src.database.db_manager import DatabaseManager


# Configure logging
logger = logging.getLogger(__name__)


class CostCalculator:
    """
    Calculator for construction rate costs with detailed resource breakdowns.

    This class calculates costs for construction rates based on rate codes and
    desired quantities, providing detailed breakdowns of materials, labor, and
    machinery resources with proportional cost adjustments.

    Attributes:
        db_manager (DatabaseManager): Database manager instance for executing queries

    Example:
        >>> from src.database.db_manager import DatabaseManager
        >>> db = DatabaseManager('data/processed/estimates.db')
        >>> calculator = CostCalculator(db)
        >>> result = calculator.calculate("ГЭСНп81-01-001-01", 150)
        >>> breakdown = calculator.get_detailed_breakdown("ГЭСНп81-01-001-01", 150)
    """

    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize CostCalculator with database manager.

        Args:
            db_manager: DatabaseManager instance for database operations
        """
        self.db_manager = db_manager
        logger.info("CostCalculator initialized")

    def calculate(self, rate_code: str, quantity: float) -> Dict[str, Any]:
        """
        Calculate total cost for a given rate code and quantity.

        This method retrieves the rate information from the database and calculates
        the total cost based on the specified quantity, adjusting for the rate's
        unit quantity.

        Args:
            rate_code: Rate identifier code (e.g., "ГЭСНп81-01-001-01")
            quantity: Desired quantity to calculate (must be > 0)

        Returns:
            Dict with keys:
                - rate_info: Dict with rate_code, rate_full_name, unit_type
                - base_cost: Total cost from database for the rate's unit_quantity
                - cost_per_unit: Cost per single unit (base_cost / unit_quantity)
                - calculated_total: Total cost for the specified quantity
                - materials: Materials cost for the specified quantity
                - resources: Resources (labor/machinery) cost for the specified quantity
                - quantity: The quantity used in calculation

        Raises:
            ValueError: If rate_code is empty, quantity <= 0, or rate not found
            sqlite3.Error: If database query fails

        Examples:
            >>> # Calculate cost for 150 m2
            >>> result = calculator.calculate("ГЭСНп81-01-001-01", 150)
            >>> print(f"Total: {result['calculated_total']}")

            >>> # Access rate information
            >>> print(f"Rate: {result['rate_info']['rate_full_name']}")
        """
        # Validate inputs
        if not rate_code or not rate_code.strip():
            logger.error("Empty rate_code provided")
            raise ValueError("Rate code cannot be empty")

        if quantity <= 0:
            logger.error(f"Invalid quantity: {quantity}")
            raise ValueError("Quantity must be greater than 0")

        rate_code = rate_code.strip()
        logger.info(f"Calculating cost for rate '{rate_code}' with quantity {quantity}")

        # Query rate from database
        sql = """
            SELECT
                rate_code,
                rate_full_name,
                unit_quantity,
                unit_type,
                total_cost,
                material_cost,
                (labor_cost + machine_cost) as resources_cost
            FROM rates
            WHERE rate_code = ?
        """

        try:
            rows = self.db_manager.execute_query(sql, (rate_code,))

            if not rows:
                logger.error(f"Rate code not found: {rate_code}")
                raise ValueError(f"Rate code '{rate_code}' not found in database")

            # Unpack rate data
            (
                code,
                full_name,
                unit_quantity,
                unit_type,
                total_cost,
                material_cost,
                resources_cost,
            ) = rows[0]

            # Validate unit_quantity
            if unit_quantity <= 0:
                logger.error(f"Invalid unit_quantity in database: {unit_quantity}")
                raise ValueError(
                    f"Rate '{rate_code}' has invalid unit_quantity: {unit_quantity}"
                )

            # Calculate cost per unit
            cost_per_unit = total_cost / unit_quantity

            # Calculate proportional costs for desired quantity
            multiplier = quantity / unit_quantity
            calculated_total = total_cost * multiplier
            adjusted_materials = material_cost * multiplier
            adjusted_resources = resources_cost * multiplier

            # Build result dictionary
            result = {
                "rate_info": {
                    "rate_code": code,
                    "rate_full_name": full_name,
                    "unit_type": unit_type,
                },
                "base_cost": round(total_cost, 2),
                "cost_per_unit": round(cost_per_unit, 2),
                "calculated_total": round(calculated_total, 2),
                "materials": round(adjusted_materials, 2),
                "resources": round(adjusted_resources, 2),
                "quantity": quantity,
            }

            logger.info(
                f"Calculation complete: {rate_code} x {quantity} = "
                f"{result['calculated_total']}"
            )

            return result

        except sqlite3.Error as e:
            error_msg = f"Database error during cost calculation: {str(e)}"
            logger.error(error_msg)
            raise sqlite3.Error(error_msg) from e

    def get_detailed_breakdown(self, rate_code: str, quantity: float) -> Dict[str, Any]:
        """
        Get detailed cost breakdown including all resources.

        This method extends calculate() by providing a detailed breakdown of all
        resources (materials, labor, machinery) associated with the rate, with
        quantities and costs proportionally adjusted for the specified quantity.

        Args:
            rate_code: Rate identifier code
            quantity: Desired quantity to calculate (must be > 0)

        Returns:
            Dict containing all fields from calculate() plus:
                - breakdown: List of dicts, each containing:
                    - resource_code: Resource identifier
                    - resource_name: Resource description
                    - resource_type: Type of resource (e.g., 'Ресурс', 'Материал')
                    - original_quantity: Resource quantity in database
                    - adjusted_quantity: Resource quantity adjusted for specified quantity
                    - unit: Unit of measurement
                    - unit_cost: Cost per unit of resource
                    - adjusted_cost: Total cost for adjusted quantity

        Raises:
            ValueError: If rate_code is empty, quantity <= 0, or rate not found
            sqlite3.Error: If database query fails

        Example:
            >>> breakdown = calculator.get_detailed_breakdown("ГЭСНп81-01-001-01", 150)
            >>> for resource in breakdown['breakdown']:
            ...     print(f"{resource['resource_name']}: {resource['adjusted_quantity']} {resource['unit']}")
        """
        # Get basic calculation first (validates inputs)
        result = self.calculate(rate_code, quantity)

        # Query resources for this rate
        # Note: Minimal schema only has resource_code, resource_cost, median_price
        # Full schema has resource_name, resource_type, quantity, unit, unit_cost, total_cost
        sql = """
            SELECT
                resource_code,
                resource_cost,
                median_price
            FROM resources
            WHERE rate_code = ?
            ORDER BY resource_code
        """

        try:
            rows = self.db_manager.execute_query(sql, (rate_code,))

            # Check if we got results
            if not rows:
                # Return basic calculation with note about missing detailed breakdown
                result["breakdown"] = []
                result["note"] = (
                    "Detailed resource breakdown not available in current database schema"
                )
                return result

            # Get unit_quantity from result to calculate multiplier
            sql_rate = """
                SELECT unit_quantity
                FROM rates
                WHERE rate_code = ?
            """
            rate_rows = self.db_manager.execute_query(sql_rate, (rate_code,))
            unit_quantity = rate_rows[0][0]

            # Validate unit_quantity to prevent division by zero
            if unit_quantity <= 0:
                logger.error(
                    f"Invalid unit_quantity in database for rate '{rate_code}': {unit_quantity}"
                )
                raise ValueError(
                    f"Rate '{rate_code}' has invalid unit_quantity: {unit_quantity}"
                )

            # Calculate multiplier for proportional adjustments
            multiplier = quantity / unit_quantity

            # Build resource breakdown (minimal schema version)
            breakdown = []
            for row in rows:
                resource_code, resource_cost, median_price = row

                # Calculate adjusted cost for this quantity
                adjusted_cost = resource_cost * multiplier

                breakdown.append(
                    {
                        "resource_code": resource_code,
                        "resource_cost_per_unit": round(resource_cost, 2),
                        "median_price": round(median_price, 2)
                        if median_price
                        else None,
                        "adjusted_cost": round(adjusted_cost, 2),
                        "note": "Minimal schema - detailed resource info unavailable",
                    }
                )

            # Add breakdown to result
            result["breakdown"] = breakdown

            logger.info(
                f"Detailed breakdown complete: {rate_code} with "
                f"{len(breakdown)} resources"
            )

            return result

        except sqlite3.Error as e:
            error_msg = f"Database error during breakdown calculation: {str(e)}"
            logger.error(error_msg)
            raise sqlite3.Error(error_msg) from e
