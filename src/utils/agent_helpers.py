"""
AI Agent Dialog Interaction Helper Functions

This module provides beautifully formatted wrapper functions for AI agent interactions
with the construction rates management system. All functions return structured data
with rich formatted text for optimal display in conversational interfaces.

Features:
- Natural language search with formatted results
- Quick cost calculations from descriptions or codes
- Detailed rate breakdowns with resource tables
- Multi-variant comparisons with savings analysis
- Alternative rate discovery
- Simple JSON-based query caching

Dependencies:
- rich: Terminal formatting and tables
- pandas: Data manipulation
- sqlite3: Database connectivity
"""

import logging
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from src.search.search_engine import SearchEngine
from src.search.cost_calculator import CostCalculator
from src.search.rate_comparator import RateComparator
from src.database.db_manager import DatabaseManager


# Configure logging
logger = logging.getLogger(__name__)

# Initialize Rich console
console = Console()

# Cache configuration
CACHE_DIR = Path("data/cache")
CACHE_FILE = CACHE_DIR / "query_cache.json"
CACHE_TTL_HOURS = 24


# ============================================================================
# Cache Management
# ============================================================================

def _load_cache() -> Dict[str, Any]:
    """Load query cache from JSON file."""
    try:
        if CACHE_FILE.exists():
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.warning(f"Failed to load cache: {e}")
        return {}


def _save_cache(cache: Dict[str, Any]) -> None:
    """Save query cache to JSON file."""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save cache: {e}")


def _get_cached(cache_key: str) -> Optional[Any]:
    """Get cached result if it exists and is not expired."""
    cache = _load_cache()

    if cache_key in cache:
        entry = cache[cache_key]
        cached_time = datetime.fromisoformat(entry['timestamp'])

        if datetime.now() - cached_time < timedelta(hours=CACHE_TTL_HOURS):
            logger.info(f"Cache hit for key: {cache_key[:50]}...")
            return entry['data']
        else:
            logger.debug(f"Cache expired for key: {cache_key[:50]}...")

    return None


def _set_cached(cache_key: str, data: Any) -> None:
    """Store result in cache with timestamp."""
    cache = _load_cache()
    cache[cache_key] = {
        'timestamp': datetime.now().isoformat(),
        'data': data
    }
    _save_cache(cache)
    logger.debug(f"Cached result for key: {cache_key[:50]}...")


def _is_rate_code(text: str) -> bool:
    """
    Determine if text looks like a rate code.

    Rate codes typically contain:
    - Cyrillic letters (Г, Э, С, Н, п)
    - Numbers
    - Hyphens

    Examples: "ГЭСНп81-01-001-01", "10-05-001-01"
    """
    # Check for patterns like: letters/digits followed by hyphens and more digits
    # Common prefixes: ГЭСН, ТСН, ФСС, ТСЦ, etc.
    pattern = r'^[А-Яа-яA-Za-z0-9]+[-\d]+$'
    return bool(re.match(pattern, text.strip()))


# ============================================================================
# Public API Functions
# ============================================================================

def natural_search(
    query: str,
    filters: Optional[Dict] = None,
    limit: int = 10,
    db_path: str = 'data/processed/estimates.db'
) -> Dict[str, Any]:
    """
    Perform natural language search on construction rates with beautiful formatting.

    This function wraps SearchEngine.search() and provides rich formatted output
    suitable for display in conversational interfaces. Results are cached for
    improved performance.

    Args:
        query: Russian text search query (e.g., "бетон монолитный")
        filters: Optional dict with filter criteria:
            - unit_type (str): Filter by unit type (e.g., "м3", "м2")
            - min_cost (float): Minimum total cost
            - max_cost (float): Maximum total cost
            - category (str): Filter by category code
        limit: Maximum number of results (default: 10, max: 100)
        db_path: Path to SQLite database (default: data/processed/estimates.db)

    Returns:
        Dict containing:
            - results: List[Dict] - Raw search results
            - formatted_text: str - Rich formatted table as string
            - query_info: Dict - Query metadata (query, filters, result_count)

    Raises:
        ValueError: If query is empty or invalid
        sqlite3.Error: If database query fails

    Examples:
        >>> result = natural_search("бетон монолитный", limit=5)
        >>> print(result['formatted_text'])
        >>>
        >>> # With filters
        >>> result = natural_search(
        ...     "устройство перегородок",
        ...     filters={"unit_type": "м2", "max_cost": 5000},
        ...     limit=10
        ... )
    """
    try:
        # Input validation
        if not query or not query.strip():
            error_msg = "Search query cannot be empty"
            logger.error(error_msg)
            return {
                'results': [],
                'formatted_text': f"[red]Error:[/red] {error_msg}",
                'query_info': {'error': error_msg}
            }

        # Cap limit
        limit = min(limit, 100)

        # Generate cache key
        cache_key = f"search:{query}:{json.dumps(filters, sort_keys=True)}:{limit}"

        # Check cache
        cached_result = _get_cached(cache_key)
        if cached_result is not None:
            return cached_result

        # Execute search
        logger.info(f"Executing natural search: '{query}' (limit: {limit})")

        with DatabaseManager(db_path) as db:
            search_engine = SearchEngine(db)
            results = search_engine.search(query, filters=filters, limit=limit)

        # Create Rich table
        table = Table(title=f"Search Results for: '{query}'", show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=4)
        table.add_column("Rate Code", style="cyan", width=20)
        table.add_column("Description", style="white", width=50)
        table.add_column("Unit", style="green", width=10)
        table.add_column("Cost/Unit", style="yellow", justify="right", width=12)
        table.add_column("Total Cost", style="bold yellow", justify="right", width=12)

        # Populate table
        for idx, rate in enumerate(results, start=1):
            table.add_row(
                str(idx),
                rate['rate_code'],
                rate['rate_full_name'][:50] + "..." if len(rate['rate_full_name']) > 50 else rate['rate_full_name'],
                rate['unit_measure_full'],
                f"{rate['cost_per_unit']:,.2f}",
                f"{rate['total_cost']:,.2f}"
            )

        # Render to string
        from io import StringIO
        string_buffer = StringIO()
        temp_console = Console(file=string_buffer, force_terminal=True, width=120)
        temp_console.print(table)
        formatted_text = string_buffer.getvalue()

        # Build result
        result = {
            'results': results,
            'formatted_text': formatted_text,
            'query_info': {
                'query': query,
                'filters': filters,
                'result_count': len(results),
                'limit': limit
            }
        }

        # Cache result
        _set_cached(cache_key, result)

        logger.info(f"Search completed: {len(results)} results found")
        return result

    except ValueError as e:
        error_msg = f"Validation error: {str(e)}"
        logger.error(error_msg)
        return {
            'results': [],
            'formatted_text': f"[red]Error:[/red] {error_msg}",
            'query_info': {'error': error_msg}
        }
    except Exception as e:
        error_msg = f"Search failed: {str(e)}"
        logger.error(error_msg)
        return {
            'results': [],
            'formatted_text': f"[red]Error:[/red] {error_msg}",
            'query_info': {'error': error_msg}
        }


def quick_calculate(
    rate_code_or_description: str,
    quantity: float,
    db_path: str = 'data/processed/estimates.db'
) -> Dict[str, Any]:
    """
    Calculate cost for a rate - auto-detects if input is code or description.

    Smart function that:
    - If input looks like a rate code → uses it directly
    - If input is a description → searches first, then calculates for top result

    Args:
        rate_code_or_description: Rate code (e.g., "ГЭСНп81-01-001-01") or
                                   description (e.g., "бетон монолитный")
        quantity: Quantity to calculate (must be > 0)
        db_path: Path to SQLite database (default: data/processed/estimates.db)

    Returns:
        Dict containing:
            - calculation: Dict - Cost calculation results
            - formatted_text: str - Rich formatted output
            - rate_used: str - Rate code that was used for calculation
            - search_performed: bool - Whether search was needed

    Examples:
        >>> # Using rate code
        >>> result = quick_calculate("ГЭСНп81-01-001-01", 150)
        >>> print(result['formatted_text'])
        >>>
        >>> # Using description (auto-search)
        >>> result = quick_calculate("бетон монолитный B25", 50)
        >>> print(f"Used rate: {result['rate_used']}")
    """
    try:
        # Validate quantity
        if quantity <= 0:
            error_msg = f"Quantity must be greater than 0, got: {quantity}"
            logger.error(error_msg)
            return {
                'calculation': {},
                'formatted_text': f"[red]Error:[/red] {error_msg}",
                'rate_used': '',
                'search_performed': False
            }

        rate_code = None
        search_performed = False

        # Determine if input is rate code or description
        if _is_rate_code(rate_code_or_description):
            rate_code = rate_code_or_description.strip()
            logger.info(f"Detected rate code: {rate_code}")
        else:
            # Perform search to find rate code
            logger.info(f"Searching for: '{rate_code_or_description}'")
            search_result = natural_search(rate_code_or_description, limit=1, db_path=db_path)

            if not search_result['results']:
                error_msg = f"No rates found for: '{rate_code_or_description}'"
                logger.error(error_msg)
                return {
                    'calculation': {},
                    'formatted_text': f"[red]Error:[/red] {error_msg}",
                    'rate_used': '',
                    'search_performed': True
                }

            rate_code = search_result['results'][0]['rate_code']
            search_performed = True
            logger.info(f"Found rate: {rate_code}")

        # Calculate cost
        with DatabaseManager(db_path) as db:
            calculator = CostCalculator(db)
            calculation = calculator.calculate(rate_code, quantity)

        # Format output
        rate_info = calculation['rate_info']

        # Create Rich panel with calculation details
        from io import StringIO
        string_buffer = StringIO()
        temp_console = Console(file=string_buffer, force_terminal=True, width=100)

        # Build formatted text
        output_lines = [
            f"[bold cyan]Rate:[/bold cyan] {rate_info['rate_code']}",
            f"[bold]Description:[/bold] {rate_info['rate_full_name']}",
            f"[bold]Unit Type:[/bold] {rate_info['unit_type']}",
            "",
            f"[bold yellow]Cost Breakdown:[/bold yellow]",
            f"  Cost per unit: {calculation['cost_per_unit']:,.2f} руб.",
            f"  Quantity: {quantity} {rate_info['unit_type']}",
            "",
            f"[bold green]Total Cost: {calculation['calculated_total']:,.2f} руб.[/bold green]",
            f"  Materials: {calculation['materials']:,.2f} руб.",
            f"  Resources (labor/machinery): {calculation['resources']:,.2f} руб.",
        ]

        if search_performed:
            output_lines.insert(0, f"[dim]Auto-search performed for: '{rate_code_or_description}'[/dim]")
            output_lines.insert(1, "")

        panel = Panel("\n".join(output_lines), title="Cost Calculation", border_style="green")
        temp_console.print(panel)
        formatted_text = string_buffer.getvalue()

        result = {
            'calculation': calculation,
            'formatted_text': formatted_text,
            'rate_used': rate_code,
            'search_performed': search_performed
        }

        logger.info(f"Calculation completed: {rate_code} x {quantity} = {calculation['calculated_total']}")
        return result

    except ValueError as e:
        error_msg = f"Validation error: {str(e)}"
        logger.error(error_msg)
        return {
            'calculation': {},
            'formatted_text': f"[red]Error:[/red] {error_msg}",
            'rate_used': '',
            'search_performed': False
        }
    except Exception as e:
        error_msg = f"Calculation failed: {str(e)}"
        logger.error(error_msg)
        return {
            'calculation': {},
            'formatted_text': f"[red]Error:[/red] {error_msg}",
            'rate_used': '',
            'search_performed': False
        }


def show_rate_details(
    rate_code: str,
    db_path: str = 'data/processed/estimates.db'
) -> Dict[str, Any]:
    """
    Get detailed information about a rate including resource breakdown.

    Displays rate information with a formatted table of all resources
    (materials, labor, machinery) associated with the rate.

    Args:
        rate_code: Rate identifier code (e.g., "ГЭСНп81-01-001-01")
        db_path: Path to SQLite database (default: data/processed/estimates.db)

    Returns:
        Dict containing:
            - rate: Dict - Rate information
            - resources: List[Dict] - Resource breakdown
            - formatted_text: str - Rich formatted output with tables

    Example:
        >>> details = show_rate_details("ГЭСНп81-01-001-01")
        >>> print(details['formatted_text'])
        >>> for resource in details['resources']:
        ...     print(f"{resource['resource_name']}: {resource['quantity']} {resource['unit']}")
    """
    try:
        # Validate input
        if not rate_code or not rate_code.strip():
            error_msg = "Rate code cannot be empty"
            logger.error(error_msg)
            return {
                'rate': {},
                'resources': [],
                'formatted_text': f"[red]Error:[/red] {error_msg}"
            }

        rate_code = rate_code.strip()

        # Get detailed breakdown (quantity=1 to show base values)
        with DatabaseManager(db_path) as db:
            calculator = CostCalculator(db)
            breakdown = calculator.get_detailed_breakdown(rate_code, 1.0)

        # Extract data
        rate_info = breakdown['rate_info']
        resources = breakdown['breakdown']

        # Format output
        from io import StringIO
        string_buffer = StringIO()
        temp_console = Console(file=string_buffer, force_terminal=True, width=120)

        # Rate header
        temp_console.print(Panel(
            f"[bold cyan]{rate_info['rate_code']}[/bold cyan]\n"
            f"{rate_info['rate_full_name']}\n\n"
            f"[bold]Unit:[/bold] {rate_info['unit_type']}\n"
            f"[bold]Total Cost:[/bold] {breakdown['base_cost']:,.2f} руб.\n"
            f"  Materials: {breakdown['materials']:,.2f} руб.\n"
            f"  Resources: {breakdown['resources']:,.2f} руб.",
            title="Rate Details",
            border_style="cyan"
        ))

        temp_console.print()

        # Resources table
        if resources:
            table = Table(title="Resource Breakdown", show_header=True, header_style="bold magenta")
            table.add_column("Code", style="cyan", width=15)
            table.add_column("Type", style="blue", width=12)
            table.add_column("Description", style="white", width=40)
            table.add_column("Quantity", style="yellow", justify="right", width=10)
            table.add_column("Unit", style="green", width=8)
            table.add_column("Unit Cost", style="yellow", justify="right", width=12)
            table.add_column("Total Cost", style="bold yellow", justify="right", width=12)

            for resource in resources:
                table.add_row(
                    resource['resource_code'],
                    resource['resource_type'],
                    resource['resource_name'][:40] + "..." if len(resource['resource_name']) > 40 else resource['resource_name'],
                    f"{resource['original_quantity']:.2f}",
                    resource['unit'],
                    f"{resource['unit_cost']:,.2f}",
                    f"{resource['adjusted_cost']:,.2f}"
                )

            temp_console.print(table)
        else:
            temp_console.print("[dim]No resources found for this rate[/dim]")

        formatted_text = string_buffer.getvalue()

        result = {
            'rate': rate_info,
            'resources': resources,
            'formatted_text': formatted_text
        }

        logger.info(f"Rate details retrieved: {rate_code} with {len(resources)} resources")
        return result

    except ValueError as e:
        error_msg = f"Rate not found: {str(e)}"
        logger.error(error_msg)
        return {
            'rate': {},
            'resources': [],
            'formatted_text': f"[red]Error:[/red] {error_msg}"
        }
    except Exception as e:
        error_msg = f"Failed to get rate details: {str(e)}"
        logger.error(error_msg)
        return {
            'rate': {},
            'resources': [],
            'formatted_text': f"[red]Error:[/red] {error_msg}"
        }


def compare_variants(
    descriptions: List[str],
    quantity: float,
    db_path: str = 'data/processed/estimates.db'
) -> Dict[str, Any]:
    """
    Compare multiple rate variants by searching and comparing costs.

    For each description:
    1. Searches to find the best matching rate
    2. Compares all found rates using RateComparator
    3. Shows comparison table with savings

    Args:
        descriptions: List of descriptions to search for
                     (e.g., ["бетон B25", "бетон B30", "бетон B35"])
        quantity: Quantity to calculate costs for (must be > 0)
        db_path: Path to SQLite database (default: data/processed/estimates.db)

    Returns:
        Dict containing:
            - comparison: pd.DataFrame - Comparison results
            - formatted_text: str - Rich formatted comparison table
            - rates_found: List[str] - Rate codes that were found and compared
            - search_results: Dict[str, str] - Mapping of description to rate_code

    Example:
        >>> result = compare_variants(
        ...     ["бетон монолитный B25", "бетон монолитный B30"],
        ...     quantity=100
        ... )
        >>> print(result['formatted_text'])
        >>> print(f"Best option saves: {result['comparison'].iloc[0]['difference_from_cheapest']:.2f} руб.")
    """
    try:
        # Validate inputs
        if not descriptions or len(descriptions) < 2:
            error_msg = "At least 2 descriptions required for comparison"
            logger.error(error_msg)
            return {
                'comparison': pd.DataFrame(),
                'formatted_text': f"[red]Error:[/red] {error_msg}",
                'rates_found': [],
                'search_results': {}
            }

        if quantity <= 0:
            error_msg = f"Quantity must be greater than 0, got: {quantity}"
            logger.error(error_msg)
            return {
                'comparison': pd.DataFrame(),
                'formatted_text': f"[red]Error:[/red] {error_msg}",
                'rates_found': [],
                'search_results': {}
            }

        # Search for each description
        logger.info(f"Searching for {len(descriptions)} variants")
        rate_codes = []
        search_results = {}

        for desc in descriptions:
            search_result = natural_search(desc, limit=1, db_path=db_path)

            if search_result['results']:
                rate_code = search_result['results'][0]['rate_code']
                rate_codes.append(rate_code)
                search_results[desc] = rate_code
                logger.info(f"Found '{desc}' -> {rate_code}")
            else:
                logger.warning(f"No results for: '{desc}'")

        if len(rate_codes) < 2:
            error_msg = f"Found only {len(rate_codes)} rates, need at least 2 for comparison"
            logger.error(error_msg)
            return {
                'comparison': pd.DataFrame(),
                'formatted_text': f"[red]Error:[/red] {error_msg}",
                'rates_found': rate_codes,
                'search_results': search_results
            }

        # Compare rates
        comparator = RateComparator(db_path)
        comparison_df = comparator.compare(rate_codes, quantity)

        # Format output
        from io import StringIO
        string_buffer = StringIO()
        temp_console = Console(file=string_buffer, force_terminal=True, width=140)

        # Search mapping info
        temp_console.print("[bold]Search Results:[/bold]")
        for desc, code in search_results.items():
            temp_console.print(f"  '{desc}' → {code}")
        temp_console.print()

        # Comparison table
        table = Table(
            title=f"Cost Comparison for {quantity} units",
            show_header=True,
            header_style="bold magenta"
        )
        table.add_column("Rank", style="dim", width=5)
        table.add_column("Rate Code", style="cyan", width=20)
        table.add_column("Description", style="white", width=45)
        table.add_column("Unit", style="green", width=8)
        table.add_column("Cost/Unit", style="yellow", justify="right", width=12)
        table.add_column("Total Cost", style="bold yellow", justify="right", width=14)
        table.add_column("Difference", style="red", justify="right", width=14)
        table.add_column("% Diff", style="red", justify="right", width=8)

        for idx, row in comparison_df.iterrows():
            # Highlight cheapest option
            style = "bold green" if idx == 0 else ""

            table.add_row(
                str(idx + 1),
                row['rate_code'],
                row['rate_full_name'][:45] + "..." if len(row['rate_full_name']) > 45 else row['rate_full_name'],
                row['unit_type'],
                f"{row['cost_per_unit']:,.2f}",
                f"{row['total_for_quantity']:,.2f}",
                f"+{row['difference_from_cheapest']:,.2f}" if row['difference_from_cheapest'] > 0 else "0.00",
                f"+{row['difference_percent']:.1f}%" if row['difference_percent'] > 0 else "—",
                style=style
            )

        temp_console.print(table)

        # Summary
        cheapest = comparison_df.iloc[0]
        most_expensive = comparison_df.iloc[-1]
        max_savings = most_expensive['difference_from_cheapest']

        temp_console.print()
        temp_console.print(Panel(
            f"[bold green]Best option:[/bold green] {cheapest['rate_code']}\n"
            f"[bold]Cost:[/bold] {cheapest['total_for_quantity']:,.2f} руб.\n\n"
            f"[bold yellow]Maximum savings:[/bold yellow] {max_savings:,.2f} руб. "
            f"({most_expensive['difference_percent']:.1f}%)",
            title="Summary",
            border_style="green"
        ))

        formatted_text = string_buffer.getvalue()

        result = {
            'comparison': comparison_df,
            'formatted_text': formatted_text,
            'rates_found': rate_codes,
            'search_results': search_results
        }

        logger.info(f"Comparison completed: {len(rate_codes)} rates compared")
        return result

    except Exception as e:
        error_msg = f"Comparison failed: {str(e)}"
        logger.error(error_msg)
        return {
            'comparison': pd.DataFrame(),
            'formatted_text': f"[red]Error:[/red] {error_msg}",
            'rates_found': [],
            'search_results': {}
        }


def find_similar_rates(
    rate_code: str,
    max_results: int = 5,
    db_path: str = 'data/processed/estimates.db'
) -> Dict[str, Any]:
    """
    Find alternative rates similar to the given rate.

    Uses RateComparator.find_alternatives() to discover similar rates
    based on full-text search similarity and provides formatted comparison.

    Args:
        rate_code: Source rate code to find alternatives for
        max_results: Maximum number of alternatives to return (default: 5)
        db_path: Path to SQLite database (default: data/processed/estimates.db)

    Returns:
        Dict containing:
            - alternatives: pd.DataFrame - Alternative rates comparison
            - formatted_text: str - Rich formatted alternatives table
            - source_rate: str - Original rate code
            - alternatives_count: int - Number of alternatives found

    Example:
        >>> result = find_similar_rates("ГЭСНп81-01-001-01", max_results=5)
        >>> print(result['formatted_text'])
        >>> print(f"Found {result['alternatives_count']} alternatives")
    """
    try:
        # Validate inputs
        if not rate_code or not rate_code.strip():
            error_msg = "Rate code cannot be empty"
            logger.error(error_msg)
            return {
                'alternatives': pd.DataFrame(),
                'formatted_text': f"[red]Error:[/red] {error_msg}",
                'source_rate': '',
                'alternatives_count': 0
            }

        if max_results <= 0:
            error_msg = f"max_results must be greater than 0, got: {max_results}"
            logger.error(error_msg)
            return {
                'alternatives': pd.DataFrame(),
                'formatted_text': f"[red]Error:[/red] {error_msg}",
                'source_rate': rate_code,
                'alternatives_count': 0
            }

        rate_code = rate_code.strip()

        # Find alternatives
        logger.info(f"Finding alternatives for: {rate_code}")
        comparator = RateComparator(db_path)
        alternatives_df = comparator.find_alternatives(rate_code, max_results=max_results)

        if alternatives_df.empty:
            error_msg = f"No alternatives found for rate: {rate_code}"
            logger.warning(error_msg)
            return {
                'alternatives': alternatives_df,
                'formatted_text': f"[yellow]Warning:[/yellow] {error_msg}",
                'source_rate': rate_code,
                'alternatives_count': 0
            }

        # Format output
        from io import StringIO
        string_buffer = StringIO()
        temp_console = Console(file=string_buffer, force_terminal=True, width=140)

        # Source rate is first row
        source_row = alternatives_df.iloc[0]

        temp_console.print(Panel(
            f"[bold cyan]Source Rate:[/bold cyan] {source_row['rate_code']}\n"
            f"{source_row['rate_full_name']}\n\n"
            f"[bold]Cost per unit:[/bold] {source_row['cost_per_unit']:,.2f} руб.\n"
            f"[bold]Total cost:[/bold] {source_row['total_for_quantity']:,.2f} руб.",
            title="Original Rate",
            border_style="cyan"
        ))

        temp_console.print()

        # Alternatives table
        alternatives_only = alternatives_df.iloc[1:]  # Skip source rate

        if not alternatives_only.empty:
            table = Table(
                title="Similar Alternatives",
                show_header=True,
                header_style="bold magenta"
            )
            table.add_column("Rank", style="dim", width=5)
            table.add_column("Rate Code", style="cyan", width=20)
            table.add_column("Description", style="white", width=45)
            table.add_column("Unit", style="green", width=8)
            table.add_column("Cost/Unit", style="yellow", justify="right", width=12)
            table.add_column("Total Cost", style="bold yellow", justify="right", width=14)
            table.add_column("Difference", style="red", justify="right", width=14)
            table.add_column("% Diff", style="red", justify="right", width=8)

            for idx, row in alternatives_only.iterrows():
                # Style based on cost difference
                style = "green" if row['difference_from_cheapest'] == 0 else ""

                diff_sign = "+" if row['difference_from_cheapest'] > 0 else ""

                table.add_row(
                    str(idx),
                    row['rate_code'],
                    row['rate_full_name'][:45] + "..." if len(row['rate_full_name']) > 45 else row['rate_full_name'],
                    row['unit_type'],
                    f"{row['cost_per_unit']:,.2f}",
                    f"{row['total_for_quantity']:,.2f}",
                    f"{diff_sign}{row['difference_from_cheapest']:,.2f}",
                    f"{diff_sign}{row['difference_percent']:.1f}%",
                    style=style
                )

            temp_console.print(table)

            # Summary
            cheapest = alternatives_df.iloc[0]
            best_alternative = alternatives_only.loc[alternatives_only['total_for_quantity'].idxmin()]

            if best_alternative['total_for_quantity'] < cheapest['total_for_quantity']:
                savings = cheapest['total_for_quantity'] - best_alternative['total_for_quantity']
                temp_console.print()
                temp_console.print(Panel(
                    f"[bold green]Better option found![/bold green]\n"
                    f"Rate: {best_alternative['rate_code']}\n"
                    f"Savings: {savings:,.2f} руб. ({abs(best_alternative['difference_percent']):.1f}%)",
                    title="Recommendation",
                    border_style="green"
                ))
        else:
            temp_console.print("[dim]No alternative rates found[/dim]")

        formatted_text = string_buffer.getvalue()

        result = {
            'alternatives': alternatives_df,
            'formatted_text': formatted_text,
            'source_rate': rate_code,
            'alternatives_count': len(alternatives_only)
        }

        logger.info(f"Found {len(alternatives_only)} alternatives for {rate_code}")
        return result

    except ValueError as e:
        error_msg = f"Validation error: {str(e)}"
        logger.error(error_msg)
        return {
            'alternatives': pd.DataFrame(),
            'formatted_text': f"[red]Error:[/red] {error_msg}",
            'source_rate': rate_code,
            'alternatives_count': 0
        }
    except Exception as e:
        error_msg = f"Failed to find alternatives: {str(e)}"
        logger.error(error_msg)
        return {
            'alternatives': pd.DataFrame(),
            'formatted_text': f"[red]Error:[/red] {error_msg}",
            'source_rate': rate_code,
            'alternatives_count': 0
        }
