# AI Agent Helper Functions

Beautifully formatted wrapper functions for AI agent dialog interactions with the construction rates management system.

## Overview

The `agent_helpers.py` module provides 5 high-level functions designed for conversational AI interfaces. Each function returns structured data with rich formatted text output, perfect for display in chat interfaces or terminal applications.

## Features

- ✨ **Rich formatted output** using `rich` library for beautiful terminal displays
- 🔍 **Smart auto-detection** of rate codes vs. descriptions
- 💾 **Automatic caching** with 24-hour TTL for improved performance
- 🛡️ **Comprehensive error handling** with user-friendly messages
- 📊 **Detailed logging** for debugging and monitoring
- 🎯 **Type hints** and extensive docstrings

## Installation

Ensure you have the required dependencies:

```bash
pip install rich>=13.0.0 pandas>=2.0.0
```

## Quick Start

```python
from src.utils.agent_helpers import (
    natural_search,
    quick_calculate,
    show_rate_details,
    compare_variants,
    find_similar_rates
)

# Search for rates
result = natural_search("бетон монолитный", limit=5)
print(result['formatted_text'])

# Calculate costs
calc = quick_calculate("ГЭСНп81-01-001-01", quantity=150)
print(calc['formatted_text'])
```

## API Reference

### 1. `natural_search(query, filters=None, limit=10, db_path='...')`

Perform natural language search with formatted results table.

**Parameters:**
- `query` (str): Russian text search query
- `filters` (dict, optional): Filter criteria
  - `unit_type`: Filter by unit (e.g., "м3", "м2")
  - `min_cost`: Minimum cost threshold
  - `max_cost`: Maximum cost threshold
  - `category`: Filter by category code
- `limit` (int): Max results (default: 10, max: 100)
- `db_path` (str): Database path

**Returns:**
```python
{
    'results': List[Dict],  # Raw search results
    'formatted_text': str,  # Rich formatted table
    'query_info': {         # Query metadata
        'query': str,
        'filters': dict,
        'result_count': int,
        'limit': int
    }
}
```

**Example:**
```python
# Simple search
result = natural_search("бетон монолитный", limit=10)

# With filters
result = natural_search(
    "устройство перегородок",
    filters={"unit_type": "м2", "max_cost": 5000},
    limit=20
)

# Display results
print(result['formatted_text'])
```

---

### 2. `quick_calculate(rate_code_or_description, quantity, db_path='...')`

Calculate cost - auto-detects if input is rate code or description.

**Smart Detection:**
- Input looks like rate code → uses directly
- Input is description → searches first, then calculates

**Parameters:**
- `rate_code_or_description` (str): Rate code OR description
- `quantity` (float): Quantity to calculate (must be > 0)
- `db_path` (str): Database path

**Returns:**
```python
{
    'calculation': {        # Cost calculation results
        'rate_info': dict,
        'base_cost': float,
        'cost_per_unit': float,
        'calculated_total': float,
        'materials': float,
        'resources': float,
        'quantity': float
    },
    'formatted_text': str,  # Rich formatted panel
    'rate_used': str,       # Rate code used
    'search_performed': bool  # Whether search was needed
}
```

**Examples:**
```python
# Method 1: Using rate code directly
result = quick_calculate("ГЭСНп81-01-001-01", 150)

# Method 2: Using description (auto-search)
result = quick_calculate("бетон монолитный B25", 50)

# Both return same structure
print(result['formatted_text'])
print(f"Total: {result['calculation']['calculated_total']} руб.")
```

---

### 3. `show_rate_details(rate_code, db_path='...')`

Get detailed rate information with resource breakdown table.

**Parameters:**
- `rate_code` (str): Rate identifier
- `db_path` (str): Database path

**Returns:**
```python
{
    'rate': {               # Rate information
        'rate_code': str,
        'rate_full_name': str,
        'unit_type': str
    },
    'resources': List[{     # Resource breakdown
        'resource_code': str,
        'resource_type': str,
        'resource_name': str,
        'original_quantity': float,
        'unit': str,
        'unit_cost': float,
        'adjusted_cost': float
    }],
    'formatted_text': str   # Rich formatted output
}
```

**Example:**
```python
details = show_rate_details("ГЭСНп81-01-001-01")
print(details['formatted_text'])

# Access individual resources
for resource in details['resources']:
    print(f"{resource['resource_name']}: {resource['quantity']} {resource['unit']}")
```

---

### 4. `compare_variants(descriptions, quantity, db_path='...')`

Compare multiple rate variants by searching and comparing costs.

**Workflow:**
1. Searches for each description
2. Finds best matching rate for each
3. Compares all found rates
4. Shows savings analysis

**Parameters:**
- `descriptions` (List[str]): List of descriptions to compare (min 2)
- `quantity` (float): Quantity for cost calculation
- `db_path` (str): Database path

**Returns:**
```python
{
    'comparison': pd.DataFrame,  # Comparison results
    'formatted_text': str,       # Rich formatted table
    'rates_found': List[str],    # Rate codes found
    'search_results': {          # Description → rate_code mapping
        'description': 'rate_code'
    }
}
```

**Example:**
```python
result = compare_variants(
    [
        "бетон монолитный B25",
        "бетон монолитный B30",
        "бетон монолитный B35"
    ],
    quantity=100
)

print(result['formatted_text'])

# Access comparison data
df = result['comparison']
cheapest = df.iloc[0]
savings = df.iloc[-1]['difference_from_cheapest']
print(f"Maximum savings: {savings:.2f} руб.")
```

---

### 5. `find_similar_rates(rate_code, max_results=5, db_path='...')`

Find alternative rates similar to the given rate using FTS5 search.

**Parameters:**
- `rate_code` (str): Source rate code
- `max_results` (int): Max alternatives to return (default: 5)
- `db_path` (str): Database path

**Returns:**
```python
{
    'alternatives': pd.DataFrame,  # Alternative rates comparison
    'formatted_text': str,         # Rich formatted table
    'source_rate': str,            # Original rate code
    'alternatives_count': int      # Number of alternatives found
}
```

**Example:**
```python
result = find_similar_rates("ГЭСНп81-01-001-01", max_results=5)
print(result['formatted_text'])

# Check if better alternatives exist
alternatives = result['alternatives']
source_cost = alternatives.iloc[0]['total_for_quantity']
better_options = alternatives[alternatives['total_for_quantity'] < source_cost]

if not better_options.empty:
    best = better_options.iloc[0]
    savings = source_cost - best['total_for_quantity']
    print(f"Better option: {best['rate_code']} (save {savings:.2f} руб.)")
```

## Caching

All functions use automatic caching to improve performance:

- **Cache location:** `data/cache/query_cache.json`
- **TTL:** 24 hours
- **Cache key:** Based on function name, parameters, and values
- **Thread-safe:** Yes (JSON file-based)

To clear cache:
```python
from pathlib import Path
cache_file = Path("data/cache/query_cache.json")
if cache_file.exists():
    cache_file.unlink()
```

## Error Handling

All functions return structured error messages in the `formatted_text` field:

```python
result = natural_search("")  # Empty query

if 'error' in result['query_info']:
    print(f"Error: {result['query_info']['error']}")
    # Output: Error: Search query cannot be empty
```

Common error scenarios:
- Empty inputs
- Invalid quantities (≤ 0)
- Rate codes not found
- Database connection failures
- No search results

## Output Formatting

All functions return `formatted_text` using the `rich` library:

- **Tables:** Search results, comparisons, resource breakdowns
- **Panels:** Cost calculations, rate details, summaries
- **Colors:** Cyan (headers), Yellow (values), Red (errors), Green (success)
- **Styles:** Bold for emphasis, dim for metadata

**Rendering options:**

```python
from rich.console import Console

console = Console()
result = natural_search("бетон", limit=5)

# Print to terminal
console.print(result['formatted_text'])

# Save to HTML
console.save_html("output.html")

# Export as text (no colors)
from rich.console import Console
text_console = Console(file=open('output.txt', 'w'), legacy_windows=False)
text_console.print(result['formatted_text'])
```

## Usage Examples

See `/examples/agent_helpers_demo.py` for a complete demonstration of all functions.

Run the demo:
```bash
python3 examples/agent_helpers_demo.py
```

## Testing

Run the test suite:

```bash
# Run all unit tests
pytest tests/test_agent_helpers.py -v

# Run without integration tests
pytest tests/test_agent_helpers.py -v -m "not integration"

# Run with coverage
pytest tests/test_agent_helpers.py --cov=src.utils.agent_helpers
```

## Logging

Enable debug logging to see detailed execution flow:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
logging.getLogger('src.utils.agent_helpers').setLevel(logging.DEBUG)

result = natural_search("бетон", limit=5)
# Logs: Executing natural search: 'бетон' (limit: 5)
# Logs: Search completed: 45 results found
```

## Performance Tips

1. **Use caching:** First query is slow, subsequent queries are instant
2. **Limit results:** Use reasonable `limit` values (5-20 for most cases)
3. **Filter early:** Apply filters to reduce search space
4. **Batch operations:** Use `compare_variants` instead of multiple `quick_calculate` calls

## Integration Examples

### Flask API
```python
from flask import Flask, jsonify
from src.utils.agent_helpers import natural_search

app = Flask(__name__)

@app.route('/api/search/<query>')
def search(query):
    result = natural_search(query, limit=10)
    return jsonify({
        'results': result['results'],
        'count': result['query_info']['result_count']
    })
```

### Telegram Bot
```python
from telegram import Update
from telegram.ext import CommandHandler
from src.utils.agent_helpers import quick_calculate

async def calculate_handler(update: Update, context):
    # /calculate бетон B25 100
    args = context.args
    description = ' '.join(args[:-1])
    quantity = float(args[-1])

    result = quick_calculate(description, quantity)
    await update.message.reply_text(result['formatted_text'])
```

### OpenAI Function Calling
```python
functions = [
    {
        "name": "search_construction_rates",
        "description": "Search for construction rates by description",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 10}
            }
        }
    }
]

def handle_function_call(function_name, arguments):
    if function_name == "search_construction_rates":
        result = natural_search(**arguments)
        return result['formatted_text']
```

## Contributing

When adding new helper functions:

1. Follow the existing return structure pattern
2. Always return `formatted_text` with rich formatting
3. Add comprehensive error handling
4. Include docstring with examples
5. Write unit tests with mocks
6. Update this README

## License

Part of the n8npiplines-bim project.
