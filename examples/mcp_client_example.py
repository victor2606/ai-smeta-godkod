"""
MCP Client Usage Examples

This file demonstrates how to use the Construction Estimator MCP server tools.
These examples show common workflows and use cases.

Note: This is a reference guide. Actual MCP client integration depends on your
MCP client implementation.
"""

import json


def example_1_simple_search():
    """Example 1: Simple text search for construction rates."""
    print("\n=== Example 1: Simple Search ===")

    # Search for gypsum board partitions
    result = natural_search("перегородки гипсокартон", limit=5)
    data = json.loads(result)

    print(f"Found {data['count']} results:")
    for i, rate in enumerate(data['results'][:3], 1):
        print(f"{i}. {rate['rate_code']}: {rate['rate_full_name']}")
        print(f"   Cost: {rate['cost_per_unit']} руб/{rate['unit_measure_full']}")


def example_2_filtered_search():
    """Example 2: Search with unit type filter."""
    print("\n=== Example 2: Filtered Search ===")

    # Search for concrete, filter by cubic meters
    result = natural_search("бетон монолитный", unit_type="м3", limit=10)
    data = json.loads(result)

    print(f"Found {data['count']} concrete rates (м3):")
    for rate in data['results'][:3]:
        print(f"- {rate['rate_code']}: {rate['cost_per_unit']} руб/м3")


def example_3_quick_calculate_by_code():
    """Example 3: Calculate cost using rate code."""
    print("\n=== Example 3: Calculate by Code ===")

    # Calculate cost for 150 m2 of partitions
    result = quick_calculate("10-05-001-01", 150)
    data = json.loads(result)

    if data['success']:
        print(f"Rate: {data['rate_info']['rate_full_name']}")
        print(f"Quantity: {data['quantity']} {data['rate_info']['unit_type']}")
        print(f"Cost per unit: {data['cost_per_unit']} руб")
        print(f"Total cost: {data['calculated_total']} руб")
        print(f"  - Materials: {data['materials']} руб")
        print(f"  - Labor/Machinery: {data['resources']} руб")


def example_4_quick_calculate_by_description():
    """Example 4: Calculate cost using description (auto-search)."""
    print("\n=== Example 4: Calculate by Description ===")

    # Automatic search + calculation
    result = quick_calculate("устройство перегородок из ГКЛ", 100)
    data = json.loads(result)

    if data['success']:
        print(f"Auto-detected rate: {data['rate_info']['rate_code']}")
        print(f"Search was used: {data['search_used']}")
        print(f"Total cost for 100 m2: {data['calculated_total']} руб")


def example_5_detailed_breakdown():
    """Example 5: Get detailed resource breakdown."""
    print("\n=== Example 5: Detailed Breakdown ===")

    # Get breakdown for 200 m2
    result = show_rate_details("10-05-001-01", quantity=200)
    data = json.loads(result)

    if data['success']:
        print(f"Rate: {data['rate_info']['rate_full_name']}")
        print(f"Total: {data['total_cost']} руб for {data['quantity']} м2\n")

        print("Resource breakdown:")
        for resource in data['breakdown'][:5]:  # Show first 5 resources
            print(f"- {resource['resource_name']}")
            print(f"  Type: {resource['resource_type']}")
            print(f"  Quantity: {resource['adjusted_quantity']} {resource['unit']}")
            print(f"  Cost: {resource['adjusted_cost']} руб")


def example_6_compare_multiple_rates():
    """Example 6: Compare multiple rate variants."""
    print("\n=== Example 6: Compare Variants ===")

    # Compare three partition types for 100 m2
    rate_codes = ["10-05-001-01", "10-06-037-02", "10-07-002-03"]
    result = compare_variants(rate_codes, quantity=100)
    data = json.loads(result)

    if data['success']:
        print(f"Comparing {data['count']} rates for {data['quantity']} m2:\n")

        for i, variant in enumerate(data['comparison'], 1):
            print(f"{i}. {variant['rate_code']}")
            print(f"   {variant['rate_full_name'][:60]}...")
            print(f"   Total: {variant['total_for_quantity']} руб")
            if variant['difference_percent'] > 0:
                print(f"   Difference: +{variant['difference_percent']}% "
                      f"(+{variant['difference_from_cheapest']} руб)")
            else:
                print(f"   ✓ Cheapest option")
            print()


def example_7_find_alternatives():
    """Example 7: Find similar rates."""
    print("\n=== Example 7: Find Alternatives ===")

    # Find alternatives to a specific rate
    result = find_similar_rates("10-05-001-01", max_results=5)
    data = json.loads(result)

    if data['success']:
        print(f"Source rate: {data['source_rate']}")
        print(f"Found {data['count']} alternatives:\n")

        for i, alt in enumerate(data['alternatives'], 1):
            marker = "★" if alt['rate_code'] == data['source_rate'] else " "
            print(f"{marker} {i}. {alt['rate_code']}")
            print(f"   {alt['rate_full_name'][:60]}...")
            print(f"   Cost: {alt['cost_per_unit']} руб/{alt['unit_type']}")
            print(f"   Difference: {alt['difference_percent']}%")
            print()


def example_8_complete_workflow():
    """Example 8: Complete workflow from search to comparison."""
    print("\n=== Example 8: Complete Workflow ===")

    # Step 1: Search for rates
    print("Step 1: Searching for partition rates...")
    search_result = natural_search("перегородки", limit=5)
    search_data = json.loads(search_result)

    # Step 2: Select top 3 rates for comparison
    top_3_codes = [r['rate_code'] for r in search_data['results'][:3]]
    print(f"Selected {len(top_3_codes)} rates for comparison")

    # Step 3: Compare rates
    print("\nStep 2: Comparing selected rates...")
    compare_result = compare_variants(top_3_codes, quantity=150)
    compare_data = json.loads(compare_result)

    # Step 4: Get cheapest option
    cheapest = compare_data['comparison'][0]
    print(f"\nCheapest option: {cheapest['rate_code']}")
    print(f"Cost: {cheapest['total_for_quantity']} руб for 150 m2")

    # Step 5: Get detailed breakdown for cheapest
    print("\nStep 3: Getting detailed breakdown...")
    details_result = show_rate_details(cheapest['rate_code'], quantity=150)
    details_data = json.loads(details_result)

    print(f"Total resources: {len(details_data['breakdown'])}")
    print(f"Materials: {details_data['materials']} руб")
    print(f"Labor/Machinery: {details_data['resources']} руб")

    # Step 6: Find alternatives
    print("\nStep 4: Finding alternatives...")
    alt_result = find_similar_rates(cheapest['rate_code'], max_results=3)
    alt_data = json.loads(alt_result)

    print(f"Found {alt_data['count']} similar rates")


def example_9_error_handling():
    """Example 9: Error handling."""
    print("\n=== Example 9: Error Handling ===")

    # Example 1: Invalid quantity
    result = quick_calculate("10-05-001-01", -10)
    data = json.loads(result)
    if 'error' in data:
        print(f"Error: {data['error']}")
        print(f"Details: {data['details']}")

    # Example 2: Rate not found
    result = quick_calculate("абракадабра", 100)
    data = json.loads(result)
    if 'error' in data:
        print(f"\nError: {data['error']}")
        print(f"Details: {data['details']}")


def example_10_cost_estimation_report():
    """Example 10: Generate cost estimation report."""
    print("\n=== Example 10: Cost Estimation Report ===")

    # Define items for estimation
    items = [
        {"description": "перегородки гипсокартон", "quantity": 150, "unit": "м2"},
        {"description": "бетон монолитный В25", "quantity": 50, "unit": "м3"},
        {"description": "штукатурка стен", "quantity": 300, "unit": "м2"}
    ]

    print("COST ESTIMATION REPORT")
    print("=" * 70)

    total_cost = 0

    for i, item in enumerate(items, 1):
        print(f"\n{i}. {item['description'].upper()}")

        # Calculate cost
        result = quick_calculate(item['description'], item['quantity'])
        data = json.loads(result)

        if data['success']:
            print(f"   Rate: {data['rate_info']['rate_code']}")
            print(f"   Quantity: {item['quantity']} {item['unit']}")
            print(f"   Unit cost: {data['cost_per_unit']} руб")
            print(f"   Subtotal: {data['calculated_total']} руб")

            total_cost += data['calculated_total']
        else:
            print(f"   ERROR: {data.get('details', 'Unknown error')}")

    print("\n" + "=" * 70)
    print(f"TOTAL ESTIMATE: {total_cost:,.2f} руб")


# Usage demonstration
if __name__ == "__main__":
    print("Construction Estimator MCP Server - Usage Examples")
    print("=" * 70)

    # Note: These examples assume the MCP server is running and tools are available
    # In actual use, you would call these through your MCP client

    examples = [
        ("Simple Search", example_1_simple_search),
        ("Filtered Search", example_2_filtered_search),
        ("Calculate by Code", example_3_quick_calculate_by_code),
        ("Calculate by Description", example_4_quick_calculate_by_description),
        ("Detailed Breakdown", example_5_detailed_breakdown),
        ("Compare Variants", example_6_compare_multiple_rates),
        ("Find Alternatives", example_7_find_alternatives),
        ("Complete Workflow", example_8_complete_workflow),
        ("Error Handling", example_9_error_handling),
        ("Cost Report", example_10_cost_estimation_report)
    ]

    print("\nAvailable examples:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"{i}. {name}")

    print("\nTo run an example, uncomment the function call below:")

    # Uncomment to run specific examples:
    # example_1_simple_search()
    # example_8_complete_workflow()
    # example_10_cost_estimation_report()
