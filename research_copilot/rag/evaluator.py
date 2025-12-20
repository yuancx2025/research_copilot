from typing import List, Dict, Optional, Tuple
from langchain_core.documents import Document


class RAGEvaluator:
    """
    Evaluation framework for RAG system performance.
    
    Provides metrics for retrieval quality and answer accuracy.
    """
    
    def __init__(self):
        """Initialize evaluator."""
        pass
    
    def hit_rate_at_k(self, retrieved_docs: List[Document], relevant_doc_ids: List[str], k: int = 5) -> float:
        """
        Calculate Hit Rate @ K.
        
        Hit Rate @ K = 1 if at least one relevant document is in top K, else 0.
        
        Args:
            retrieved_docs: List of retrieved documents
            relevant_doc_ids: List of IDs of relevant documents
            k: Number of top documents to consider
        
        Returns:
            Hit rate (0.0 or 1.0)
        """
        if not retrieved_docs or not relevant_doc_ids:
            return 0.0
        
        top_k = retrieved_docs[:k]
        retrieved_ids = [doc.metadata.get("parent_id", "") or doc.metadata.get("source", "") for doc in top_k]
        
        # Check if any relevant document is in top K
        for doc_id in retrieved_ids:
            if doc_id in relevant_doc_ids:
                return 1.0
        
        return 0.0
    
    def mrr(self, retrieved_docs: List[Document], relevant_doc_ids: List[str]) -> float:
        """
        Calculate Mean Reciprocal Rank (MRR).
        
        MRR = 1 / rank of first relevant document, or 0 if none found.
        
        Args:
            retrieved_docs: List of retrieved documents
            relevant_doc_ids: List of IDs of relevant documents
        
        Returns:
            MRR score (0.0 to 1.0)
        """
        if not retrieved_docs or not relevant_doc_ids:
            return 0.0
        
        for rank, doc in enumerate(retrieved_docs, start=1):
            doc_id = doc.metadata.get("parent_id", "") or doc.metadata.get("source", "")
            if doc_id in relevant_doc_ids:
                return 1.0 / rank
        
        return 0.0
    
    def precision_at_k(self, retrieved_docs: List[Document], relevant_doc_ids: List[str], k: int = 5) -> float:
        """
        Calculate Precision @ K.
        
        Precision @ K = (number of relevant docs in top K) / K
        
        Args:
            retrieved_docs: List of retrieved documents
            relevant_doc_ids: List of IDs of relevant documents
            k: Number of top documents to consider
        
        Returns:
            Precision score (0.0 to 1.0)
        """
        if not retrieved_docs or not relevant_doc_ids:
            return 0.0
        
        top_k = retrieved_docs[:k]
        retrieved_ids = [doc.metadata.get("parent_id", "") or doc.metadata.get("source", "") for doc in top_k]
        
        relevant_count = sum(1 for doc_id in retrieved_ids if doc_id in relevant_doc_ids)
        return relevant_count / k if k > 0 else 0.0
    
    def recall_at_k(self, retrieved_docs: List[Document], relevant_doc_ids: List[str], k: int = 5) -> float:
        """
        Calculate Recall @ K.
        
        Recall @ K = (number of relevant docs in top K) / (total number of relevant docs)
        
        Args:
            retrieved_docs: List of retrieved documents
            relevant_doc_ids: List of IDs of relevant documents
            k: Number of top documents to consider
        
        Returns:
            Recall score (0.0 to 1.0)
        """
        if not retrieved_docs or not relevant_doc_ids:
            return 0.0
        
        total_relevant = len(relevant_doc_ids)
        if total_relevant == 0:
            return 0.0
        
        top_k = retrieved_docs[:k]
        retrieved_ids = [doc.metadata.get("parent_id", "") or doc.metadata.get("source", "") for doc in top_k]
        
        relevant_count = sum(1 for doc_id in retrieved_ids if doc_id in relevant_doc_ids)
        return relevant_count / total_relevant
    
    def evaluate_retrieval(self, query: str, retrieved_docs: List[Document], 
                         relevant_doc_ids: List[str], k: int = 5) -> Dict[str, float]:
        """
        Evaluate retrieval performance with multiple metrics.
        
        Args:
            query: Search query
            retrieved_docs: List of retrieved documents
            relevant_doc_ids: List of IDs of relevant documents
            k: Number of top documents to consider
        
        Returns:
            Dictionary with evaluation metrics
        """
        return {
            "hit_rate@k": self.hit_rate_at_k(retrieved_docs, relevant_doc_ids, k),
            "mrr": self.mrr(retrieved_docs, relevant_doc_ids),
            "precision@k": self.precision_at_k(retrieved_docs, relevant_doc_ids, k),
            "recall@k": self.recall_at_k(retrieved_docs, relevant_doc_ids, k),
        }
    
    def compare_retrieval(self, baseline_docs: List[Document], improved_docs: List[Document],
                         relevant_doc_ids: List[str], k: int = 5) -> Dict[str, Dict[str, float]]:
        """
        Compare two retrieval methods.
        
        Args:
            baseline_docs: Documents from baseline retrieval
            improved_docs: Documents from improved retrieval (e.g., with reranking)
            relevant_doc_ids: List of IDs of relevant documents
            k: Number of top documents to consider
        
        Returns:
            Dictionary with metrics for both methods
        """
        return {
            "baseline": self.evaluate_retrieval("", baseline_docs, relevant_doc_ids, k),
            "improved": self.evaluate_retrieval("", improved_docs, relevant_doc_ids, k),
        }

