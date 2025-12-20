"""
Tests for tools/local_tools.py - Local document search tools
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from tools.local_tools import LocalToolkit
from tools.base import SourceType


class TestLocalToolkit:
    """Test LocalToolkit class"""
    
    def test_source_type(self):
        """Test that LocalToolkit has correct source type"""
        config = Mock()
        toolkit = LocalToolkit(config)
        
        assert toolkit.source_type == SourceType.LOCAL
    
    def test_is_always_available(self):
        """Test that local tools are always available"""
        config = Mock()
        toolkit = LocalToolkit(config)
        
        assert toolkit.is_available() is True
    
    def test_search_without_collection(self):
        """Test search when collection is not set"""
        config = Mock()
        toolkit = LocalToolkit(config)
        
        results = toolkit._search_child_chunks("test query")
        
        assert len(results) == 1
        assert "error" in results[0]
    
    def test_search_with_collection(self):
        """Test search with a mock collection"""
        config = Mock()
        toolkit = LocalToolkit(config)
        
        # Mock collection and search results
        mock_doc = MagicMock()
        mock_doc.page_content = "Test content"
        mock_doc.metadata = {
            "parent_id": "parent_1",
            "source": "test.pdf"
        }
        
        mock_collection = MagicMock()
        mock_collection.similarity_search.return_value = [mock_doc]
        
        toolkit.set_collection(mock_collection)
        
        results = toolkit._search_child_chunks("test query", k=5)
        
        assert len(results) == 1
        assert results[0]["content"] == "Test content"
        assert results[0]["source_type"] == "local"
        mock_collection.similarity_search.assert_called_once()
    
    def test_retrieve_parent_chunks(self):
        """Test retrieving parent chunks"""
        config = Mock()
        toolkit = LocalToolkit(config)
        
        # Mock parent store manager
        mock_chunks = [
            {
                "content": "Full parent content",
                "parent_id": "parent_1",
                "metadata": {"source": "test.pdf"}
            }
        ]
        
        toolkit.parent_store_manager.load_many = Mock(return_value=mock_chunks)
        
        results = toolkit._retrieve_parent_chunks(["parent_1"])
        
        assert len(results) == 1
        assert results[0]["content"] == "Full parent content"
        assert results[0]["source_type"] == "local"
    
    def test_create_tools(self):
        """Test that tools are created correctly"""
        config = Mock()
        toolkit = LocalToolkit(config)
        
        tools = toolkit.create_tools()
        
        assert len(tools) == 2
        assert tools[0].name == "search_local_documents"
        assert tools[1].name == "retrieve_document_context"
    
    def test_search_error_handling(self):
        """Test error handling in search"""
        config = Mock()
        toolkit = LocalToolkit(config)
        
        mock_collection = MagicMock()
        mock_collection.similarity_search.side_effect = Exception("Search failed")
        
        toolkit.set_collection(mock_collection)
        
        results = toolkit._search_child_chunks("test")
        
        assert len(results) == 1
        assert "error" in results[0]
    
    def test_retrieve_error_handling(self):
        """Test error handling in retrieval"""
        config = Mock()
        toolkit = LocalToolkit(config)
        
        toolkit.parent_store_manager.load_many = Mock(side_effect=Exception("Load failed"))
        
        results = toolkit._retrieve_parent_chunks(["parent_1"])
        
        assert len(results) == 1
        assert "error" in results[0]

