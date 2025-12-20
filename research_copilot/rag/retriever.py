from typing import List, Dict, Optional, Tuple
from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore

from research_copilot.storage.parent_store import ParentStoreManager
from .reranker import Reranker
from research_copilot.config import settings as config
class Retriever:
    """
    Enhanced retrieval with optional post-retrieval reranking.
    
    Wraps QdrantVectorStore search and integrates reranking and parent context retrieval.
    """
    
    def __init__(self, collection: QdrantVectorStore, parent_store: ParentStoreManager,
                 reranker: Optional[Reranker] = None, enable_reranking: bool = True):
        """
        Initialize retriever.
        
        Args:
            collection: QdrantVectorStore collection
            parent_store: ParentStoreManager for retrieving full context
            reranker: Optional Reranker instance
            enable_reranking: Whether to enable reranking (default: True)
        """
        self.collection = collection
        self.parent_store = parent_store
        self.reranker = reranker
        self.enable_reranking = enable_reranking and reranker is not None and reranker.is_available()
    
    def retrieve(self, query: str, k: int = 5, score_threshold: float = 0.7,
                 fetch_k: Optional[int] = None) -> List[Document]:
        """
        Retrieve documents without reranking.
        
        Args:
            query: Search query
            k: Number of documents to return
            score_threshold: Minimum similarity score threshold
            fetch_k: Number of documents to fetch (if None, uses k)
        
        Returns:
            List of retrieved documents
        """
        fetch_k = fetch_k or k
        try:
            results = self.collection.similarity_search(
                query, 
                k=fetch_k, 
                score_threshold=score_threshold
            )
            return results[:k]
        except Exception as e:
            print(f"Error during retrieval: {e}")
            return []
    
    def retrieve_with_rerank(self, query: str, k: int = 5, 
                             score_threshold: float = 0.7,
                             initial_k: Optional[int] = None) -> List[Tuple[Document, float]]:
        """
        Retrieve documents with post-retrieval reranking.
        
        Args:
            query: Search query
            k: Number of documents to return after reranking
            score_threshold: Minimum similarity score threshold for initial retrieval
            initial_k: Number of documents to retrieve before reranking (defaults to config)
        
        Returns:
            List of tuples (document, relevance_score) sorted by relevance
        """
        if not self.enable_reranking:
            # Fallback to non-reranked retrieval
            docs = self.retrieve(query, k=k, score_threshold=score_threshold)
            return [(doc, 1.0) for doc in docs]
        
        # Get initial_k from config or use default
        if initial_k is None:
            initial_k = getattr(config, 'RERANK_INITIAL_K', 20)
        
        # Retrieve more documents than needed for reranking
        initial_docs = self.retrieve(query, k=initial_k, score_threshold=score_threshold)
        
        if not initial_docs:
            return []
        
        # Rerank documents
        reranked = self.reranker.rerank(query, initial_docs, top_k=k)
        
        return reranked
    
    def retrieve_parent_context(self, parent_ids: List[str]) -> List[Dict]:
        """
        Retrieve full parent document chunks for complete context.
        
        Args:
            parent_ids: List of parent chunk IDs
        
        Returns:
            List of parent chunks with content and metadata
        """
        try:
            chunks = self.parent_store.load_many(parent_ids)
            return chunks
        except Exception as e:
            print(f"Error retrieving parent context: {e}")
            return []
    
    def search(self, query: str, k: int = 5, score_threshold: float = 0.7,
               use_reranking: Optional[bool] = None) -> List[Dict]:
        """
        Search and return results in dictionary format (for tools compatibility).
        
        Args:
            query: Search query
            k: Number of results to return
            score_threshold: Minimum similarity score
            use_reranking: Override enable_reranking setting
        
        Returns:
            List of dictionaries with content, parent_id, source, source_type
        """
        use_reranking = use_reranking if use_reranking is not None else self.enable_reranking
        
        if use_reranking:
            results = self.retrieve_with_rerank(query, k=k, score_threshold=score_threshold)
            documents = [doc for doc, _ in results]
        else:
            documents = self.retrieve(query, k=k, score_threshold=score_threshold)
        
        return [
            {
                "content": doc.page_content,
                "parent_id": doc.metadata.get("parent_id", ""),
                "source": doc.metadata.get("source", ""),
                "source_type": doc.metadata.get("source_type", "local")
            }
            for doc in documents
        ]

