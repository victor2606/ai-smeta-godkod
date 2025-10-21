# MCP Server Documentation

## Overview

The Construction Estimator MCP (Model Context Protocol) server provides AI agents with access to construction rate search, cost calculation, and comparison capabilities through a standardized interface built on the FastMCP 2.x framework.

## Architecture

### Technology Stack
- **Framework**: FastMCP 2.x
- **Transport**: SSE (Server-Sent Events)
- **Database**: SQLite (28,686 rates, 294,883 resources)
- **Language**: Python 3.8+

### Components
- **SearchEngine**: FTS5-powered full-text search
- **CostCalculator**: Rate cost calculation with resource breakdown
- **RateComparator**: Multi-rate comparison and similarity search
- **DatabaseManager**: Optimized SQLite connection management

## Installation

### Prerequisites
```bash
# Install dependencies
pip install -r requirements.txt
```

### Required Dependencies
- `fastmcp>=2.0.0` - FastMCP framework
- `pandas>=2.0.0` - Data manipulation
- `sqlite3` - Database (Python stdlib)

## Running the Server

### Start Server
```bash
python mcp_server.py
```

### Server Configuration
- **Database Path**: `data/processed/estimates.db`
- **Server Name**: "Construction Estimator"
- **Transport**: SSE (default)
- **Port**: Auto-configured by FastMCP

### Logging
Server uses Python's built-in logging with INFO level by default:
```
2025-10-21 10:30:00 - root - INFO - Initializing MCP server with database: data/processed/estimates.db
2025-10-21 10:30:01 - root - INFO - SearchEngine initialized
2025-10-21 10:30:01 - root - INFO - CostCalculator initialized
2025-10-21 10:30:01 - root - INFO - RateComparator initialized
```

## MCP Tools

### 1. natural_search

**Purpose**: Search construction rates by Russian description using full-text search.

**Parameters**:
- `query` (string, required): Russian text search query
  - Example: "перегородки гипсокартон"
  - Example: "бетон монолитный класс В25"
- `unit_type` (string, optional): Filter by unit of measurement
  - Example: "м2", "м3", "т"
- `limit` (integer, optional): Max results (default: 10, max: 100)

**Response Structure**:
```json
{
  "success": true,
  "count": 5,
  "results": [
    {
      "rate_code": "10-05-001-01",
      "rate_full_name": "Перегородки гипсокартонные...",
      "unit_measure_full": "100 м2",
      "cost_per_unit": 1383.20,
      "total_cost": 138320.18,
      "rank": -0.5234
    }
  ]
}
```

**Usage Example**:
```python
# Search for gypsum board partitions
result = natural_search("перегородки гипсокартон", limit=5)

# Search for concrete with unit filter
result = natural_search("бетон", unit_type="м3", limit=10)
```

**Error Responses**:
```json
{
  "error": "Invalid input",
  "details": "Query cannot be empty"
}
```

---

### 2. quick_calculate

**Purpose**: Calculate cost for a rate with auto-detection of code vs description.

**Parameters**:
- `rate_identifier` (string, required): Either rate code OR Russian description
  - Rate code example: "10-05-001-01"
  - Description example: "перегородки гипсокартон"
- `quantity` (float, required): Quantity to calculate (must be > 0)

**Auto-Detection Logic**:
The tool automatically detects whether the input is:
- **Rate Code**: Contains hyphens and numbers (e.g., "10-05-001-01")
- **Search Query**: Contains spaces or Cyrillic words (e.g., "перегородки")

**Response Structure**:
```json
{
  "success": true,
  "search_used": false,
  "rate_info": {
    "rate_code": "10-05-001-01",
    "rate_full_name": "Перегородки гипсокартонные...",
    "unit_type": "м2"
  },
  "cost_per_unit": 1383.20,
  "calculated_total": 207480.27,
  "materials": 150234.56,
  "resources": 57245.71,
  "quantity": 150.0
}
```

**Usage Examples**:
```python
# Direct calculation with rate code
result = quick_calculate("10-05-001-01", 150)

# Automatic search + calculation
result = quick_calculate("перегородки гипсокартон", 150)
```

**Error Responses**:
```json
{
  "error": "Invalid input",
  "details": "Quantity must be greater than 0, got: -10"
}
```

---

### 3. show_rate_details

**Purpose**: Get detailed resource breakdown for a rate.

**Parameters**:
- `rate_code` (string, required): Rate identifier
  - Example: "10-05-001-01"
- `quantity` (float, optional): Quantity for calculation (default: 1.0)

**Response Structure**:
```json
{
  "success": true,
  "rate_info": {
    "rate_code": "10-05-001-01",
    "rate_full_name": "Перегородки гипсокартонные...",
    "unit_type": "м2"
  },
  "total_cost": 207480.27,
  "cost_per_unit": 1383.20,
  "materials": 150234.56,
  "resources": 57245.71,
  "quantity": 150.0,
  "breakdown": [
    {
      "resource_code": "101-0001",
      "resource_name": "Листы гипсокартонные",
      "resource_type": "Материал",
      "original_quantity": 210.0,
      "adjusted_quantity": 315.0,
      "unit": "м2",
      "unit_cost": 450.50,
      "adjusted_cost": 141907.50
    }
  ]
}
```

**Usage Example**:
```python
# Get details for 150 m2
result = show_rate_details("10-05-001-01", quantity=150)

# Get base details (1 unit)
result = show_rate_details("10-05-001-01")
```

---

### 4. compare_variants

**Purpose**: Compare multiple rate variants for cost analysis.

**Parameters**:
- `rate_codes` (array of strings, required): List of rate codes to compare
  - Example: ["10-05-001-01", "10-06-037-02", "10-07-002-03"]
- `quantity` (float, required): Quantity for comparison

**Response Structure**:
```json
{
  "success": true,
  "count": 3,
  "quantity": 100.0,
  "comparison": [
    {
      "rate_code": "10-05-001-01",
      "rate_full_name": "Перегородки гипсокартонные...",
      "unit_type": "м2",
      "cost_per_unit": 1383.20,
      "total_for_quantity": 138320.00,
      "materials_for_quantity": 100156.37,
      "difference_from_cheapest": 0.0,
      "difference_percent": 0.0
    },
    {
      "rate_code": "10-06-037-02",
      "rate_full_name": "Перегородки двухслойные...",
      "unit_type": "м2",
      "cost_per_unit": 1971.24,
      "total_for_quantity": 197124.00,
      "materials_for_quantity": 145678.90,
      "difference_from_cheapest": 58804.00,
      "difference_percent": 42.51
    }
  ]
}
```

**Usage Example**:
```python
# Compare three partition types
result = compare_variants(
    ["10-05-001-01", "10-06-037-02", "10-07-002-03"],
    quantity=100
)
```

**Notes**:
- Results are sorted by `total_for_quantity` (ascending)
- Cheapest option has `difference_from_cheapest: 0.0`
- Differences calculated from minimum cost

---

### 5. find_similar_rates

**Purpose**: Find alternative rates using similarity search.

**Parameters**:
- `rate_code` (string, required): Source rate to find alternatives for
  - Example: "10-05-001-01"
- `max_results` (integer, optional): Max alternatives to return (default: 5, max: 20)

**Response Structure**:
```json
{
  "success": true,
  "source_rate": "10-05-001-01",
  "count": 6,
  "alternatives": [
    {
      "rate_code": "10-05-001-01",
      "rate_full_name": "Перегородки гипсокартонные...",
      "unit_type": "м2",
      "cost_per_unit": 1383.20,
      "total_for_quantity": 138320.00,
      "materials_for_quantity": 100156.37,
      "difference_from_cheapest": 0.0,
      "difference_percent": 0.0
    },
    {
      "rate_code": "10-05-002-01",
      "rate_full_name": "Перегородки гипсокартонные усиленные...",
      "unit_type": "м2",
      "cost_per_unit": 1520.45,
      "total_for_quantity": 152045.00,
      "materials_for_quantity": 110234.12,
      "difference_from_cheapest": 13725.00,
      "difference_percent": 9.92
    }
  ]
}
```

**Usage Example**:
```python
# Find 5 similar rates
result = find_similar_rates("10-05-001-01", max_results=5)
```

**Notes**:
- Source rate is included in results for comparison
- Uses FTS5 full-text search for similarity matching
- Results sorted by total cost
- Quantity normalized to source rate's unit_quantity

## Error Handling

All tools follow a consistent error response pattern:

### Error Response Structure
```json
{
  "error": "Error type",
  "details": "Detailed error message"
}
```

### Common Error Types

#### Invalid Input
```json
{
  "error": "Invalid input",
  "details": "Query cannot be empty"
}
```

#### Rate Not Found
```json
{
  "error": "Rate not found",
  "details": "No rates found matching 'абракадабра'"
}
```

#### Calculation Failed
```json
{
  "error": "Calculation failed",
  "details": "Rate code 'INVALID-999' not found in database"
}
```

#### Unexpected Error
```json
{
  "error": "Unexpected error",
  "details": "Database connection failed"
}
```

## Testing

### Run Test Suite
```bash
# Run all MCP server tests
pytest tests/test_mcp_server.py -v

# Run specific test class
pytest tests/test_mcp_server.py::TestNaturalSearch -v

# Run with coverage
pytest tests/test_mcp_server.py --cov=mcp_server --cov-report=html
```

### Test Coverage
- `TestNaturalSearch`: 6 tests covering search functionality
- `TestQuickCalculate`: 7 tests covering calculation and auto-detection
- `TestShowRateDetails`: 5 tests covering detailed breakdown
- `TestCompareVariants`: 5 tests covering multi-rate comparison
- `TestFindSimilarRates`: 5 tests covering similarity search
- `TestUtilityFunctions`: 3 tests covering helper functions
- `TestIntegrationScenarios`: 3 tests covering real-world workflows

Total: **34 comprehensive tests**

## Performance Considerations

### Database Optimization
- WAL mode enabled for better concurrency
- 64MB cache size for faster queries
- FTS5 indexes for full-text search

### Connection Management
- Single DatabaseManager instance (module-level)
- Connection pooling via context managers
- Automatic cleanup on server shutdown

### Response Size
- Default limits enforced (10-100 results)
- JSON serialization optimized for DataFrames
- Numeric values formatted to 2 decimal places

## Security Considerations

### Input Validation
- All inputs validated before database queries
- SQL injection prevented via parameterized queries
- Quantity bounds enforced (> 0)
- Limit caps enforced (max 100 for search, max 20 for alternatives)

### Database Access
- Read-only operations only (SELECT queries)
- No user-modifiable SQL
- Foreign key constraints enabled

## Troubleshooting

### Database Not Found
```
FileNotFoundError: Database file not found: data/processed/estimates.db
```
**Solution**: Ensure database exists at specified path or update `DB_PATH` constant.

### Import Errors
```
ModuleNotFoundError: No module named 'fastmcp'
```
**Solution**: Install dependencies with `pip install -r requirements.txt`

### Connection Errors
```
sqlite3.Error: unable to open database file
```
**Solution**: Check database file permissions and path validity.

### Empty Search Results
```json
{"success": true, "count": 0, "results": []}
```
**Solution**: Verify search query is in Russian and matches database content.

## Development

### Adding New Tools

1. Define tool function with `@mcp.tool()` decorator:
```python
@mcp.tool()
def my_new_tool(param1: str, param2: int) -> str:
    """Tool docstring (used by MCP for documentation)."""
    try:
        # Implementation
        result = {"success": True, "data": "..."}
        return safe_json_serialize(result)
    except Exception as e:
        error = {"error": "Error type", "details": str(e)}
        return safe_json_serialize(error)
```

2. Add comprehensive tests in `tests/test_mcp_server.py`

3. Update this documentation

### Code Style
- Follow PEP 8
- Use type hints for all parameters
- Comprehensive docstrings (Google style)
- Error handling in all tools
- Logging for debugging

## License

See project LICENSE file.

## Support

For issues, questions, or contributions, please refer to the main project repository.
