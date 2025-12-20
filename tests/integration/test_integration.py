"""
Integration tests for tools with actual APIs.

These tests require API keys and will make real API calls.
Run with: pytest tests/test_integration.py -v -m integration

Set environment variables or create a .env file:
- GITHUB_TOKEN (optional, for higher rate limits)
- YOUTUBE_API_KEY (optional, for YouTube search)
- TAVILY_API_KEY (optional, for web search)
"""
import pytest
import os
from unittest.mock import Mock
from tools.base import SourceType
from tools.local_tools import LocalToolkit
from tools.arxiv_tools import ArxivToolkit
from tools.github_tools import GitHubToolkit
from tools.youtube_tools import YouTubeToolkit
from tools.web_tools import WebToolkit


@pytest.fixture
def integration_config():
    """Create config with API keys from environment."""
    config = Mock()
    
    # ArXiv - no key needed
    config.MAX_ARXIV_RESULTS = 5
    
    # GitHub - optional token
    config.GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", None)
    config.USE_GITHUB_MCP = False
    
    # YouTube - optional API key
    config.YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", None)
    
    # Web - optional Tavily key
    config.TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", None)
    config.USE_WEB_SEARCH_MCP = False
    config.MAX_WEB_RESULTS = 5
    
    # Enable all agents
    config.ENABLE_ARXIV_AGENT = True
    config.ENABLE_YOUTUBE_AGENT = True
    config.ENABLE_GITHUB_AGENT = True
    config.ENABLE_WEB_AGENT = True
    
    return config


@pytest.mark.integration
class TestArxivIntegration:
    """Integration tests for ArXiv tools with real API."""
    
    def test_search_arxiv_real(self, integration_config):
        """Test ArXiv search with real API."""
        toolkit = ArxivToolkit(integration_config)
        
        results = toolkit._search_arxiv("transformer neural network", max_results=3)
        
        assert len(results) > 0
        assert "error" not in results[0]
        assert "arxiv_id" in results[0]
        assert "title" in results[0]
        assert results[0]["source_type"] == "arxiv"
        print(f"\n✓ Found {len(results)} papers")
        print(f"  Example: {results[0]['title']}")
    
    def test_get_paper_content_real(self, integration_config):
        """Test getting paper content with real API."""
        toolkit = ArxivToolkit(integration_config)
        
        # Use a well-known paper ID
        result = toolkit._get_paper_content("1706.03762")  # Attention Is All You Need
        
        # PyMuPDF might not be installed, so allow for that error
        if "error" in result and "PyMuPDF" in result["error"]:
            pytest.skip("PyMuPDF not installed - install with: pip install pymupdf")
        
        assert "error" not in result
        assert "content" in result
        assert "arxiv_id" in result
        assert len(result["content"]) > 0
        print(f"\n✓ Retrieved paper: {result.get('title', 'Unknown')}")
    
    def test_find_related_papers_real(self, integration_config):
        """Test finding related papers with real API."""
        toolkit = ArxivToolkit(integration_config)
        
        results = toolkit._find_related_papers("1706.03762", max_results=3)
        
        assert len(results) > 0
        assert all("arxiv_id" in r for r in results)
        print(f"\n✓ Found {len(results)} related papers")


@pytest.mark.integration
class TestGitHubIntegration:
    """Integration tests for GitHub tools with real API."""
    
    def test_search_repositories_real(self, integration_config):
        """Test GitHub repository search with real API."""
        toolkit = GitHubToolkit(integration_config)
        
        results = toolkit._search_repositories("langchain", max_results=3)
        
        assert len(results) > 0
        assert "error" not in results[0]
        assert "full_name" in results[0]
        assert "url" in results[0]
        assert results[0]["source_type"] == "github"
        print(f"\n✓ Found {len(results)} repositories")
        print(f"  Example: {results[0]['full_name']}")
    
    def test_get_readme_real(self, integration_config):
        """Test getting README with real API."""
        toolkit = GitHubToolkit(integration_config)
        
        result = toolkit._get_readme("langchain-ai/langchain")
        
        assert "error" not in result
        assert "content" in result
        assert len(result["content"]) > 0
        print(f"\n✓ Retrieved README ({len(result['content'])} chars)")
    
    def test_get_file_content_real(self, integration_config):
        """Test getting file content with real API."""
        toolkit = GitHubToolkit(integration_config)
        
        result = toolkit._get_file_content(
            "langchain-ai/langchain",
            "langchain/__init__.py"
        )
        
        # File might not exist or path might be wrong, allow for 404
        if "error" in result and "404" in result["error"]:
            pytest.skip(f"File not found: {result.get('error', 'Unknown error')}")
        
        assert "error" not in result
        assert "content" in result
        assert "langchain" in result["content"].lower() or len(result["content"]) > 0
        print(f"\n✓ Retrieved file: {result['path']}")
    
    def test_get_repo_structure_real(self, integration_config):
        """Test getting repository structure with real API."""
        toolkit = GitHubToolkit(integration_config)
        
        result = toolkit._get_repo_structure("langchain-ai/langchain", "")
        
        assert "error" not in result
        assert "contents" in result
        assert len(result["contents"]) > 0
        print(f"\n✓ Retrieved structure with {len(result['contents'])} items")


@pytest.mark.integration
class TestYouTubeIntegration:
    """Integration tests for YouTube tools."""
    
    def test_get_transcript_real(self, integration_config):
        """Test getting YouTube transcript (no API key needed)."""
        toolkit = YouTubeToolkit(integration_config)
        
        # Use a well-known educational video
        video_id = "dQw4w9WgXcQ"  # Replace with a video that has transcripts
        result = toolkit._get_youtube_transcript(video_id)
        
        # May fail if video doesn't have transcripts, that's OK
        if "error" not in result:
            assert "transcript" in result
            assert len(result["transcript"]) > 0
            print(f"\n✓ Retrieved transcript ({len(result['transcript'])} chars)")
        else:
            print(f"\n⚠ Transcript not available: {result['error']}")
            pytest.skip("Video transcript not available")
    
    def test_search_youtube_with_api(self, integration_config):
        """Test YouTube search (requires API key)."""
        if not integration_config.YOUTUBE_API_KEY:
            pytest.skip("YOUTUBE_API_KEY not set")
        
        toolkit = YouTubeToolkit(integration_config)
        
        results = toolkit._search_youtube("python tutorial", max_results=3)
        
        if "error" not in results[0]:
            assert len(results) > 0
            assert "video_id" in results[0]
            assert "title" in results[0]
            print(f"\n✓ Found {len(results)} videos")
            print(f"  Example: {results[0]['title']}")
        else:
            print(f"\n⚠ Search failed: {results[0].get('error', 'Unknown error')}")


@pytest.mark.integration
class TestWebIntegration:
    """Integration tests for web tools."""
    
    def test_extract_webpage_real(self, integration_config):
        """Test extracting webpage content (no API key needed)."""
        toolkit = WebToolkit(integration_config)
        
        result = toolkit._extract_webpage_content("https://www.python.org")
        
        assert "error" not in result
        assert "content" in result
        assert len(result["content"]) > 0
        assert "python" in result["content"].lower()
        print(f"\n✓ Extracted {len(result['content'])} chars from webpage")
    
    def test_web_search_with_tavily(self, integration_config):
        """Test web search with Tavily API."""
        if not integration_config.TAVILY_API_KEY:
            pytest.skip("TAVILY_API_KEY not set")
        
        toolkit = WebToolkit(integration_config)
        
        results = toolkit._web_search("python programming", max_results=3)
        
        if "error" not in results[0]:
            assert len(results) > 0
            assert "title" in results[0]
            assert "url" in results[0]
            print(f"\n✓ Found {len(results)} web results")
            print(f"  Example: {results[0]['title']}")
        else:
            print(f"\n⚠ Search failed: {results[0].get('error', 'Unknown error')}")
    
    def test_search_documentation_real(self, integration_config):
        """Test searching documentation sites."""
        if not integration_config.TAVILY_API_KEY:
            pytest.skip("TAVILY_API_KEY not set")
        
        toolkit = WebToolkit(integration_config)
        
        results = toolkit._search_documentation("langchain", "agents")
        
        if results and "error" not in results[0]:
            assert len(results) > 0
            print(f"\n✓ Found {len(results)} documentation results")


@pytest.mark.integration
class TestToolRegistryIntegration:
    """Integration tests for tool registry with real APIs."""
    
    def test_registry_initialization(self, integration_config):
        """Test initializing registry with all toolkits."""
        from tools.registry import initialize_registry
        
        registry = initialize_registry(integration_config)
        
        available_sources = registry.list_available_sources()
        
        assert SourceType.LOCAL in available_sources
        assert SourceType.ARXIV in available_sources
        print(f"\n✓ Registry initialized with {len(available_sources)} sources")
        print(f"  Available: {[s.value for s in available_sources]}")
    
    def test_get_all_tools(self, integration_config):
        """Test getting all tools from registry."""
        from tools.registry import initialize_registry
        
        registry = initialize_registry(integration_config)
        
        tools = registry.get_all_tools()
        
        assert len(tools) > 0
        print(f"\n✓ Registry provides {len(tools)} tools")
        print(f"  Tool names: {[t.name for t in tools[:5]]}...")

