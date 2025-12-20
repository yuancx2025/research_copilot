"""
Tests for rag/retriever.py - Enhanced retrieval with reranking
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from langchain_core.documents import Document

from rag.retriever import Retriever
from rag.reranker import Reranker


class TestRetriever:
    """Test Retriever class"""
    
    @pytest.fixture
    def mock_collection(self):
        """Create mock collection"""
        # Create a real Document object, not a MagicMock
        mock_doc = Document(
            page_content="Test content",
            metadata={"parent_id": "p1", "source": "test.pdf"}
        )
        
        collection = MagicMock()
        collection.similarity_search.return_value = [mock_doc]
        return collection
    
    @pytest.fixture
    def mock_parent_store(self):
        """Create mock parent store"""
        parent_store = MagicMock()
        parent_store.load_many.return_value = [
            {"content": "Full parent content", "parent_id": "p1", "metadata": {}}
        ]
        return parent_store
    
    @pytest.fixture
    def mock_reranker(self):
        """Create mock reranker"""
        reranker = MagicMock(spec=Reranker)
        reranker.is_available.return_value = True
        reranker.rerank.return_value = [
            (Document(page_content="Reranked content", metadata={}), 0.9)
        ]
        return reranker
    
    def test_retriever_initialization(self, mock_collection, mock_parent_store):
        """Test retriever initializes correctly"""
        retriever = Retriever(mock_collection, mock_parent_store)
        
        assert retriever.collection == mock_collection
        assert retriever.parent_store == mock_parent_store
        assert retriever.enable_reranking is False  # No reranker provided
    
    def test_retriever_with_reranker(self, mock_collection, mock_parent_store, mock_reranker):
        """Test retriever with reranker enabled"""
        retriever = Retriever(mock_collection, mock_parent_store, mock_reranker, enable_reranking=True)
        
        assert retriever.reranker == mock_reranker
        assert retriever.enable_reranking is True
    
    def test_retrieve_basic(self, mock_collection, mock_parent_store):
        """Test basic retrieval without reranking"""
        retriever = Retriever(mock_collection, mock_parent_store)
        
        results = retriever.retrieve("test query", k=5)
        
        assert len(results) == 1
        assert isinstance(results[0], Document)
        mock_collection.similarity_search.assert_called_once()
    
    def test_retrieve_with_reranking(self, mock_collection, mock_parent_store, mock_reranker):
        """Test retrieval with reranking enabled"""
        retriever = Retriever(mock_collection, mock_parent_store, mock_reranker, enable_reranking=True)
        
        results = retriever.retrieve_with_rerank("test query", k=5)
        
        assert len(results) > 0
        assert isinstance(results[0], tuple)
        assert isinstance(results[0][0], Document)
        assert isinstance(results[0][1], float)
        mock_reranker.rerank.assert_called_once()
    
    def test_retrieve_with_reranking_disabled(self, mock_collection, mock_parent_store, mock_reranker):
        """Test retrieval falls back when reranking disabled"""
        retriever = Retriever(mock_collection, mock_parent_store, mock_reranker, enable_reranking=False)
        
        results = retriever.retrieve_with_rerank("test query", k=5)
        
        # Should return documents with dummy scores
        assert len(results) > 0
        assert all(isinstance(r, tuple) for r in results)
        assert all(score == 1.0 for _, score in results)
        mock_reranker.rerank.assert_not_called()
    
    def test_retrieve_without_reranker(self, mock_collection, mock_parent_store):
        """Test retrieve_with_rerank falls back when no reranker"""
        retriever = Retriever(mock_collection, mock_parent_store)
        
        results = retriever.retrieve_with_rerank("test query", k=5)
        
        assert len(results) > 0
        assert all(score == 1.0 for _, score in results)
    
    def test_retrieve_parent_context(self, mock_collection, mock_parent_store):
        """Test retrieving parent context"""
        retriever = Retriever(mock_collection, mock_parent_store)
        
        results = retriever.retrieve_parent_context(["p1", "p2"])
        
        assert len(results) > 0
        assert isinstance(results[0], dict)
        mock_parent_store.load_many.assert_called_once_with(["p1", "p2"])
    
    def test_retrieve_parent_context_error(self, mock_collection, mock_parent_store):
        """Test error handling in parent context retrieval"""
        mock_parent_store.load_many.side_effect = Exception("Load failed")
        retriever = Retriever(mock_collection, mock_parent_store)
        
        results = retriever.retrieve_parent_context(["p1"])
        
        assert results == []
    
    def test_search_with_reranking(self, mock_collection, mock_parent_store, mock_reranker):
        """Test search method with reranking"""
        retriever = Retriever(mock_collection, mock_parent_store, mock_reranker, enable_reranking=True)
        
        results = retriever.search("test query", k=5, use_reranking=True)
        
        assert len(results) > 0
        assert isinstance(results[0], dict)
        assert "content" in results[0]
        assert "parent_id" in results[0]
        assert "source" in results[0]
        assert "source_type" in results[0]
    
    def test_search_without_reranking(self, mock_collection, mock_parent_store):
        """Test search method without reranking"""
        retriever = Retriever(mock_collection, mock_parent_store)
        
        results = retriever.search("test query", k=5, use_reranking=False)
        
        assert len(results) > 0
        assert isinstance(results[0], dict)
        mock_collection.similarity_search.assert_called_once()
    
    def test_retrieve_error_handling(self, mock_collection, mock_parent_store):
        """Test error handling in retrieval"""
        mock_collection.similarity_search.side_effect = Exception("Search failed")
        retriever = Retriever(mock_collection, mock_parent_store)
        
        results = retriever.retrieve("test query")
        
        assert results == []
    
    def test_retrieve_parameters(self, mock_collection, mock_parent_store):
        """Test retrieval with custom parameters"""
        retriever = Retriever(mock_collection, mock_parent_store)
        
        retriever.retrieve("test query", k=10, score_threshold=0.8, fetch_k=20)
        
        mock_collection.similarity_search.assert_called_once_with(
            "test query", k=20, score_threshold=0.8
        )
    
    def test_retrieve_with_rerank_parameters(self, mock_collection, mock_parent_store, mock_reranker):
        """Test retrieve_with_rerank with custom parameters"""
        retriever = Retriever(mock_collection, mock_parent_store, mock_reranker, enable_reranking=True)
        
        retriever.retrieve_with_rerank("test query", k=5, initial_k=15)
        
        # Should retrieve initial_k documents
        mock_collection.similarity_search.assert_called()
        call_kwargs = mock_collection.similarity_search.call_args[1]
        assert call_kwargs['k'] == 15

