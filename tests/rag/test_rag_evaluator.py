"""
Tests for rag/evaluator.py - RAG evaluation metrics
"""
import math

import pytest
from langchain_core.documents import Document

from rag.evaluator import RAGEvaluator


class TestRAGEvaluator:
    """Test RAGEvaluator class"""
    
    @pytest.fixture
    def evaluator(self):
        """Create evaluator instance"""
        return RAGEvaluator()
    
    @pytest.fixture
    def mock_documents(self):
        """Create mock documents"""
        return [
            Document(
                page_content="Document about machine learning",
                metadata={"parent_id": "doc1", "source": "ml.pdf"}
            ),
            Document(
                page_content="Python programming guide",
                metadata={"parent_id": "doc2", "source": "python.pdf"}
            ),
            Document(
                page_content="Deep learning tutorial",
                metadata={"parent_id": "doc3", "source": "dl.pdf"}
            ),
            Document(
                page_content="Data science basics",
                metadata={"parent_id": "doc4", "source": "ds.pdf"}
            ),
            Document(
                page_content="Web development",
                metadata={"parent_id": "doc5", "source": "web.pdf"}
            ),
        ]
    
    def test_hit_rate_at_k_perfect(self, evaluator, mock_documents):
        """Test hit rate when relevant doc is in top K"""
        relevant_ids = ["doc1"]
        k = 3
        
        hit_rate = evaluator.hit_rate_at_k(mock_documents, relevant_ids, k)
        
        assert hit_rate == 1.0
    
    def test_hit_rate_at_k_miss(self, evaluator, mock_documents):
        """Test hit rate when relevant doc is not in top K"""
        relevant_ids = ["doc5"]  # Last document
        k = 3
        
        hit_rate = evaluator.hit_rate_at_k(mock_documents, relevant_ids, k)
        
        assert hit_rate == 0.0
    
    def test_hit_rate_at_k_empty(self, evaluator, mock_documents):
        """Test hit rate with empty inputs"""
        assert evaluator.hit_rate_at_k([], [], 5) == 0.0
        assert evaluator.hit_rate_at_k(mock_documents, [], 5) == 0.0
        assert evaluator.hit_rate_at_k([], ["doc1"], 5) == 0.0
    
    def test_mrr_perfect(self, evaluator, mock_documents):
        """Test MRR when relevant doc is first"""
        relevant_ids = ["doc1"]
        
        mrr = evaluator.mrr(mock_documents, relevant_ids)
        
        assert mrr == 1.0
    
    def test_mrr_second_position(self, evaluator, mock_documents):
        """Test MRR when relevant doc is second"""
        relevant_ids = ["doc2"]
        
        mrr = evaluator.mrr(mock_documents, relevant_ids)
        
        assert mrr == 0.5  # 1 / 2
    
    def test_mrr_not_found(self, evaluator, mock_documents):
        """Test MRR when relevant doc not found"""
        relevant_ids = ["nonexistent"]
        
        mrr = evaluator.mrr(mock_documents, relevant_ids)
        
        assert mrr == 0.0
    
    def test_precision_at_k_perfect(self, evaluator, mock_documents):
        """Test precision when all top K are relevant"""
        relevant_ids = ["doc1", "doc2", "doc3"]
        k = 3
        
        precision = evaluator.precision_at_k(mock_documents, relevant_ids, k)
        
        assert precision == 1.0
    
    def test_precision_at_k_partial(self, evaluator, mock_documents):
        """Test precision when some top K are relevant"""
        relevant_ids = ["doc1", "doc3"]  # Only 2 out of top 3
        k = 3
        
        precision = evaluator.precision_at_k(mock_documents, relevant_ids, k)
        
        assert abs(precision - 2/3) < 0.001
    
    def test_precision_at_k_zero(self, evaluator, mock_documents):
        """Test precision when no relevant docs in top K"""
        relevant_ids = ["doc5"]
        k = 3
        
        precision = evaluator.precision_at_k(mock_documents, relevant_ids, k)
        
        assert precision == 0.0
    
    def test_recall_at_k_perfect(self, evaluator, mock_documents):
        """Test recall when all relevant docs are retrieved"""
        relevant_ids = ["doc1", "doc2"]
        k = 5  # Retrieve all
        
        recall = evaluator.recall_at_k(mock_documents, relevant_ids, k)
        
        assert recall == 1.0
    
    def test_recall_at_k_partial(self, evaluator, mock_documents):
        """Test recall when some relevant docs are retrieved"""
        relevant_ids = ["doc1", "doc2", "doc3", "doc4"]
        k = 2  # Only retrieve top 2
        
        recall = evaluator.recall_at_k(mock_documents, relevant_ids, k)
        
        assert abs(recall - 0.5) < 0.001  # 2 out of 4
    
    def test_recall_at_k_empty_relevant(self, evaluator, mock_documents):
        """Test recall with no relevant documents"""
        recall = evaluator.recall_at_k(mock_documents, [], k=5)
        
        assert recall == 0.0
    
    def test_evaluate_retrieval_comprehensive(self, evaluator, mock_documents):
        """Test comprehensive evaluation"""
        relevant_ids = ["doc1", "doc3"]
        k = 3
        
        metrics = evaluator.evaluate_retrieval("test query", mock_documents, relevant_ids, k)
        
        assert "hit_rate@k" in metrics
        assert "mrr" in metrics
        assert "precision@k" in metrics
        assert "recall@k" in metrics
        
        assert 0.0 <= metrics["hit_rate@k"] <= 1.0
        assert 0.0 <= metrics["mrr"] <= 1.0
        assert 0.0 <= metrics["precision@k"] <= 1.0
        assert 0.0 <= metrics["recall@k"] <= 1.0
    
    def test_compare_retrieval(self, evaluator):
        """Test comparison between two retrieval methods"""
        baseline_docs = [
            Document(page_content="doc1", metadata={"parent_id": "doc1"}),
            Document(page_content="doc2", metadata={"parent_id": "doc2"}),
            Document(page_content="doc3", metadata={"parent_id": "doc3"}),
        ]
        
        improved_docs = [
            Document(page_content="doc1", metadata={"parent_id": "doc1"}),
            Document(page_content="doc3", metadata={"parent_id": "doc3"}),
            Document(page_content="doc2", metadata={"parent_id": "doc2"}),
        ]
        
        relevant_ids = ["doc1", "doc3"]
        k = 2
        
        comparison = evaluator.compare_retrieval(baseline_docs, improved_docs, relevant_ids, k)
        
        assert "baseline" in comparison
        assert "improved" in comparison
        
        assert "hit_rate@k" in comparison["baseline"]
        assert "hit_rate@k" in comparison["improved"]
        assert "mrr" in comparison["baseline"]
        assert "mrr" in comparison["improved"]
    
    def test_chunks_of_one_parent_count_once_for_recall(self, evaluator):
        """Two retrieved children of the same relevant parent must not push recall above 1."""
        docs = [
            Document(page_content="a", metadata={"parent_id": "p1"}),
            Document(page_content="b", metadata={"parent_id": "p1"}),
            Document(page_content="c", metadata={"parent_id": "p9"}),
        ]
        metrics = evaluator.evaluate_retrieval("q", docs, ["p1"], k=3)
        assert metrics["recall@k"] == 1.0
        assert metrics["hit_rate@k"] == 1.0
        assert abs(metrics["precision@k"] - 2 / 3) < 1e-9  # two of three chunks are on target
        assert metrics["ndcg@k"] == 1.0

    def test_mrr_and_ndcg_rank_unique_documents(self, evaluator):
        docs = [
            Document(page_content="a", metadata={"parent_id": "p9"}),
            Document(page_content="b", metadata={"parent_id": "p9"}),
            Document(page_content="c", metadata={"parent_id": "p1"}),
        ]
        assert evaluator.mrr(docs, ["p1"]) == 0.5  # second unique document, third chunk
        assert abs(evaluator.ndcg_at_k(docs, ["p1"], k=3) - 1 / math.log2(3)) < 1e-9
        assert evaluator.ndcg_at_k(docs, ["p1"], k=2) == 0.0

    def test_ndcg_graded_relevance(self, evaluator, mock_documents):
        perfect = evaluator.ndcg_at_k(mock_documents, {"doc1": 2, "doc2": 1}, k=5)
        swapped = evaluator.ndcg_at_k(mock_documents, {"doc1": 1, "doc2": 2}, k=5)
        assert perfect == 1.0 and 0 < swapped < 1

    def test_custom_id_key(self):
        docs = [Document(page_content="a", metadata={"parent_id": "x_parent_0", "corpus_id": "42"})]
        assert RAGEvaluator(id_key="corpus_id").hit_rate_at_k(docs, ["42"], k=1) == 1.0

    def test_document_without_parent_id(self, evaluator):
        """Test evaluation with documents using source instead of parent_id"""
        docs = [
            Document(page_content="doc1", metadata={"source": "doc1"}),
            Document(page_content="doc2", metadata={"source": "doc2"}),
        ]
        
        relevant_ids = ["doc1"]
        
        hit_rate = evaluator.hit_rate_at_k(docs, relevant_ids, k=1)
        assert hit_rate == 1.0
        
        mrr = evaluator.mrr(docs, relevant_ids)
        assert mrr == 1.0

