#!/usr/bin/env python3
"""
Test runner for the Sandbox Terminal MCP Server
"""

import sys
import unittest
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))


def run_tests(test_module=None, verbosity=2):
    """Run unit tests."""
    if test_module:
        # Run specific test module
        suite = unittest.TestLoader().loadTestsFromName(f"tests.{test_module}")
    else:
        # Discover and run all tests
        suite = unittest.TestLoader().discover("tests", pattern="test_*.py")
    
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    
    return result.wasSuccessful()


def main():
    parser = argparse.ArgumentParser(description="Run tests for Sandbox Terminal MCP Server")
    parser.add_argument(
        "module",
        nargs="?",
        help="Specific test module to run (e.g., test_session_store)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Increase verbosity"
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Decrease verbosity"
    )
    
    args = parser.parse_args()
    
    # Determine verbosity
    verbosity = 2
    if args.verbose:
        verbosity = 3
    elif args.quiet:
        verbosity = 1
    
    # Run tests
    success = run_tests(args.module, verbosity)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()