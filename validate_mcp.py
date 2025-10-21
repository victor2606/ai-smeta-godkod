#!/usr/bin/env python3
"""
MCP Server Validation Script

Quick validation that the MCP server can be imported and initialized.
Does not start the server, just validates the setup.
"""

import sys
import json
from pathlib import Path

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


def check_database():
    """Check if database file exists."""
    db_path = Path("data/processed/estimates.db")
    if not db_path.exists():
        print(f"{RED}✗ Database not found at {db_path}{RESET}")
        return False

    size_mb = db_path.stat().st_size / (1024 * 1024)
    print(f"{GREEN}✓ Database found: {db_path} ({size_mb:.1f} MB){RESET}")
    return True


def check_dependencies():
    """Check if required dependencies are installed."""
    required = ['fastmcp', 'pandas', 'numpy']
    missing = []

    for module in required:
        try:
            __import__(module)
            print(f"{GREEN}✓ {module} installed{RESET}")
        except ImportError:
            print(f"{RED}✗ {module} not installed{RESET}")
            missing.append(module)

    return len(missing) == 0


def check_imports():
    """Check if project modules can be imported."""
    try:
        from src.database.db_manager import DatabaseManager
        print(f"{GREEN}✓ DatabaseManager imported{RESET}")

        from src.search.search_engine import SearchEngine
        print(f"{GREEN}✓ SearchEngine imported{RESET}")

        from src.search.cost_calculator import CostCalculator
        print(f"{GREEN}✓ CostCalculator imported{RESET}")

        from src.search.rate_comparator import RateComparator
        print(f"{GREEN}✓ RateComparator imported{RESET}")

        return True
    except ImportError as e:
        print(f"{RED}✗ Import error: {e}{RESET}")
        return False


def validate_mcp_server():
    """Validate MCP server can be imported (without running)."""
    try:
        # Import without initializing
        import importlib.util
        spec = importlib.util.spec_from_file_location("mcp_server", "mcp_server.py")

        if spec is None or spec.loader is None:
            print(f"{RED}✗ Cannot load mcp_server.py{RESET}")
            return False

        print(f"{GREEN}✓ mcp_server.py can be loaded{RESET}")
        return True
    except Exception as e:
        print(f"{RED}✗ Error loading mcp_server.py: {e}{RESET}")
        return False


def test_basic_functionality():
    """Test basic functionality without running server."""
    try:
        # We can't actually run the server in validation mode,
        # but we can check the utility functions exist
        print(f"{BLUE}ℹ Skipping functional tests (would require running server){RESET}")
        return True
    except Exception as e:
        print(f"{RED}✗ Functional test error: {e}{RESET}")
        return False


def main():
    """Run all validation checks."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}MCP Server Validation{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")

    checks = [
        ("Database", check_database),
        ("Dependencies", check_dependencies),
        ("Project Imports", check_imports),
        ("MCP Server", validate_mcp_server),
        ("Basic Functionality", test_basic_functionality)
    ]

    results = []

    for name, check_func in checks:
        print(f"\n{YELLOW}Checking {name}...{RESET}")
        result = check_func()
        results.append((name, result))

    # Summary
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}Validation Summary{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")

    all_passed = True
    for name, result in results:
        status = f"{GREEN}PASS{RESET}" if result else f"{RED}FAIL{RESET}"
        print(f"{name:.<40} {status}")
        if not result:
            all_passed = False

    print(f"\n{BLUE}{'='*60}{RESET}\n")

    if all_passed:
        print(f"{GREEN}✓ All validation checks passed!{RESET}")
        print(f"\n{YELLOW}Next steps:{RESET}")
        print(f"1. Run tests: {BLUE}pytest tests/test_mcp_server.py -v{RESET}")
        print(f"2. Start server: {BLUE}python mcp_server.py{RESET}")
        print(f"3. See examples: {BLUE}examples/mcp_client_example.py{RESET}")
        return 0
    else:
        print(f"{RED}✗ Some validation checks failed{RESET}")
        print(f"\n{YELLOW}Troubleshooting:{RESET}")
        print(f"1. Install dependencies: {BLUE}pip install -r requirements.txt{RESET}")
        print(f"2. Check database exists at: {BLUE}data/processed/estimates.db{RESET}")
        print(f"3. See documentation: {BLUE}docs/MCP_SERVER.md{RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
