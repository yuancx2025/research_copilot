"""
Tests for rag/reranker.py - LLM-based post-retrieval reranking
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from langchain_core.documents import Document
from langchain_core.messages import AIMessage

from rag.reranker import Reranker


class TestReranker:
    """Test LLM-based Reranker class"""
    
    @pytest.fixture
    def mock_llm(self):
        """Create mock LLM"""
        llm = MagicMock()
        return llm
    
    @pytest.fixture
    def mock_documents(self):
        """Create mock documents for testing"""
        return [
            Document(
                page_content="This is about machine learning and AI.",
                metadata={"source": "doc1", "parent_id": "p1", "source_type": "local"}
            ),
            Document(
                page_content="Python programming tutorial.",
                metadata={"source": "doc2", "parent_id": "p2", "source_type": "web"}
            ),
            Document(
                page_content="Deep learning neural networks.",
                metadata={"source": "doc3", "parent_id": "p3", "source_type": "arxiv"}
            ),
        ]
    
    def test_reranker_initialization(self, mock_llm):
        """Test reranker initializes correctly"""
        reranker = Reranker(llm=mock_llm, top_k=5, batch_size=3)
        
        assert reranker.llm == mock_llm
        assert reranker.top_k == 5
        assert reranker.batch_size == 3
    
    def test_reranker_initialization_defaults(self, mock_llm):
        """Test reranker initializes with default parameters"""
        reranker = Reranker(llm=mock_llm)
        
        assert reranker.top_k == 5
        assert reranker.batch_size == 5
    
    def test_is_available(self, mock_llm):
        """Test availability check"""
        reranker = Reranker(llm=mock_llm)
        assert reranker.is_available() is True
        
        reranker.llm = None
        assert reranker.is_available() is False
    
    def test_rerank_with_llm(self, mock_llm, mock_documents):
        """Test reranking with available LLM"""
        query = "machine learning"
        
        # Mock LLM response with JSON scores
        mock_response = MagicMock()
        mock_response.content = "[0.9, 0.3, 0.7]"
        mock_llm.invoke.return_value = mock_response
        
        reranker = Reranker(llm=mock_llm, top_k=2)
        results = reranker.rerank(query, mock_documents, top_k=2)
        
        assert len(results) == 2
        assert isinstance(results[0], tuple)
        assert isinstance(results[0][0], Document)
        assert isinstance(results[0][1], float)
        # First result should have highest score
        assert results[0][1] >= results[1][1]
        mock_llm.invoke.assert_called()
    
    def test_rerank_without_llm(self, mock_documents):
        """Test reranking falls back when LLM unavailable"""
        query = "machine learning"
        
        reranker = Reranker(llm=None)
        results = reranker.rerank(query, mock_documents, top_k=2)
        
        assert len(results) == 2
        # Should return documents with dummy scores
        assert all(score == 1.0 for _, score in results)
    
    def test_rerank_empty_documents(self, mock_llm):
        """Test reranking with empty document list"""
        query = "test query"
        
        reranker = Reranker(llm=mock_llm)
        results = reranker.rerank(query, [])
        
        assert results == []
    
    def test_rerank_error_handling(self, mock_llm, mock_documents):
        """Test error handling during reranking"""
        query = "test query"
        
        mock_llm.invoke.side_effect = Exception("LLM failed")
        
        reranker = Reranker(llm=mock_llm)
        results = reranker.rerank(query, mock_documents, top_k=2)
        
        # Should fall back to default scores
        assert len(results) == 2
        assert all(score == 0.5 for _, score in results)
    
    def test_rerank_custom_top_k(self, mock_llm, mock_documents):
        """Test reranking with custom top_k"""
        query = "test query"
        
        mock_response = MagicMock()
        mock_response.content = "[0.9, 0.8, 0.7]"
        mock_llm.invoke.return_value = mock_response
        
        reranker = Reranker(llm=mock_llm, top_k=5)
        results = reranker.rerank(query, mock_documents, top_k=1)
        
        assert len(results) == 1
    
    def test_rerank_scores_ordering(self, mock_llm, mock_documents):
        """Test that reranked results are ordered by score (descending)"""
        query = "test query"
        
        mock_response = MagicMock()
        mock_response.content = "[0.3, 0.9, 0.6]"
        mock_llm.invoke.return_value = mock_response
        
        reranker = Reranker(llm=mock_llm)
        results = reranker.rerank(query, mock_documents)
        
        # Verify descending order
        scores = [score for _, score in results]
        assert scores == sorted(scores, reverse=True)
    
    def test_rerank_batch_processing(self, mock_llm, mock_documents):
        """Test that documents are processed in batches"""
        query = "test query"
        
        # Create more documents than batch size
        many_docs = mock_documents * 3  # 9 documents
        
        mock_response = MagicMock()
        mock_response.content = "[0.9, 0.8, 0.7]"
        mock_llm.invoke.return_value = mock_response
        
        reranker = Reranker(llm=mock_llm, batch_size=3)
        results = reranker.rerank(query, many_docs, top_k=5)
        
        # Should process in batches (3 batches of 3 docs each)
        assert mock_llm.invoke.call_count == 3
        assert len(results) == 5
    
    def test_parse_scores_json_array(self, mock_llm):
        """Test parsing scores from JSON array"""
        reranker = Reranker(llm=mock_llm)
        
        # Test various JSON formats
        test_cases = [
            ("[0.9, 0.8, 0.7]", [0.9, 0.8, 0.7]),
            ("```json\n[0.9, 0.8, 0.7]\n```", [0.9, 0.8, 0.7]),
            ("Scores: [0.9, 0.8, 0.7]", [0.9, 0.8, 0.7]),
        ]
        
        for response, expected in test_cases:
            scores = reranker._parse_scores(response, 3)
            assert len(scores) == 3
            assert all(0.0 <= s <= 1.0 for s in scores)
    
    def test_parse_scores_fallback(self, mock_llm):
        """Test parsing falls back on invalid JSON"""
        reranker = Reranker(llm=mock_llm)
        
        scores = reranker._parse_scores("invalid json", 3)
        
        # Should return default scores
        assert len(scores) == 3
        assert all(s == 0.5 for s in scores)
    
    def test_parse_scores_normalization(self, mock_llm):
        """Test that scores are normalized to 0.0-1.0 range"""
        reranker = Reranker(llm=mock_llm)
        
        # Test scores outside range
        scores = reranker._parse_scores("[-1.0, 2.0, 0.5]", 3)
        
        assert scores[0] == 0.0  # Clamped to 0.0
        assert scores[1] == 1.0  # Clamped to 1.0
        assert scores[2] == 0.5
    
    def test_scoring_prompt_includes_source_type(self, mock_llm, mock_documents):
        """Test that scoring prompt includes source type information"""
        query = "test query"
        
        mock_response = MagicMock()
        mock_response.content = "[0.9, 0.8, 0.7]"
        mock_llm.invoke.return_value = mock_response
        
        reranker = Reranker(llm=mock_llm)
        reranker.rerank(query, mock_documents)
        
        # Check that prompt was created with source type info
        call_args = mock_llm.invoke.call_args[0][0]
        prompt_text = str(call_args)
        
        # Should include source type in prompt
        assert "Source Type" in prompt_text or "source_type" in prompt_text.lower()
