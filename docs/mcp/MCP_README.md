# Construction Estimator MCP Server

A production-ready Model Context Protocol (MCP) server providing AI agents with access to Russian construction rate database with 28,686 rates and 294,883 resources.

## Features

- **Full-Text Search**: FTS5-powered Russian language search across construction rates
- **Cost Calculation**: Automatic cost calculation with detailed resource breakdown
- **Rate Comparison**: Multi-rate comparison with cost difference analysis
- **Smart Auto-Detection**: Automatically detects whether input is a rate code or search query
- **Similarity Search**: Find alternative rates using semantic similarity
- **Production-Ready**: Comprehensive error handling, logging, and testing

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Required packages:
- `fastmcp>=2.0.0` - FastMCP framework
- `pandas>=2.0.0` - Data manipulation
- Other dependencies listed in `requirements.txt`

### 2. Verify Database

Ensure the SQLite database exists:
```bash
ls -lh data/processed/estimates.db
```

Expected output: ~328MB database file

### 3. Start Server

```bash
python mcp_server.py
```

Expected output:
```
2025-10-21 10:30:00 - root - INFO - Initializing MCP server with database: data/processed/estimates.db
2025-10-21 10:30:01 - root - INFO - SearchEngine initialized
2025-10-21 10:30:01 - root - INFO - CostCalculator initialized
2025-10-21 10:30:01 - root - INFO - RateComparator initialized
2025-10-21 10:30:01 - root - INFO - Starting MCP server for Construction Estimator...
```

## Available Tools

### 1. `natural_search`
Search construction rates by Russian description.

**Example**:
```json
{
  "query": "перегородки гипсокартон",
  "unit_type": "м2",
  "limit": 5
}
```

### 2. `quick_calculate`
Calculate cost with auto-detection of code vs description.

**Example**:
```json
{
  "rate_identifier": "10-05-001-01",
  "quantity": 150
}
```

### 3. `show_rate_details`
Get detailed resource breakdown for a rate.

**Example**:
```json
{
  "rate_code": "10-05-001-01",
  "quantity": 150
}
```

### 4. `compare_variants`
Compare multiple rates side-by-side.

**Example**:
```json
{
  "rate_codes": ["10-05-001-01", "10-06-037-02"],
  "quantity": 100
}
```

### 5. `find_similar_rates`
Find alternative rates using similarity search.

**Example**:
```json
{
  "rate_code": "10-05-001-01",
  "max_results": 5
}
```

## Testing

Run the comprehensive test suite:

```bash
# Run all tests
pytest tests/test_mcp_server.py -v

# Run with coverage
pytest tests/test_mcp_server.py --cov=mcp_server --cov-report=html

# Run specific test class
pytest tests/test_mcp_server.py::TestNaturalSearch -v
```

**Test Coverage**: 34 comprehensive tests covering:
- ✓ Search functionality (6 tests)
- ✓ Cost calculation (7 tests)
- ✓ Detailed breakdown (5 tests)
- ✓ Rate comparison (5 tests)
- ✓ Similarity search (5 tests)
- ✓ Utility functions (3 tests)
- ✓ Integration workflows (3 tests)

## Documentation

- **Full Documentation**: [docs/MCP_SERVER.md](docs/MCP_SERVER.md)
- **Usage Examples**: [examples/mcp_client_example.py](examples/mcp_client_example.py)
- **API Reference**: See tool docstrings in `mcp_server.py`

## Architecture

```
mcp_server.py (FastMCP 2.x)
├── natural_search        → SearchEngine (FTS5)
├── quick_calculate       → CostCalculator + SearchEngine
├── show_rate_details     → CostCalculator (detailed)
├── compare_variants      → RateComparator
└── find_similar_rates    → RateComparator (FTS5)

Core Components:
├── DatabaseManager       → SQLite connection management
├── SearchEngine          → FTS5 full-text search
├── CostCalculator        → Rate cost calculation
└── RateComparator        → Multi-rate comparison
```

## Database Schema

**Rates Table** (28,686 rows):
- `rate_code`: Unique rate identifier
- `rate_full_name`: Full descriptive name
- `unit_type`, `unit_quantity`: Measurement units
- `total_cost`: Total rate cost
- `materials_cost`, `resources_cost`: Cost breakdown
- `search_text`: FTS5 indexed search field

**Resources Table** (294,883 rows):
- `resource_code`: Resource identifier
- `resource_name`: Resource description
- `resource_type`: Material/Labor/Machinery
- `quantity`, `unit`: Resource quantity and unit
- `unit_cost`, `total_cost`: Cost information

**FTS5 Index**: `rates_fts` for full-text search

## Performance

- **Database**: SQLite with WAL mode, 64MB cache
- **Search**: FTS5 index for sub-second queries
- **Response Size**: Limited to prevent memory issues (max 100 search results)
- **Connection**: Single persistent connection with automatic cleanup

## Error Handling

All tools return consistent JSON error responses:

```json
{
  "error": "Error type",
  "details": "Detailed error message"
}
```

Common errors:
- `Invalid input`: Empty query, negative quantity, etc.
- `Rate not found`: Non-existent rate code
- `Calculation failed`: Database or computation error
- `Unexpected error`: Unhandled exceptions

## Security

- **Read-Only**: All operations are SELECT queries only
- **SQL Injection Protection**: Parameterized queries throughout
- **Input Validation**: All inputs validated before processing
- **Bounds Enforcement**: Limits capped (max 100 results, max 20 alternatives)

## Troubleshooting

### Database Not Found
```
FileNotFoundError: Database file not found: data/processed/estimates.db
```
**Solution**: Ensure database exists or update `DB_PATH` in `mcp_server.py`

### Module Not Found
```
ModuleNotFoundError: No module named 'fastmcp'
```
**Solution**: Run `pip install -r requirements.txt`

### Empty Search Results
```json
{"success": true, "count": 0, "results": []}
```
**Solution**: Verify query is in Russian and matches database content

### Connection Errors
```
sqlite3.Error: unable to open database file
```
**Solution**: Check database permissions and path

## Development

### Adding New Tools

1. Add function with `@mcp.tool()` decorator
2. Follow existing error handling pattern
3. Use `safe_json_serialize()` for responses
4. Add comprehensive tests
5. Update documentation

### Code Style
- PEP 8 compliance
- Type hints for all parameters
- Google-style docstrings
- Comprehensive error handling
- INFO-level logging

## File Structure

```
/Users/vic/git/n8npiplines-bim/
├── mcp_server.py                    # Main MCP server (5 tools)
├── MCP_README.md                    # This file
├── requirements.txt                 # Python dependencies
├── data/
│   └── processed/
│       └── estimates.db             # SQLite database (328MB)
├── src/
│   ├── database/
│   │   └── db_manager.py           # Database connection manager
│   └── search/
│       ├── search_engine.py        # FTS5 search engine
│       ├── cost_calculator.py      # Cost calculation logic
│       └── rate_comparator.py      # Rate comparison logic
├── tests/
│   └── test_mcp_server.py          # MCP server test suite (34 tests)
├── docs/
│   └── MCP_SERVER.md               # Comprehensive documentation
└── examples/
    └── mcp_client_example.py       # Usage examples (10 scenarios)
```

## Database Statistics

- **Total Rates**: 28,686
- **Total Resources**: 294,883
- **Database Size**: 328MB
- **FTS5 Index**: Full-text search enabled
- **Data Coverage**: 89.3% of source Excel data
- **Categories**: Construction, renovation, finishing work

## Example Queries

### Search for partitions
```json
natural_search("перегородки гипсокартон", limit=5)
→ Returns 5 gypsum board partition rates
```

### Calculate cost for 150 m2
```json
quick_calculate("10-05-001-01", 150)
→ Returns total cost, materials, resources breakdown
```

### Compare 3 partition types
```json
compare_variants(["10-05-001-01", "10-06-037-02", "10-07-002-03"], 100)
→ Returns sorted comparison with cost differences
```

### Find alternatives
```json
find_similar_rates("10-05-001-01", max_results=5)
→ Returns 5 similar rates with source for comparison
```

## Support

For issues, questions, or contributions:
1. Check [docs/MCP_SERVER.md](docs/MCP_SERVER.md) for detailed documentation
2. Review [examples/mcp_client_example.py](examples/mcp_client_example.py) for usage patterns
3. Run tests to verify setup: `pytest tests/test_mcp_server.py -v`

## License

See project LICENSE file.

---

**Built with FastMCP 2.x** | **Database: SQLite 3** | **Python 3.8+**
