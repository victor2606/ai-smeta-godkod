"""
MCP Server for Construction Estimator

A production-ready FastMCP server implementation providing construction rate search,
cost calculation, and comparison capabilities via 5 specialized tools.

This server exposes the following tools:
- natural_search: Full-text search for construction rates in Russian
- quick_calculate: Auto-detecting cost calculator (by code or description)
- show_rate_details: Detailed resource breakdown for a rate
- compare_variants: Compare multiple rates for cost analysis
- find_similar_rates: Find alternative rates using similarity search

Author: Construction Estimator Team
Framework: FastMCP 2.x
Database: SQLite (data/processed/estimates.db)
"""

import json
import logging
import re
from typing import List, Dict, Any, Optional
from pathlib import Path

from fastmcp import FastMCP

from src.database.db_manager import DatabaseManager
from src.search.search_engine import SearchEngine
from src.search.cost_calculator import CostCalculator
from src.search.rate_comparator import RateComparator


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Initialize FastMCP server
mcp = FastMCP("Construction Estimator")


# Database and service initialization
DB_PATH = "data/processed/estimates.db"
logger.info(f"Initializing MCP server with database: {DB_PATH}")

# Verify database exists
if not Path(DB_PATH).exists():
    logger.error(f"Database file not found: {DB_PATH}")
    raise FileNotFoundError(f"Database file not found: {DB_PATH}")

# Initialize database manager and services at module level
db_manager = DatabaseManager(DB_PATH)
db_manager.connect()
logger.info("DatabaseManager connected successfully")

search_engine = SearchEngine(db_manager)
logger.info("SearchEngine initialized")

cost_calculator = CostCalculator(db_manager)
logger.info("CostCalculator initialized")

rate_comparator = RateComparator(DB_PATH)
logger.info("RateComparator initialized")

logger.info("All services initialized successfully")


# Utility functions
def safe_json_serialize(obj: Any) -> str:
    """
    Safely serialize objects to JSON, handling NaN, Infinity, and DataFrames.

    Args:
        obj: Object to serialize (dict, list, DataFrame, etc.)

    Returns:
        JSON string representation
    """
    import pandas as pd
    import numpy as np

    def clean_value(v):
        """Clean a single value, handling NaN and Infinity."""
        # Skip arrays/lists/dicts - they need recursive cleaning
        if isinstance(v, (list, dict, np.ndarray)):
            return v
        # Check for scalar NaN or Infinity
        try:
            if pd.isna(v) or (isinstance(v, float) and not np.isfinite(v)):
                return None
        except (TypeError, ValueError):
            # If pd.isna() fails (e.g., for some exotic types), just return the value
            pass
        return v

    # Convert DataFrame to list of dicts
    if isinstance(obj, pd.DataFrame):
        obj = obj.replace([np.nan, np.inf, -np.inf], None).to_dict(orient='records')

    # Convert dict values if needed
    if isinstance(obj, dict):
        obj = {k: clean_value(v) for k, v in obj.items()}

    # Convert list items if needed
    if isinstance(obj, list):
        obj = [{k: clean_value(v) for k, v in item.items()} if isinstance(item, dict) else item
               for item in obj]

    return json.dumps(obj, ensure_ascii=False, indent=2)


def format_cost(value: float) -> float:
    """Format cost value to 2 decimal places."""
    return round(value, 2)


def is_rate_code(identifier: str) -> bool:
    """
    Detect if identifier is a rate code or search query.

    Rate codes typically contain patterns like:
    - Numbers and hyphens: "10-05-001-01"
    - Alphanumeric with hyphens: "ГЭСНп81-01-001"

    Args:
        identifier: String to check

    Returns:
        True if looks like a rate code, False if looks like a search query
    """
    # Remove whitespace
    identifier = identifier.strip()

    # Check for patterns indicating rate code:
    # - Contains hyphens and numbers
    # - Starts with numbers or specific prefixes (ГЭСН, ФЕР, etc.)
    # - Does not contain multiple spaces (typical of search queries)

    # If contains multiple spaces, it's likely a search query
    if len(identifier.split()) > 2:
        return False

    # Check for typical rate code patterns
    rate_code_patterns = [
        r'^\d{2}-\d{2}-\d{3}-\d{2}$',  # Pattern like 10-05-001-01
        r'^[А-Яа-я]+\d{2}-\d{2}',       # Pattern like ГЭСНп81-01
        r'^\d+-\d+',                     # Any pattern starting with numbers and hyphen
    ]

    for pattern in rate_code_patterns:
        if re.match(pattern, identifier):
            return True

    # If contains only alphanumeric and hyphens (no spaces), likely a code
    if re.match(r'^[А-Яа-яA-Za-z0-9\-]+$', identifier) and '-' in identifier:
        return True

    return False


# MCP Tools
@mcp.tool()
def natural_search(query: str, unit_type: str = None, limit: int = 10) -> str:
    """Search construction rates by description in Russian.

    Performs full-text search on construction rates database using FTS5.
    Returns rates matching the search query with cost information.

    Args:
        query: Russian text query (e.g., "перегородки гипсокартон", "бетон монолитный")
        unit_type: Optional filter by unit of measurement (e.g., "м2", "м3", "т")
        limit: Maximum number of results to return (default: 10, max: 100)

    Returns:
        JSON string with list of matching rates containing:
        - rate_code: Rate identifier
        - rate_full_name: Full descriptive name
        - unit_measure_full: Full unit description
        - cost_per_unit: Cost per single unit
        - total_cost: Total cost for the rate
        - rank: Relevance score

    Example:
        >>> natural_search("перегородки гипсокартон", unit_type="м2", limit=5)
    """
    logger.info(f"Tool invoked: natural_search(query='{query}', unit_type={unit_type}, limit={limit})")

    try:
        # Validate inputs
        if not query or not query.strip():
            error_response = {
                "error": "Invalid input",
                "details": "Query cannot be empty"
            }
            logger.error(f"natural_search error: {error_response['details']}")
            return safe_json_serialize(error_response)

        # Cap limit at 100
        limit = min(max(1, limit), 100)

        # Build filters
        filters = {}
        if unit_type:
            filters['unit_type'] = unit_type.strip()

        # Execute search
        results = search_engine.search(query, filters=filters, limit=limit)

        # Format results for JSON output
        formatted_results = []
        for result in results:
            formatted_results.append({
                'rate_code': result['rate_code'],
                'rate_full_name': result['rate_full_name'],
                'unit_measure_full': result['unit_measure_full'],
                'cost_per_unit': format_cost(result['cost_per_unit']),
                'total_cost': format_cost(result['total_cost']),
                'rank': result['rank']
            })

        response = {
            "success": True,
            "count": len(formatted_results),
            "results": formatted_results
        }

        logger.info(f"natural_search completed: {len(formatted_results)} results found")
        return safe_json_serialize(response)

    except Exception as e:
        error_response = {
            "error": "Search failed",
            "details": str(e)
        }
        logger.error(f"natural_search error: {str(e)}", exc_info=True)
        return safe_json_serialize(error_response)


@mcp.tool()
def quick_calculate(rate_identifier: str, quantity: float) -> str:
    """Calculate cost for a rate code or search by description.

    Auto-detects whether the identifier is a rate code or a search query.
    If it's a search query, finds the best matching rate first, then calculates cost.

    Args:
        rate_identifier: Either:
            - Rate code (e.g., "10-05-001-01", "ГЭСНп81-01-001")
            - Russian description (e.g., "перегородки гипсокартон")
        quantity: Quantity to calculate cost for (must be > 0)

    Returns:
        JSON string with calculation result containing:
        - rate_info: Dict with rate_code, rate_full_name, unit_type
        - cost_per_unit: Cost per single unit
        - calculated_total: Total cost for specified quantity
        - materials: Materials cost
        - resources: Labor/machinery cost
        - quantity: The quantity used in calculation
        - search_used: Boolean indicating if search was performed

    Example:
        >>> quick_calculate("10-05-001-01", 150)
        >>> quick_calculate("перегородки гипсокартон", 100)
    """
    logger.info(f"Tool invoked: quick_calculate(rate_identifier='{rate_identifier}', quantity={quantity})")

    try:
        # Validate quantity
        if quantity <= 0:
            error_response = {
                "error": "Invalid input",
                "details": f"Quantity must be greater than 0, got: {quantity}"
            }
            logger.error(f"quick_calculate error: {error_response['details']}")
            return safe_json_serialize(error_response)

        # Validate identifier
        if not rate_identifier or not rate_identifier.strip():
            error_response = {
                "error": "Invalid input",
                "details": "Rate identifier cannot be empty"
            }
            logger.error(f"quick_calculate error: {error_response['details']}")
            return safe_json_serialize(error_response)

        rate_identifier = rate_identifier.strip()
        search_used = False
        rate_code = None

        # Auto-detect: is it a code or search query?
        if is_rate_code(rate_identifier):
            # Use directly as rate code
            rate_code = rate_identifier
            logger.info(f"Detected as rate code: {rate_code}")
        else:
            # Search for the rate first
            logger.info(f"Detected as search query: {rate_identifier}")
            search_results = search_engine.search(rate_identifier, limit=1)

            if not search_results:
                error_response = {
                    "error": "Rate not found",
                    "details": f"No rates found matching '{rate_identifier}'"
                }
                logger.error(f"quick_calculate error: {error_response['details']}")
                return safe_json_serialize(error_response)

            # Use the best match
            rate_code = search_results[0]['rate_code']
            search_used = True
            logger.info(f"Found best match: {rate_code}")

        # Calculate cost
        result = cost_calculator.calculate(rate_code, quantity)

        # Format response
        response = {
            "success": True,
            "search_used": search_used,
            "rate_info": result['rate_info'],
            "cost_per_unit": format_cost(result['cost_per_unit']),
            "calculated_total": format_cost(result['calculated_total']),
            "materials": format_cost(result['materials']),
            "resources": format_cost(result['resources']),
            "quantity": quantity
        }

        logger.info(f"quick_calculate completed: {rate_code} x {quantity} = {response['calculated_total']}")
        return safe_json_serialize(response)

    except ValueError as e:
        error_response = {
            "error": "Calculation failed",
            "details": str(e)
        }
        logger.error(f"quick_calculate error: {str(e)}")
        return safe_json_serialize(error_response)

    except Exception as e:
        error_response = {
            "error": "Unexpected error",
            "details": str(e)
        }
        logger.error(f"quick_calculate error: {str(e)}", exc_info=True)
        return safe_json_serialize(error_response)


@mcp.tool()
def show_rate_details(rate_code: str, quantity: float = 1.0) -> str:
    """Get detailed resource breakdown for a rate.

    Provides comprehensive breakdown of all resources (materials, labor, machinery)
    associated with the rate, with quantities and costs adjusted for specified quantity.

    Args:
        rate_code: Rate identifier (e.g., "10-05-001-01")
        quantity: Quantity for calculation (default: 1.0, must be > 0)

    Returns:
        JSON string with detailed breakdown containing:
        - rate_info: Dict with rate_code, rate_full_name, unit_type
        - total_cost: Total cost for specified quantity
        - cost_per_unit: Cost per single unit
        - materials: Total materials cost
        - resources: Total labor/machinery cost
        - quantity: The quantity used
        - breakdown: List of resource items with:
            - resource_code: Resource identifier
            - resource_name: Resource description
            - resource_type: Type (Material, Labor, etc.)
            - adjusted_quantity: Quantity for specified amount
            - unit: Unit of measurement
            - unit_cost: Cost per unit of resource
            - adjusted_cost: Total cost for resource

    Example:
        >>> show_rate_details("10-05-001-01", quantity=150)
    """
    logger.info(f"Tool invoked: show_rate_details(rate_code='{rate_code}', quantity={quantity})")

    try:
        # Validate inputs
        if not rate_code or not rate_code.strip():
            error_response = {
                "error": "Invalid input",
                "details": "Rate code cannot be empty"
            }
            logger.error(f"show_rate_details error: {error_response['details']}")
            return safe_json_serialize(error_response)

        if quantity <= 0:
            error_response = {
                "error": "Invalid input",
                "details": f"Quantity must be greater than 0, got: {quantity}"
            }
            logger.error(f"show_rate_details error: {error_response['details']}")
            return safe_json_serialize(error_response)

        # Get detailed breakdown
        result = cost_calculator.get_detailed_breakdown(rate_code.strip(), quantity)

        # Format response
        response = {
            "success": True,
            "rate_info": result['rate_info'],
            "total_cost": format_cost(result['calculated_total']),
            "cost_per_unit": format_cost(result['cost_per_unit']),
            "materials": format_cost(result['materials']),
            "resources": format_cost(result['resources']),
            "quantity": quantity,
            "breakdown": result['breakdown']
        }

        logger.info(f"show_rate_details completed: {rate_code} with {len(result['breakdown'])} resources")
        return safe_json_serialize(response)

    except ValueError as e:
        error_response = {
            "error": "Rate not found or invalid",
            "details": str(e)
        }
        logger.error(f"show_rate_details error: {str(e)}")
        return safe_json_serialize(error_response)

    except Exception as e:
        error_response = {
            "error": "Unexpected error",
            "details": str(e)
        }
        logger.error(f"show_rate_details error: {str(e)}", exc_info=True)
        return safe_json_serialize(error_response)


@mcp.tool()
def compare_variants(rate_codes: List[str], quantity: float) -> str:
    """Compare multiple rate variants for cost analysis.

    Compares multiple rates side-by-side, calculating costs for the specified
    quantity and showing differences from the cheapest option.

    Args:
        rate_codes: List of rate codes to compare (e.g., ["10-05-001-01", "10-06-037-02"])
        quantity: Quantity for comparison (must be > 0)

    Returns:
        JSON string with comparison table containing:
        - success: Boolean
        - count: Number of rates compared
        - comparison: List of rate comparisons (sorted by total cost), each with:
            - rate_code: Rate identifier
            - rate_full_name: Full descriptive name
            - unit_type: Unit of measurement
            - cost_per_unit: Cost for one unit
            - total_for_quantity: Total cost for specified quantity
            - materials_for_quantity: Materials cost
            - difference_from_cheapest: Cost difference from minimum (rubles)
            - difference_percent: Cost difference from minimum (percentage)

    Example:
        >>> compare_variants(["10-05-001-01", "10-06-037-02"], quantity=100)
    """
    logger.info(f"Tool invoked: compare_variants(rate_codes={rate_codes}, quantity={quantity})")

    try:
        # Validate inputs
        if not rate_codes or len(rate_codes) == 0:
            error_response = {
                "error": "Invalid input",
                "details": "rate_codes list cannot be empty"
            }
            logger.error(f"compare_variants error: {error_response['details']}")
            return safe_json_serialize(error_response)

        if quantity <= 0:
            error_response = {
                "error": "Invalid input",
                "details": f"Quantity must be greater than 0, got: {quantity}"
            }
            logger.error(f"compare_variants error: {error_response['details']}")
            return safe_json_serialize(error_response)

        # Perform comparison
        comparison_df = rate_comparator.compare(rate_codes, quantity)

        # Convert DataFrame to list of dicts
        comparison_results = comparison_df.to_dict(orient='records')

        # Format numeric values
        for item in comparison_results:
            for key in ['cost_per_unit', 'total_for_quantity', 'materials_for_quantity',
                       'difference_from_cheapest', 'difference_percent']:
                if key in item:
                    item[key] = format_cost(item[key])

        response = {
            "success": True,
            "count": len(comparison_results),
            "quantity": quantity,
            "comparison": comparison_results
        }

        logger.info(f"compare_variants completed: {len(comparison_results)} rates compared")
        return safe_json_serialize(response)

    except ValueError as e:
        error_response = {
            "error": "Comparison failed",
            "details": str(e)
        }
        logger.error(f"compare_variants error: {str(e)}")
        return safe_json_serialize(error_response)

    except Exception as e:
        error_response = {
            "error": "Unexpected error",
            "details": str(e)
        }
        logger.error(f"compare_variants error: {str(e)}", exc_info=True)
        return safe_json_serialize(error_response)


@mcp.tool()
def find_similar_rates(rate_code: str, max_results: int = 5) -> str:
    """Find alternative rates similar to the given rate.

    Uses full-text search to find rates with similar descriptions, useful for
    discovering alternative materials or methods.

    Args:
        rate_code: Rate identifier to find alternatives for (e.g., "10-05-001-01")
        max_results: Maximum number of alternatives to return (default: 5, max: 20)

    Returns:
        JSON string with similar rates containing:
        - success: Boolean
        - source_rate: Original rate code
        - count: Number of alternatives found
        - alternatives: List of similar rates (including source for comparison), each with:
            - rate_code: Rate identifier
            - rate_full_name: Full descriptive name
            - unit_type: Unit of measurement
            - cost_per_unit: Cost for one unit
            - total_for_quantity: Total cost (normalized to source quantity)
            - materials_for_quantity: Materials cost
            - difference_from_cheapest: Cost difference from minimum
            - difference_percent: Cost difference percentage

    Example:
        >>> find_similar_rates("10-05-001-01", max_results=5)
    """
    logger.info(f"Tool invoked: find_similar_rates(rate_code='{rate_code}', max_results={max_results})")

    try:
        # Validate inputs
        if not rate_code or not rate_code.strip():
            error_response = {
                "error": "Invalid input",
                "details": "Rate code cannot be empty"
            }
            logger.error(f"find_similar_rates error: {error_response['details']}")
            return safe_json_serialize(error_response)

        # Cap max_results at 20
        max_results = min(max(1, max_results), 20)

        # Find alternatives
        alternatives_df = rate_comparator.find_alternatives(rate_code.strip(), max_results=max_results)

        # Convert DataFrame to list of dicts
        alternatives_results = alternatives_df.to_dict(orient='records')

        # Format numeric values
        for item in alternatives_results:
            for key in ['cost_per_unit', 'total_for_quantity', 'materials_for_quantity',
                       'difference_from_cheapest', 'difference_percent']:
                if key in item:
                    item[key] = format_cost(item[key])

        response = {
            "success": True,
            "source_rate": rate_code.strip(),
            "count": len(alternatives_results),
            "alternatives": alternatives_results
        }

        logger.info(f"find_similar_rates completed: {len(alternatives_results)} alternatives found")
        return safe_json_serialize(response)

    except ValueError as e:
        error_response = {
            "error": "Rate not found or invalid",
            "details": str(e)
        }
        logger.error(f"find_similar_rates error: {str(e)}")
        return safe_json_serialize(error_response)

    except Exception as e:
        error_response = {
            "error": "Unexpected error",
            "details": str(e)
        }
        logger.error(f"find_similar_rates error: {str(e)}", exc_info=True)
        return safe_json_serialize(error_response)


# Server entry point
if __name__ == "__main__":
    logger.info("Starting MCP server for Construction Estimator...")
    logger.info(f"Server name: {mcp.name}")
    logger.info(f"Database: {DB_PATH}")
    logger.info(f"Registered tools: natural_search, quick_calculate, show_rate_details, compare_variants, find_similar_rates")

    # Start health check server in background (for Docker healthcheck)
    try:
        from health_server import start_health_server_background
        health_thread = start_health_server_background(port=8001, db_path=DB_PATH)
        logger.info("Health check server started on port 8001")
    except ImportError as e:
        logger.warning(f"Health server not available: {e}")
    except Exception as e:
        logger.warning(f"Failed to start health server: {e}")

    try:
        # Run the FastMCP server with SSE transport for HTTP connections
        # This allows N8N to connect externally via HTTP/SSE
        logger.info("Starting MCP server with SSE transport on 0.0.0.0:8000")
        mcp.run(transport="sse", host="0.0.0.0", port=8000)
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Server error: {str(e)}", exc_info=True)
        raise
    finally:
        # Cleanup database connection
        if db_manager.connection:
            db_manager.disconnect()
            logger.info("Database connection closed")
        logger.info("MCP server stopped")
