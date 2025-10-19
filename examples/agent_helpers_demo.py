"""
Demo Script for AI Agent Helper Functions

This script demonstrates how to use the agent_helpers module for
conversational interactions with the construction rates database.

Run this script to see formatted output examples for all 5 helper functions.
"""

from rich.console import Console
from src.utils.agent_helpers import (
    natural_search,
    quick_calculate,
    show_rate_details,
    compare_variants,
    find_similar_rates
)

console = Console()


def demo_natural_search():
    """Demonstrate natural language search."""
    console.print("\n[bold cyan]=== DEMO 1: Natural Language Search ===[/bold cyan]\n")

    query = "бетон монолитный"
    console.print(f"[yellow]Searching for:[/yellow] '{query}'")

    result = natural_search(query, limit=5)

    # Print formatted output
    console.print(result['formatted_text'])

    # Show metadata
    console.print(f"\n[dim]Found {result['query_info']['result_count']} results[/dim]")


def demo_quick_calculate():
    """Demonstrate quick cost calculation."""
    console.print("\n[bold cyan]=== DEMO 2: Quick Cost Calculation ===[/bold cyan]\n")

    # Demo 2a: Using description (auto-search)
    console.print("[yellow]Method 1: Using description (auto-search)[/yellow]")
    result = quick_calculate("перегородки гипсокартонные", 150)
    console.print(result['formatted_text'])

    # Demo 2b: Using rate code directly
    if result['rate_used']:
        console.print("\n[yellow]Method 2: Using rate code directly[/yellow]")
        result2 = quick_calculate(result['rate_used'], 200)
        console.print(result2['formatted_text'])


def demo_show_rate_details():
    """Demonstrate rate details display."""
    console.print("\n[bold cyan]=== DEMO 3: Show Rate Details ===[/bold cyan]\n")

    # First search to get a rate code
    search_result = natural_search("монтаж", limit=1)

    if search_result['results']:
        rate_code = search_result['results'][0]['rate_code']
        console.print(f"[yellow]Showing details for:[/yellow] {rate_code}\n")

        result = show_rate_details(rate_code)
        console.print(result['formatted_text'])


def demo_compare_variants():
    """Demonstrate variant comparison."""
    console.print("\n[bold cyan]=== DEMO 4: Compare Variants ===[/bold cyan]\n")

    descriptions = [
        "перегородки из гипсокартона однослойные",
        "перегородки из гипсокартона двухслойные"
    ]

    console.print("[yellow]Comparing:[/yellow]")
    for desc in descriptions:
        console.print(f"  • {desc}")

    result = compare_variants(descriptions, quantity=100)
    console.print("\n" + result['formatted_text'])


def demo_find_similar_rates():
    """Demonstrate finding similar/alternative rates."""
    console.print("\n[bold cyan]=== DEMO 5: Find Similar Rates ===[/bold cyan]\n")

    # Search for a rate first
    search_result = natural_search("бетон", limit=1)

    if search_result['results']:
        rate_code = search_result['results'][0]['rate_code']
        console.print(f"[yellow]Finding alternatives for:[/yellow] {rate_code}\n")

        result = find_similar_rates(rate_code, max_results=5)
        console.print(result['formatted_text'])


def main():
    """Run all demos."""
    console.print("[bold green]AI Agent Helper Functions - Demo Script[/bold green]")
    console.print("[dim]Demonstrating formatted output for conversational AI interfaces[/dim]\n")

    try:
        # Run each demo
        demo_natural_search()
        demo_quick_calculate()
        demo_show_rate_details()
        demo_compare_variants()
        demo_find_similar_rates()

        console.print("\n[bold green]✓ All demos completed successfully![/bold green]\n")

    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {str(e)}")
        console.print("\n[yellow]Note:[/yellow] Make sure the database exists at data/processed/estimates.db")
        console.print("Run the ETL pipeline first: python -m src.etl.build_database")


if __name__ == "__main__":
    main()
