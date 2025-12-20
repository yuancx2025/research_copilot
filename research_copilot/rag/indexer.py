from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime
from langchain_core.documents import Document

from .chunker import Chunker
from research_copilot.storage.qdrant_client import VectorDbManager
from research_copilot.storage.parent_store import ParentStoreManager


class Indexer:
    """
    Unified indexing interface for all document sources.
    
    Handles chunking, metadata enrichment, and storage to vector DB and parent store.
    """
    
    def __init__(self, vector_db: VectorDbManager, parent_store: ParentStoreManager, chunker: Chunker):
        self.vector_db = vector_db
        self.parent_store = parent_store
        self.chunker = chunker
    
    def index_document(self, md_path: Path, collection, source_type: str = "local", 
                      source_metadata: Optional[Dict] = None) -> bool:
        """
        Index a single markdown document.
        
        Args:
            md_path: Path to markdown file
            collection: QdrantVectorStore collection
            source_type: Type of source ("local", "arxiv", "youtube", "github", "web")
            source_metadata: Additional metadata to add to chunks
        
        Returns:
            True if indexing successful, False otherwise
        """
        try:
            parent_chunks, child_chunks = self.chunker.create_chunks_single(md_path)
            
            if not child_chunks:
                return False
            
            # Enrich metadata with source information
            enriched_metadata = {
                "source_type": source_type,
                "indexed_at": datetime.now().isoformat(),
            }
            if source_metadata:
                enriched_metadata.update(source_metadata)
            
            # Add metadata to all chunks
            for parent_id, parent_chunk in parent_chunks:
                parent_chunk.metadata.update(enriched_metadata)
            
            for child_chunk in child_chunks:
                # Copy parent metadata to child chunks
                parent_id = child_chunk.metadata.get("parent_id", "")
                if parent_id:
                    # Find corresponding parent metadata
                    for pid, pchunk in parent_chunks:
                        if pid == parent_id:
                            child_chunk.metadata.update(pchunk.metadata)
                            break
                else:
                    child_chunk.metadata.update(enriched_metadata)
            
            # Store in vector DB and parent store
            collection.add_documents(child_chunks)
            self.parent_store.save_many(parent_chunks)
            
            return True
        except Exception as e:
            print(f"Error indexing document {md_path}: {e}")
            return False
    
    def index_text(self, text: str, collection, source_type: str, 
                   source_metadata: Optional[Dict] = None) -> bool:
        """
        Index raw text content (for multi-source indexing).
        
        Args:
            text: Raw text content to index
            collection: QdrantVectorStore collection
            source_type: Type of source ("arxiv", "youtube", "github", "web")
            source_metadata: Metadata including source_id, title, etc.
        
        Returns:
            True if indexing successful, False otherwise
        """
        try:
            # Prepare metadata
            enriched_metadata = {
                "source_type": source_type,
                "indexed_at": datetime.now().isoformat(),
            }
            if source_metadata:
                enriched_metadata.update(source_metadata)
            
            # Create chunks from text
            parent_chunks, child_chunks = self.chunker.create_chunks_from_text(text, enriched_metadata)
            
            if not child_chunks:
                return False
            
            # Store in vector DB and parent store
            collection.add_documents(child_chunks)
            self.parent_store.save_many(parent_chunks)
            
            return True
        except Exception as e:
            print(f"Error indexing text content: {e}")
            return False
    
    def index_batch(self, md_paths: List[Path], collection, source_type: str = "local",
                    progress_callback=None) -> tuple[int, int]:
        """
        Index multiple documents in batch.
        
        Args:
            md_paths: List of markdown file paths
            collection: QdrantVectorStore collection
            source_type: Type of source
            progress_callback: Optional callback function(progress, message)
        
        Returns:
            Tuple of (added_count, skipped_count)
        """
        added = 0
        skipped = 0
        
        for i, md_path in enumerate(md_paths):
            if progress_callback:
                progress_callback((i + 1) / len(md_paths), f"Processing {md_path.name}")
            
            if self.index_document(md_path, collection, source_type):
                added += 1
            else:
                skipped += 1
        
        return added, skipped

