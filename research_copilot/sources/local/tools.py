import logging
from typing import List, Dict, Optional
from langchain_core.tools import tool, BaseTool, ToolException
from research_copilot.runtime.base_toolkit import BaseToolkit
from research_copilot.runtime.schemas import SourceType
from research_copilot.storage.parent_store import ParentStoreManager
from research_copilot.rag.retriever import Retriever
from research_copilot.config import settings as config

logger = logging.getLogger(__name__)


class LocalToolkit(BaseToolkit):
    """Tools for searching locally indexed documents."""
    
    source_type = SourceType.LOCAL
    
    def __init__(self, config, collection=None):
        self.config = config
        self.collection = collection
        self.parent_store_manager = ParentStoreManager()
        self.retriever = None
    
    def set_collection(self, collection):
        """Set the vector store collection (called after initialization)."""
        self.collection = collection
    
    def set_retriever(self, retriever: Retriever):
        """Set the retriever instance (for reranking support)."""
        self.retriever = retriever
    
    def is_available(self) -> bool:
        """Local tools are always available."""
        return True
    
    def _search_child_chunks(self, query: str, k: int = 5) -> List[Dict]:
        """
        Search for the top K most relevant document chunks from local knowledge base.
        
        Uses retriever with reranking if available, otherwise falls back to direct collection search.
        
        Args:
            query: Search query string
            k: Number of results to return (default: 5)
        
        Returns:
            List of relevant document chunks with metadata
        """
        # Failures raise ToolException so the agent's ToolNode records an error result (and the
        # tracer counts it) instead of a normal-looking result the agent reads as "nothing found".
        if not self.collection:
            raise ToolException("No document collection loaded")

        try:
            # Use retriever with reranking if available
            if self.retriever:
                # No raw score threshold: hybrid scores are rank-based, so the retriever
                # gates on dense similarity instead (RETRIEVAL_MIN_DENSE_SCORE).
                results = self.retriever.search(
                    query,
                    k=k,
                    use_reranking=getattr(config, 'ENABLE_RERANKING', True)
                )
                return results
            else:
                # Fallback to direct collection search
                results = self.collection.similarity_search(query, k=k)
                return [
                    {
                        "content": doc.page_content,
                        "parent_id": doc.metadata.get("parent_id", ""),
                        "source": doc.metadata.get("source", ""),
                        "source_type": doc.metadata.get("source_type", "local")
                    }
                    for doc in results
                ]
        except Exception as e:
            logger.exception("Local document search failed")
            raise ToolException(f"Search failed: {e}") from e
    
    def _retrieve_parent_chunks(self, parent_ids: List[str]) -> List[Dict]:
        """
        Retrieve full parent document chunks by their IDs for complete context.
        
        Args:
            parent_ids: List of parent chunk IDs to retrieve
        
        Returns:
            List of full parent chunks with complete content
        """
        try:
            chunks = self.parent_store_manager.load_many(parent_ids)
            return [
                {**chunk, "source_type": "local"}
                for chunk in chunks
            ]
        except Exception as e:
            logger.exception("Parent context retrieval failed")
            raise ToolException(f"Retrieval failed: {e}") from e
    
    def create_tools(self) -> List[BaseTool]:
        """Create local document search tools."""
        return [
            tool("search_local_documents")(self._search_child_chunks),
            tool("retrieve_document_context")(self._retrieve_parent_chunks)
        ]