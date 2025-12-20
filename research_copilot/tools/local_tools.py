from typing import List, Dict, Optional
from langchain_core.tools import tool, BaseTool
from .base import BaseToolkit, SourceType, Citation
from research_copilot.storage.parent_store import ParentStoreManager
from research_copilot.rag.retriever import Retriever
from research_copilot.config import settings as config
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
        if not self.collection:
            return [{"error": "No document collection loaded"}]
        
        try:
            # Use retriever with reranking if available
            if self.retriever:
                results = self.retriever.search(
                    query, 
                    k=k, 
                    score_threshold=0.7,
                    use_reranking=getattr(config, 'ENABLE_RERANKING', True)
                )
                return results
            else:
                # Fallback to direct collection search
                results = self.collection.similarity_search(query, k=k, score_threshold=0.7)
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
            return [{"error": f"Search failed: {str(e)}"}]
    
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
            return [{"error": f"Retrieval failed: {str(e)}"}]
    
    def create_tools(self) -> List[BaseTool]:
        """Create local document search tools."""
        return [
            tool("search_local_documents")(self._search_child_chunks),
            tool("retrieve_document_context")(self._retrieve_parent_chunks)
        ]