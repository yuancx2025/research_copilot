"""
Tests for rag/indexer.py - Unified indexing interface
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from langchain_core.documents import Document

from rag.indexer import Indexer
from rag.chunker import Chunker
from db.vector_db_manager import VectorDbManager
from db.parent_store_manager import ParentStoreManager


class TestIndexer:
    """Test Indexer class"""
    
    @pytest.fixture
    def mock_vector_db(self):
        """Create mock vector DB"""
        return Mock(spec=VectorDbManager)
    
    @pytest.fixture
    def mock_parent_store(self):
        """Create mock parent store"""
        parent_store = Mock(spec=ParentStoreManager)
        parent_store.save_many = Mock()
        return parent_store
    
    @pytest.fixture
    def mock_chunker(self):
        """Create mock chunker"""
        chunker = Mock(spec=Chunker)
        
        # Mock parent and child chunks
        parent_chunk = Document(
            page_content="Parent content",
            metadata={"parent_id": "p1", "source": "test.pdf"}
        )
        child_chunk = Document(
            page_content="Child content",
            metadata={"parent_id": "p1", "source": "test.pdf"}
        )
        
        chunker.create_chunks_single.return_value = (
            [("p1", parent_chunk)],
            [child_chunk]
        )
        
        chunker.create_chunks_from_text.return_value = (
            [("p1", parent_chunk)],
            [child_chunk]
        )
        
        return chunker
    
    @pytest.fixture
    def mock_collection(self):
        """Create mock collection"""
        collection = MagicMock()
        collection.add_documents = Mock()
        return collection
    
    @pytest.fixture
    def indexer(self, mock_vector_db, mock_parent_store, mock_chunker):
        """Create indexer instance"""
        return Indexer(mock_vector_db, mock_parent_store, mock_chunker)
    
    def test_indexer_initialization(self, indexer, mock_vector_db, mock_parent_store, mock_chunker):
        """Test indexer initializes correctly"""
        assert indexer.vector_db == mock_vector_db
        assert indexer.parent_store == mock_parent_store
        assert indexer.chunker == mock_chunker
    
    def test_index_document_success(self, indexer, mock_collection, mock_chunker, tmp_path):
        """Test successful document indexing"""
        md_file = tmp_path / "test.md"
        md_file.write_text("# Test\n\nContent.")
        
        result = indexer.index_document(md_file, mock_collection, source_type="local")
        
        assert result is True
        mock_chunker.create_chunks_single.assert_called_once()
        mock_collection.add_documents.assert_called_once()
        indexer.parent_store.save_many.assert_called_once()
    
    def test_index_document_with_metadata(self, indexer, mock_collection, mock_chunker, tmp_path):
        """Test indexing with custom metadata"""
        md_file = tmp_path / "test.md"
        md_file.write_text("# Test\n\nContent.")
        
        source_metadata = {
            "title": "Test Document",
            "author": "Test Author"
        }
        
        result = indexer.index_document(
            md_file, mock_collection, 
            source_type="arxiv",
            source_metadata=source_metadata
        )
        
        assert result is True
        # Verify metadata was passed to chunker
        call_args = mock_chunker.create_chunks_single.call_args
        assert call_args[0][0] == md_file
    
    def test_index_document_no_chunks(self, indexer, mock_collection, mock_chunker, tmp_path):
        """Test indexing when no chunks are created"""
        md_file = tmp_path / "test.md"
        md_file.write_text("# Test\n\nContent.")
        
        mock_chunker.create_chunks_single.return_value = ([], [])
        
        result = indexer.index_document(md_file, mock_collection)
        
        assert result is False
        mock_collection.add_documents.assert_not_called()
    
    def test_index_document_error(self, indexer, mock_collection, mock_chunker, tmp_path):
        """Test error handling during indexing"""
        md_file = tmp_path / "test.md"
        md_file.write_text("# Test\n\nContent.")
        
        mock_chunker.create_chunks_single.side_effect = Exception("Chunking failed")
        
        result = indexer.index_document(md_file, mock_collection)
        
        assert result is False
    
    def test_index_text_success(self, indexer, mock_collection, mock_chunker):
        """Test successful text indexing"""
        text = "# Test Document\n\nThis is test content."
        source_metadata = {
            "source_id": "test_123",
            "title": "Test"
        }
        
        result = indexer.index_text(
            text, mock_collection,
            source_type="arxiv",
            source_metadata=source_metadata
        )
        
        assert result is True
        mock_chunker.create_chunks_from_text.assert_called_once()
        mock_collection.add_documents.assert_called_once()
        indexer.parent_store.save_many.assert_called_once()
    
    def test_index_text_no_chunks(self, indexer, mock_collection, mock_chunker):
        """Test text indexing when no chunks created"""
        mock_chunker.create_chunks_from_text.return_value = ([], [])
        
        result = indexer.index_text("", mock_collection, source_type="test")
        
        assert result is False
    
    def test_index_text_error(self, indexer, mock_collection, mock_chunker):
        """Test error handling in text indexing"""
        mock_chunker.create_chunks_from_text.side_effect = Exception("Error")
        
        result = indexer.index_text("test", mock_collection, source_type="test")
        
        assert result is False
    
    def test_index_batch(self, indexer, mock_collection, mock_chunker, tmp_path):
        """Test batch indexing"""
        md_files = []
        for i in range(3):
            md_file = tmp_path / f"test_{i}.md"
            md_file.write_text(f"# Test {i}\n\nContent {i}.")
            md_files.append(md_file)
        
        added, skipped = indexer.index_batch(md_files, mock_collection)
        
        assert added == 3
        assert skipped == 0
        assert mock_collection.add_documents.call_count == 3
    
    def test_index_batch_with_progress(self, indexer, mock_collection, mock_chunker, tmp_path):
        """Test batch indexing with progress callback"""
        md_files = []
        for i in range(2):
            md_file = tmp_path / f"test_{i}.md"
            md_file.write_text(f"# Test {i}\n\nContent.")
            md_files.append(md_file)
        
        progress_calls = []
        def progress_callback(progress, message):
            progress_calls.append((progress, message))
        
        added, skipped = indexer.index_batch(
            md_files, mock_collection,
            progress_callback=progress_callback
        )
        
        assert len(progress_calls) == 2
        assert progress_calls[0][0] == 0.5  # 1/2
        assert progress_calls[1][0] == 1.0   # 2/2
    
    def test_index_batch_with_failures(self, indexer, mock_collection, mock_chunker, tmp_path):
        """Test batch indexing with some failures"""
        md_files = []
        for i in range(3):
            md_file = tmp_path / f"test_{i}.md"
            md_file.write_text(f"# Test {i}\n\nContent.")
            md_files.append(md_file)
        
        # Make second file fail
        def side_effect(*args, **kwargs):
            if args[0] == md_files[1]:
                raise Exception("Failed")
            return ([("p1", Document(page_content="test", metadata={}))], 
                   [Document(page_content="test", metadata={})])
        
        mock_chunker.create_chunks_single.side_effect = side_effect
        
        added, skipped = indexer.index_batch(md_files, mock_collection)
        
        assert added == 2
        assert skipped == 1

