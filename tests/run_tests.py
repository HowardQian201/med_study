#!/usr/bin/env python3
"""
Unified Test Runner for Medical Study Backend

This script provides a single entry point for running tests with pytest,
generating coverage reports, and ensuring code quality.

Usage:
    python tests/run_tests.py [options] [test_path]

Arguments:
    test_path (optional): Specific test file or directory to run. 
                          Defaults to running all tests in 'tests/'.

Options:
    --coverage:      Run with coverage analysis.
    --html:          Generate HTML coverage report (implies --coverage).
    --fail-under N:  Fail if coverage is below N% (implies --coverage).
    -h, --help:      Show this help message.
"""

import sys
import os
from pathlib import Path

# Ensure the project root is in the Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    import pytest
    import coverage
except ImportError:
    print("Pytest and Coverage are required. Please install them:")
    print("pip install pytest pytest-cov coverage")
    sys.exit(1)


def main():
    """Main test runner function."""
    args = sys.argv[1:]
    pytest_args = []
    
    run_with_coverage = '--coverage' in args or '--html' in args or any(a.startswith('--fail-under') for a in args)

    if run_with_coverage:
        if '--coverage' in args:
            args.remove('--coverage')

        pytest_args.extend([
            "--cov=backend",
            "--cov-config=tests/pytest.ini",
            "--cov-report=term-missing"
        ])

        if '--html' in args:
            pytest_args.append("--cov-report=html:tests/htmlcov")
            args.remove('--html')
        
        fail_under_arg = next((a for a in args if a.startswith('--fail-under')), None)
        if fail_under_arg:
            pytest_args.append(f"--cov-{fail_under_arg.lstrip('-')}")
            args.remove(fail_under_arg)

    # Add remaining args to pytest
    pytest_args.extend(args)

    # Set default test path if not provided
    if not any(arg for arg in pytest_args if not arg.startswith('-')):
        pytest_args.append("tests/")

    print("="*60)
    print(f"🚀 Running pytest with arguments: {' '.join(pytest_args)}")
    print("="*60)

    # Change to project root to ensure consistent paths
    os.chdir(project_root)
    
    # Execute pytest
    exit_code = pytest.main(pytest_args)
    
    print("="*60)
    if exit_code == 0:
        print("✅ All tests passed!")
        if run_with_coverage and '--html' in sys.argv:
            html_path = project_root / "tests" / "htmlcov" / "index.html"
            print(f"📊 HTML Coverage Report: file://{html_path.absolute()}")
    else:
        print(f"❌ Tests failed with exit code: {exit_code}")
    print("="*60)
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main() 