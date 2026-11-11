from typing import List, Dict, Optional, Tuple
from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore, RetrievalMode
from qdrant_client import models as qmodels

from research_copilot.storage.parent_store import ParentStoreManager
from .reranker import Reranker
from research_copilot.config import settings as config

_DEFAULT = object()  # "use the configured value"


def _parent_key(doc: Document) -> str:
    """The unit the agent fetches: the parent id, else the document's own identity."""
    md = doc.metadata or {}
    return md.get("parent_id") or f"{md.get('source', '')}::{hash(doc.page_content)}"


def collapse_by_parent(docs: List[Document], k: int) -> List[Document]:
    """First (best-ranked) chunk of each parent, until ``k`` distinct parents."""
    kept, seen = [], set()
    for doc in docs:
        key = _parent_key(doc)
        if key in seen:
            continue
        seen.add(key)
        kept.append(doc)
        if len(kept) == k:
            break
    return kept


class Retriever:
    """
    Enhanced retrieval with optional post-retrieval reranking.

    Wraps QdrantVectorStore search and integrates reranking and parent context retrieval.

    Relevance gate: hybrid (RRF) scores are rank-based, so a score threshold on
    them filters nothing. Instead the retriever checks the best *dense* cosine
    similarity for the query and returns no results when it is below
    ``min_relevance`` (RETRIEVAL_MIN_DENSE_SCORE), so the agent can say the
    documents do not cover the question instead of answering from noise.
    """

    def __init__(self, collection: QdrantVectorStore, parent_store: ParentStoreManager,
                 reranker: Optional[Reranker] = None, enable_reranking: bool = True,
                 min_relevance=_DEFAULT, fetch_multiplier=_DEFAULT, collapse_parents=_DEFAULT,
                 fusion=_DEFAULT):
        """
        Initialize retriever.

        Args:
            collection: QdrantVectorStore collection
            parent_store: ParentStoreManager for retrieving full context
            reranker: Optional Reranker instance
            enable_reranking: Whether to enable reranking (default: True)
            min_relevance: Minimum best dense cosine similarity; None disables the gate
        """
        self.collection = collection
        self.parent_store = parent_store
        self.reranker = reranker
        self.enable_reranking = enable_reranking and reranker is not None and reranker.is_available()
        self.min_relevance = (getattr(config, "RETRIEVAL_MIN_DENSE_SCORE", None)
                              if min_relevance is _DEFAULT else min_relevance)
        self.fetch_multiplier = (getattr(config, "RETRIEVAL_FETCH_MULTIPLIER", 1)
                                 if fetch_multiplier is _DEFAULT else fetch_multiplier)
        self.collapse_parents = (getattr(config, "RETRIEVAL_COLLAPSE_PARENTS", False)
                                 if collapse_parents is _DEFAULT else collapse_parents)
        # How Qdrant merges the BM25 and dense result lists in hybrid mode: "rrf" (rank-based)
        # or "dbsf" (distribution-based score fusion, which keeps score magnitudes).
        self.fusion = getattr(config, "RETRIEVAL_HYBRID_FUSION", "rrf") if fusion is _DEFAULT else fusion
        self._dense_view = None

    def _dense_store(self) -> Optional[QdrantVectorStore]:
        """A dense-only view of the same collection, or None if the store cannot provide one."""
        if not isinstance(self.collection, QdrantVectorStore):
            return None
        mode = self.collection.retrieval_mode
        if mode == RetrievalMode.DENSE:
            return self.collection
        if mode != RetrievalMode.HYBRID:
            return None
        if self._dense_view is None:
            self._dense_view = QdrantVectorStore(
                client=self.collection.client,
                collection_name=self.collection.collection_name,
                embedding=self.collection.embeddings,
                retrieval_mode=RetrievalMode.DENSE,
                vector_name=self.collection.vector_name,
            )
        return self._dense_view

    def _fusion_kwargs(self, fusion: Optional[str]) -> dict:
        """``hybrid_fusion`` for real Qdrant hybrid stores; nothing for other stores."""
        if (not fusion or not isinstance(self.collection, QdrantVectorStore)
                or self.collection.retrieval_mode != RetrievalMode.HYBRID):
            return {}
        return {"hybrid_fusion": qmodels.FusionQuery(fusion=qmodels.Fusion(fusion.lower()))}

    def top_dense_score(self, query: str) -> Optional[float]:
        """Cosine similarity of the best dense match, or None when unavailable."""
        store = self._dense_store()
        if store is None:
            return None
        hits = store.similarity_search_with_score(query, k=1)
        return float(hits[0][1]) if hits else None

    def is_relevant(self, query: str, min_relevance=_DEFAULT) -> bool:
        """False only when the corpus has no dense match at or above the gate."""
        gate = self.min_relevance if min_relevance is _DEFAULT else min_relevance
        if gate is None:
            return True
        top = self.top_dense_score(query)
        return top is None or top >= gate

    def retrieve(self, query: str, k: int = 5, score_threshold: Optional[float] = None,
                 fetch_k: Optional[int] = None, min_relevance=_DEFAULT, collapse=_DEFAULT,
                 fusion=_DEFAULT) -> List[Document]:
        """
        Retrieve documents without reranking.

        Args:
            query: Search query
            k: Number of results to return (distinct parents when collapsing)
            score_threshold: Raw store score threshold (no effect on hybrid scores; prefer the gate)
            fetch_k: Chunk candidates per search leg (default: k * RETRIEVAL_FETCH_MULTIPLIER).
                Qdrant hybrid search only fuses this many candidates from each of BM25 and dense.
            min_relevance: Override the dense relevance gate for this call
            collapse: Keep only the best chunk of each parent (default: RETRIEVAL_COLLAPSE_PARENTS).
                The agent fetches whole parents, so repeated chunks of one parent waste context slots.
            fusion: Hybrid fusion method, "rrf" or "dbsf" (default: RETRIEVAL_HYBRID_FUSION)

        Returns:
            List of retrieved documents
        """
        collapse = self.collapse_parents if collapse is _DEFAULT else collapse
        if fetch_k is None:
            fetch_k = k * self.fetch_multiplier if self.fetch_multiplier else k
        if not self.is_relevant(query, min_relevance):
            return []
        # Errors propagate: returning [] here made a broken index look like "no relevant documents".
        extra = self._fusion_kwargs(self.fusion if fusion is _DEFAULT else fusion)
        results = self.collection.similarity_search(
            query,
            k=fetch_k,
            score_threshold=score_threshold,
            **extra
        )
        return collapse_by_parent(results, k) if collapse else results[:k]
    
    def retrieve_with_rerank(self, query: str, k: int = 5,
                             score_threshold: Optional[float] = None,
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
        
        # Retrieve chunk-level candidates (not collapsed) so the reranker sees every chunk
        initial_docs = self.retrieve(query, k=initial_k, score_threshold=score_threshold,
                                     fetch_k=initial_k, collapse=False)

        if not initial_docs:
            return []

        if not self.collapse_parents:
            return self.reranker.rerank(query, initial_docs, top_k=k)
        # Score every candidate, then keep the best-scoring chunk of each parent
        reranked = self.reranker.rerank(query, initial_docs, top_k=len(initial_docs))
        kept, seen = [], set()
        for doc, score in reranked:
            key = _parent_key(doc)
            if key in seen:
                continue
            seen.add(key)
            kept.append((doc, score))
            if len(kept) == k:
                break
        return kept
    
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
    
    def search(self, query: str, k: int = 5, score_threshold: Optional[float] = None,
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

