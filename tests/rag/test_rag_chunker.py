"""
Tests for rag/chunker.py - Document chunking
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from langchain_core.documents import Document

from rag.chunker import Chunker
import config


class TestChunker:
    """Test Chunker class"""
    
    @pytest.fixture
    def chunker(self):
        """Create a Chunker instance"""
        return Chunker()
    
    def test_chunker_initialization(self, chunker):
        """Test chunker initializes correctly"""
        assert chunker is not None
        assert hasattr(chunker, 'create_chunks_single')
        assert hasattr(chunker, 'create_chunks_from_text')
    
    def test_create_chunks_from_text_basic(self, chunker):
        """Test creating chunks from simple text"""
        text = "# Title\n\nThis is a test document with some content."
        source_metadata = {
            "source_id": "test_doc",
            "source_type": "test"
        }
        
        parent_chunks, child_chunks = chunker.create_chunks_from_text(text, source_metadata)
        
        assert len(parent_chunks) > 0
        assert len(child_chunks) > 0
        assert all(isinstance(pc[0], str) for pc in parent_chunks)  # parent_id is string
        assert all(isinstance(cc, Document) for cc in child_chunks)
    
    def test_create_chunks_from_text_metadata(self, chunker):
        """Test that metadata is preserved in chunks"""
        text = "# Test Document\n\nContent here."
        source_metadata = {
            "source_id": "test_123",
            "source_type": "arxiv",
            "title": "Test Paper"
        }
        
        parent_chunks, child_chunks = chunker.create_chunks_from_text(text, source_metadata)
        
        # Check parent chunks have metadata
        for parent_id, parent_chunk in parent_chunks:
            assert parent_chunk.metadata.get("source_id") == "test_123"
            assert parent_chunk.metadata.get("source_type") == "arxiv"
            assert parent_chunk.metadata.get("title") == "Test Paper"
        
        # Check child chunks inherit metadata
        for child_chunk in child_chunks:
            assert child_chunk.metadata.get("source_type") == "arxiv"
    
    def test_create_chunks_from_text_large_document(self, chunker):
        """Test chunking large document"""
        # Create text larger than MAX_PARENT_SIZE
        large_text = "# Title\n\n" + "Content paragraph. " * 1000
        
        parent_chunks, child_chunks = chunker.create_chunks_from_text(large_text)
        
        assert len(parent_chunks) > 0
        assert len(child_chunks) > 0
        # Verify chunks are within reasonable size limits (allow small overage for formatting)
        for parent_id, parent_chunk in parent_chunks:
            assert len(parent_chunk.page_content) <= config.MAX_PARENT_SIZE + 100  # Allow small buffer
    
    def test_create_chunks_from_text_small_document(self, chunker):
        """Test chunking small document (should merge)"""
        small_text = "# Title\n\nShort content."
        
        parent_chunks, child_chunks = chunker.create_chunks_from_text(small_text)
        
        # Small documents should still produce at least one chunk
        assert len(parent_chunks) >= 1
        assert len(child_chunks) >= 1
    
    def test_create_chunks_single_file(self, chunker, tmp_path):
        """Test creating chunks from a markdown file"""
        # Create a test markdown file
        md_file = tmp_path / "test.md"
        md_file.write_text("# Test Document\n\nThis is test content.")
        
        parent_chunks, child_chunks = chunker.create_chunks_single(md_file)
        
        assert len(parent_chunks) > 0
        assert len(child_chunks) > 0
        
        # Check that source metadata is set
        for parent_id, parent_chunk in parent_chunks:
            assert "source" in parent_chunk.metadata
            assert "parent_id" in parent_chunk.metadata
    
    def test_create_chunks_single_nonexistent_file(self, chunker):
        """Test handling nonexistent file"""
        nonexistent = Path("nonexistent_file.md")
        
        with pytest.raises(FileNotFoundError):
            chunker.create_chunks_single(nonexistent)
    
    def test_chunks_have_parent_id(self, chunker):
        """Test that all chunks have parent_id metadata"""
        text = "# Test\n\nContent."
        parent_chunks, child_chunks = chunker.create_chunks_from_text(text)
        
        # Get parent IDs
        parent_ids = [pid for pid, _ in parent_chunks]
        
        # Check child chunks reference parent IDs
        for child_chunk in child_chunks:
            child_parent_id = child_chunk.metadata.get("parent_id")
            assert child_parent_id is not None
            assert child_parent_id in parent_ids
    
    def test_empty_text_handling(self, chunker):
        """Test handling empty text"""
        parent_chunks, child_chunks = chunker.create_chunks_from_text("")
        
        # Empty text might produce empty chunks or minimal chunk
        # Behavior depends on implementation
        assert isinstance(parent_chunks, list)
        assert isinstance(child_chunks, list)

