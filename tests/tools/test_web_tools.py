"""
Tests for tools/web_tools.py - Web search and extraction tools
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import requests
from bs4 import BeautifulSoup
from tools.web_tools import WebToolkit
from tools.base import SourceType


class TestWebToolkit:
    """Test WebToolkit class"""
    
    def test_source_type(self):
        """Test that WebToolkit has correct source type"""
        config = Mock()
        config.TAVILY_API_KEY = None
        config.USE_WEB_SEARCH_MCP = False
        toolkit = WebToolkit(config)
        
        assert toolkit.source_type == SourceType.WEB
    
    def test_is_available_without_config(self):
        """Test availability without API key or MCP"""
        config = Mock()
        config.TAVILY_API_KEY = None
        config.USE_WEB_SEARCH_MCP = False
        toolkit = WebToolkit(config)
        
        assert toolkit.is_available() is False
    
    def test_is_available_with_api_key(self):
        """Test availability with API key"""
        config = Mock()
        config.TAVILY_API_KEY = "test_key"
        config.USE_WEB_SEARCH_MCP = False
        config.MAX_WEB_RESULTS = 10
        
        with patch('tools.web_tools.TavilySearchResults') as mock_tavily:
            mock_tavily.return_value = MagicMock()
            toolkit = WebToolkit(config)
            assert toolkit.is_available() is True
    
    def test_web_search_without_api(self):
        """Test web search without API configured"""
        config = Mock()
        config.TAVILY_API_KEY = None
        config.USE_WEB_SEARCH_MCP = False
        toolkit = WebToolkit(config)
        
        results = toolkit._web_search("test query")
        
        assert len(results) == 1
        assert "error" in results[0]
    
    def test_web_search_with_api(self):
        """Test web search with Tavily API"""
        config = Mock()
        config.TAVILY_API_KEY = "test_key"
        config.USE_WEB_SEARCH_MCP = False
        config.MAX_WEB_RESULTS = 10
        
        with patch('langchain_community.tools.tavily_search.TavilySearchResults') as mock_tavily_class:
            mock_tavily_instance = MagicMock()
            mock_tavily_instance.invoke.return_value = [
                {
                    "title": "Test Article",
                    "url": "https://example.com/article",
                    "content": "This is test content",
                    "score": 0.9
                }
            ]
            mock_tavily_class.return_value = mock_tavily_instance
            
            toolkit = WebToolkit(config)
            results = toolkit._web_search("test query")
            
            assert len(results) > 0
            assert results[0]["title"] == "Test Article"
            assert results[0]["source_type"] == "web"
    
    @patch('tools.web_tools.requests.get')
    def test_extract_webpage_content(self, mock_get):
        """Test extracting webpage content"""
        config = Mock()
        config.TAVILY_API_KEY = None
        config.USE_WEB_SEARCH_MCP = False
        toolkit = WebToolkit(config)
        
        # Mock HTML response
        html_content = """
        <html>
            <head><title>Test Page</title></head>
            <body>
                <article>
                    <h1>Main Title</h1>
                    <p>This is the main content of the article.</p>
                </article>
            </body>
        </html>
        """
        
        mock_response = MagicMock()
        mock_response.content = html_content.encode()
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = toolkit._extract_webpage_content("https://example.com/article")
        
        assert "content" in result
        assert "Main Title" in result["content"]
        assert result["source_type"] == "web"
    
    @patch('tools.web_tools.requests.get')
    def test_extract_structured_content(self, mock_get):
        """Test extracting structured content"""
        config = Mock()
        config.TAVILY_API_KEY = None
        config.USE_WEB_SEARCH_MCP = False
        toolkit = WebToolkit(config)
        
        html_content = """
        <html>
            <head><title>Test Page</title></head>
            <body>
                <h1>Heading 1</h1>
                <h2>Heading 2</h2>
                <p>This is a paragraph with more than 50 characters to be included.</p>
                <code>print("Hello")</code>
            </body>
        </html>
        """
        
        mock_response = MagicMock()
        mock_response.content = html_content.encode()
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = toolkit._extract_webpage_content("https://example.com", extract_type="structured")
        
        assert "structured_content" in result
        assert "headings" in result["structured_content"]
        assert "paragraphs" in result["structured_content"]
    
    def test_search_documentation(self):
        """Test searching documentation sites"""
        config = Mock()
        config.TAVILY_API_KEY = "test_key"
        config.USE_WEB_SEARCH_MCP = False
        config.MAX_WEB_RESULTS = 10
        
        toolkit = WebToolkit(config)
        toolkit._web_search = Mock(return_value=[
            {"title": "LangChain Docs", "url": "https://python.langchain.com", "content": "test"}
        ])
        
        results = toolkit._search_documentation("langchain", "agents")
        
        assert len(results) > 0
        toolkit._web_search.assert_called_once()
    
    @patch('tools.web_tools.requests.get')
    def test_extract_code_from_url(self, mock_get):
        """Test extracting code from webpage"""
        config = Mock()
        config.TAVILY_API_KEY = None
        config.USE_WEB_SEARCH_MCP = False
        toolkit = WebToolkit(config)
        
        html_content = """
        <html>
            <body>
                <pre class="language-python"><code>def hello():
    print("Hello")</code></pre>
            </body>
        </html>
        """
        
        mock_response = MagicMock()
        mock_response.content = html_content.encode()
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = toolkit._extract_code_from_url("https://example.com/tutorial")
        
        assert "code_blocks" in result
        assert len(result["code_blocks"]) > 0
        assert result["code_blocks"][0]["language"] == "python"
    
    def test_create_tools(self):
        """Test that tools are created correctly"""
        config = Mock()
        config.TAVILY_API_KEY = "test_key"
        config.USE_WEB_SEARCH_MCP = False
        config.MAX_WEB_RESULTS = 10
        
        with patch('langchain_community.tools.tavily_search.TavilySearchResults') as mock_tavily:
            mock_tavily.return_value = MagicMock()
            toolkit = WebToolkit(config)
            tools = toolkit.create_tools()
            
            assert len(tools) == 4
            tool_names = [t.name for t in tools]
            assert "web_search" in tool_names
            assert "extract_webpage" in tool_names
            assert "search_docs" in tool_names
            assert "extract_code" in tool_names
    
    def test_error_handling(self):
        """Test error handling"""
        config = Mock()
        config.TAVILY_API_KEY = None
        config.USE_WEB_SEARCH_MCP = False
        toolkit = WebToolkit(config)
        
        with patch('tools.web_tools.requests.get') as mock_get:
            mock_get.side_effect = requests.exceptions.RequestException("Network error")
            
            result = toolkit._extract_webpage_content("https://example.com")
            
            assert "error" in result

