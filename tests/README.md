# Medical Study Backend Testing

This directory contains all the unit and integration tests for the backend of the Medical Study application. We use `pytest` as our testing framework.

## Simplified Test Execution

We've simplified the test execution process to make it easy to run tests and check for code coverage.

### Using the Unified Test Runner

The `run_tests.py` script is the primary entry point for all tests.

**Run all tests:**
```bash
python tests/run_tests.py
```

**Run a specific test file:**
```bash
python tests/run_tests.py tests/test_main.py
```

**Run tests with coverage:**
```bash
python tests/run_tests.py --coverage
```

**Generate an HTML coverage report:**
```bash
python tests/run_tests.py --html
```
The report will be located in `tests/htmlcov/index.html`.

**Set a minimum coverage threshold:**
```bash
python tests/run_tests.py --coverage --fail-under=95
```

### Using the Makefile

For even simpler execution, you can use the `Makefile` in the root directory.

**Run all tests:**
```bash
make test
```

**Run tests with a terminal coverage report (and fail if below 90%):**
```bash
make test-coverage
```

**Run tests and generate an HTML coverage report:**
```bash
make test-coverage-html
```

**Run a specific test file:**
```bash
make test-file FILE=tests/test_main.py
```

## Test Structure

- `test_*.py`: Individual test files for each backend module.
- `conftest.py`: Contains shared fixtures, hooks, and plugins for `pytest`.
- `pytest.ini`: Configuration file for `pytest`, where we define options like test paths and coverage settings.
- `run_tests.py`: The unified test runner script.
- `README.md`: This file.

## Goal: 100% Test Coverage

The goal is to achieve and maintain 100% test coverage for the backend. This ensures that all code is validated, reducing the likelihood of bugs and regressions. You can check the current coverage at any time by running `make test-coverage-html`.

## Structure

The test directory mirrors the structure of the `backend/` directory:

```
tests/
├── __init__.py                 # Makes tests a Python package
├── conftest.py                # Pytest configuration and shared fixtures
├── pytest.ini                # Pytest settings
├── run_tests.py              # Test runner script
├── README.md                 # This file
├── test_main.py              # Tests for backend/main.py
├── test_database.py          # Tests for backend/database.py
├── test_logic.py             # Tests for backend/logic.py
├── test_open_ai_calls.py     # Tests for backend/open_ai_calls.py
└── test_aws_ocr.py           # Tests for backend/aws_ocr.py
```

## Running Tests

### Using the test runner script

```bash
# Run all tests
python tests/run_tests.py

# Run tests for a specific module
python tests/run_tests.py main
python tests/run_tests.py database
python tests/run_tests.py logic
python tests/run_tests.py open_ai_calls
python tests/run_tests.py aws_ocr
```

### Using unittest directly

```bash
# Run all tests
python -m unittest discover -s tests -p "test_*.py" -v

# Run a specific test file
python -m unittest tests.test_main -v

# Run a specific test class
python -m unittest tests.test_main.TestMainRoutes -v

# Run a specific test method
python -m unittest tests.test_main.TestMainRoutes.test_placeholder -v
```

### Using pytest (if installed)

```bash
# Run all tests
pytest

# Run tests with verbose output
pytest -v

# Run tests for a specific file
pytest tests/test_main.py

# Run tests with specific markers
pytest -m unit
pytest -m "not slow"
```

## Writing Tests

Each test file follows this structure:

1. Import necessary modules and testing utilities
2. Add the parent directory to Python path to import backend modules
3. Define test classes that inherit from `unittest.TestCase`
4. Implement `setUp()` and `tearDown()` methods if needed
5. Write test methods starting with `test_`

### Example Test Method

```python
def test_example_function(self):
    """Test description"""
    # Arrange
    input_data = "test input"
    expected_output = "expected result"
    
    # Act
    result = function_to_test(input_data)
    
    # Assert
    self.assertEqual(result, expected_output)
```

## Test Fixtures

Common test fixtures are defined in `conftest.py` and can be used across all test files:

- `mock_openai_client`: Mock OpenAI client for testing AI calls
- `sample_pdf_content`: Sample PDF content for file processing tests
- `sample_text`: Sample text content for text processing tests
- `mock_database_connection`: Mock database connection for database tests

## Best Practices

1. **Test Isolation**: Each test should be independent and not rely on other tests
2. **Mocking**: Use mocks for external dependencies (databases, APIs, file systems)
3. **Clear Names**: Use descriptive test method names that explain what is being tested
4. **AAA Pattern**: Structure tests with Arrange, Act, Assert sections
5. **Edge Cases**: Test both happy path and edge cases/error conditions
6. **Documentation**: Include docstrings explaining what each test verifies 