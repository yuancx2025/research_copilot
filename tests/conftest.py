"""
Pytest configuration and fixtures
"""
import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture
def mock_config():
    """Create a mock config object"""
    from unittest.mock import Mock
    config = Mock()
    
    # Set default config values
    config.ENABLE_ARXIV_AGENT = True
    config.ENABLE_YOUTUBE_AGENT = True
    config.ENABLE_GITHUB_AGENT = True
    config.ENABLE_WEB_AGENT = True
    config.MAX_ARXIV_RESULTS = 10
    config.MAX_WEB_RESULTS = 10
    config.YOUTUBE_API_KEY = None
    config.GITHUB_TOKEN = None
    config.TAVILY_API_KEY = None
    config.USE_GITHUB_MCP = False
    config.USE_WEB_SEARCH_MCP = False
    
    return config


@pytest.fixture
def mock_collection():
    """Create a mock vector store collection"""
    from unittest.mock import MagicMock
    
    mock_doc = MagicMock()
    mock_doc.page_content = "Test document content"
    mock_doc.metadata = {
        "parent_id": "parent_1",
        "source": "test.pdf"
    }
    
    collection = MagicMock()
    collection.similarity_search.return_value = [mock_doc]
    
    return collection

