# MCP Server Quick Reference Card

## Server Start
```bash
python mcp_server.py
```

## Tool Reference

### 1️⃣ natural_search
**Purpose**: Search rates by Russian description
**Use Case**: Finding rates by keywords

```python
natural_search(
    query="перегородки гипсокартон",  # Required: search text
    unit_type="м2",                    # Optional: filter by unit
    limit=10                            # Optional: max results (default: 10, max: 100)
)
```

**Returns**: `{"success": true, "count": 5, "results": [...]}`

---

### 2️⃣ quick_calculate
**Purpose**: Calculate cost (auto-detects code vs query)
**Use Case**: Quick cost estimation

```python
# Option A: Direct with rate code
quick_calculate("10-05-001-01", 150)

# Option B: Search by description (auto)
quick_calculate("перегородки гипсокартон", 150)
```

**Returns**: `{"success": true, "calculated_total": 207480.27, ...}`

---

### 3️⃣ show_rate_details
**Purpose**: Detailed resource breakdown
**Use Case**: Understanding what's included in a rate

```python
show_rate_details(
    rate_code="10-05-001-01",  # Required: rate identifier
    quantity=150                # Optional: quantity (default: 1.0)
)
```

**Returns**: `{"success": true, "breakdown": [...], ...}`

---

### 4️⃣ compare_variants
**Purpose**: Compare multiple rates
**Use Case**: Choosing between options

```python
compare_variants(
    rate_codes=["10-05-001-01", "10-06-037-02"],  # Required: list of codes
    quantity=100                                   # Required: comparison quantity
)
```

**Returns**: `{"success": true, "comparison": [...], ...}`

---

### 5️⃣ find_similar_rates
**Purpose**: Find alternatives
**Use Case**: Discovering similar materials/methods

```python
find_similar_rates(
    rate_code="10-05-001-01",  # Required: source rate
    max_results=5               # Optional: max alternatives (default: 5, max: 20)
)
```

**Returns**: `{"success": true, "alternatives": [...], ...}`

---

## Common Workflows

### Workflow 1: Search → Calculate
```python
# 1. Search for rates
results = natural_search("перегородки", limit=5)

# 2. Calculate cost for first result
rate_code = results["results"][0]["rate_code"]
cost = quick_calculate(rate_code, 100)
```

### Workflow 2: Compare → Details
```python
# 1. Compare options
comparison = compare_variants(["10-05-001-01", "10-06-037-02"], 100)

# 2. Get details for cheapest
cheapest = comparison["comparison"][0]["rate_code"]
details = show_rate_details(cheapest, 100)
```

### Workflow 3: Search → Find Alternatives
```python
# 1. Find a rate
results = natural_search("бетон В25", limit=1)
rate_code = results["results"][0]["rate_code"]

# 2. Find alternatives
alternatives = find_similar_rates(rate_code, max_results=5)
```

---

## Error Response Format
```json
{
  "error": "Error type",
  "details": "Detailed message"
}
```

## Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Invalid input` | Empty query, negative quantity | Check input values |
| `Rate not found` | Non-existent code | Verify rate code exists |
| `Calculation failed` | Database error | Check database connection |

---

## Tips

### Search Tips
- Use Russian keywords: "перегородки", "бетон", "штукатурка"
- Filter by unit for precision: `unit_type="м2"`
- Start broad, then refine with filters

### Calculation Tips
- Use rate codes for exact rates
- Use descriptions for quick estimates
- Check `search_used` field to see if auto-detection occurred

### Comparison Tips
- Compare rates with same unit type
- Sort is automatic (cheapest first)
- Check `difference_percent` for quick decisions

### Performance Tips
- Limit search results to needed amount
- Use caching for repeated queries
- Batch comparisons when possible

---

## Database Info

- **Total Rates**: 28,686
- **Total Resources**: 294,883
- **Size**: ~313 MB
- **Language**: Russian
- **Categories**: Construction, renovation, finishing

---

## Quick Test
```bash
# Validate setup
python validate_mcp.py

# Run tests
pytest tests/test_mcp_server.py -v

# Run specific tool tests
pytest tests/test_mcp_server.py::TestNaturalSearch -v
```

---

## Help

- **Full Docs**: `docs/MCP_SERVER.md`
- **Examples**: `examples/mcp_client_example.py`
- **Tests**: `tests/test_mcp_server.py`
- **Summary**: `MCP_IMPLEMENTATION_SUMMARY.md`
