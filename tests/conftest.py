"""
Pytest configuration file for shared test fixtures and configurations
"""
import pytest
import sys
import os

# Add the parent directory to the Python path so we can import from backend
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing"""
    from unittest.mock import MagicMock
    return MagicMock()

@pytest.fixture
def sample_pdf_content():
    """Sample PDF content for testing"""
    return b"Mock PDF content for testing"

@pytest.fixture
def sample_text():
    """Sample text content for testing"""
    return "This is sample text content for testing purposes."

@pytest.fixture
def mock_database_connection():
    """Mock database connection for testing"""
    from unittest.mock import MagicMock
    return MagicMock() 