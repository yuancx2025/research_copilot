"""
Tests for tools/arxiv_tools.py - ArXiv research tools
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from tools.arxiv_tools import ArxivToolkit
from tools.base import SourceType


class TestArxivToolkit:
    """Test ArxivToolkit class"""
    
    def test_source_type(self):
        """Test that ArxivToolkit has correct source type"""
        config = Mock()
        toolkit = ArxivToolkit(config)
        
        assert toolkit.source_type == SourceType.ARXIV
    
    def test_is_always_available(self):
        """Test that ArXiv is always available"""
        config = Mock()
        toolkit = ArxivToolkit(config)
        
        assert toolkit.is_available() is True
    
    @patch('tools.arxiv_tools.arxiv')
    def test_search_arxiv(self, mock_arxiv):
        """Test ArXiv search functionality"""
        config = Mock()
        config.MAX_ARXIV_RESULTS = 10
        toolkit = ArxivToolkit(config)
        
        # Mock ArXiv client and results
        mock_paper = MagicMock()
        mock_paper.entry_id = "http://arxiv.org/abs/1234.5678"
        mock_paper.title = "Test Paper"
        mock_paper.authors = [MagicMock(name="John Doe"), MagicMock(name="Jane Smith")]
        mock_paper.summary = "This is a test abstract" * 100  # Long abstract
        mock_paper.published.strftime.return_value = "2024-01-01"
        mock_paper.pdf_url = "https://arxiv.org/pdf/1234.5678.pdf"
        mock_paper.categories = ["cs.AI", "cs.LG"]
        mock_paper.primary_category = "cs.AI"
        
        mock_client = MagicMock()
        mock_client.results.return_value = [mock_paper]
        mock_arxiv.Client.return_value = mock_client
        mock_arxiv.SortCriterion.Relevance = "relevance"
        
        results = toolkit._search_arxiv("machine learning", max_results=5)
        
        assert len(results) > 0
        assert results[0]["title"] == "Test Paper"
        assert "arxiv_id" in results[0]
        assert results[0]["source_type"] == "arxiv"
    
    @patch('tools.arxiv_tools.ArxivLoader')
    def test_get_paper_content(self, mock_loader):
        """Test getting full paper content"""
        config = Mock()
        toolkit = ArxivToolkit(config)
        
        # Mock document loader
        mock_doc = MagicMock()
        mock_doc.page_content = "Full paper content" * 1000
        mock_doc.metadata = {
            "Title": "Test Paper",
            "Authors": "John Doe, Jane Smith",
            "Published": "2024-01-01"
        }
        
        mock_loader_instance = MagicMock()
        mock_loader_instance.load.return_value = [mock_doc]
        mock_loader.return_value = mock_loader_instance
        
        result = toolkit._get_paper_content("1234.5678")
        
        assert "arxiv_id" in result
        assert result["title"] == "Test Paper"
        assert result["source_type"] == "arxiv"
        assert len(result["content"]) <= 20000  # Should be limited
    
    def test_get_paper_content_with_url(self):
        """Test getting paper content with full URL"""
        config = Mock()
        toolkit = ArxivToolkit(config)
        
        with patch('tools.arxiv_tools.ArxivLoader') as mock_loader:
            mock_doc = MagicMock()
            mock_doc.page_content = "Content"
            mock_doc.metadata = {"Title": "Test"}
            
            mock_loader_instance = MagicMock()
            mock_loader_instance.load.return_value = [mock_doc]
            mock_loader.return_value = mock_loader_instance
            
            result = toolkit._get_paper_content("https://arxiv.org/abs/1234.5678")
            
            # Should extract ID from URL
            assert "arxiv_id" in result
    
    def test_find_related_papers(self):
        """Test finding related papers"""
        config = Mock()
        config.MAX_ARXIV_RESULTS = 10
        toolkit = ArxivToolkit(config)
        
        with patch('tools.arxiv_tools.arxiv') as mock_arxiv:
            mock_paper = MagicMock()
            mock_paper.title = "Test Paper Title"
            mock_paper.primary_category = "cs.AI"
            
            mock_client = MagicMock()
            mock_client.results.return_value = [mock_paper]
            mock_arxiv.Client.return_value = mock_client
            
            # Mock the search method
            toolkit._search_arxiv = Mock(return_value=[
                {"arxiv_id": "1234.5678", "title": "Original"},
                {"arxiv_id": "1234.5679", "title": "Related 1"},
                {"arxiv_id": "1234.5680", "title": "Related 2"}
            ])
            
            results = toolkit._find_related_papers("1234.5678", max_results=2)
            
            # Should filter out original paper
            assert all(r.get("arxiv_id") != "1234.5678" for r in results)
    
    def test_create_tools(self):
        """Test that tools are created correctly"""
        config = Mock()
        toolkit = ArxivToolkit(config)
        
        tools = toolkit.create_tools()
        
        assert len(tools) == 3
        tool_names = [t.name for t in tools]
        assert "search_arxiv" in tool_names
        assert "get_arxiv_paper" in tool_names
        assert "find_related_papers" in tool_names
    
    def test_search_error_handling(self):
        """Test error handling in search"""
        config = Mock()
        toolkit = ArxivToolkit(config)
        
        with patch('tools.arxiv_tools.arxiv') as mock_arxiv:
            mock_arxiv.Client.side_effect = Exception("Connection failed")
            
            results = toolkit._search_arxiv("test")
            
            assert len(results) == 1
            assert "error" in results[0]

