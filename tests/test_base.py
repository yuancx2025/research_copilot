"""
Tests for tools/base.py - Base classes and schemas
"""
import pytest
from tools.base import SourceType, Citation, ToolResult, BaseToolkit


class TestSourceType:
    """Test SourceType enum"""
    
    def test_source_type_values(self):
        """Test all source types are defined"""
        assert SourceType.LOCAL == "local"
        assert SourceType.ARXIV == "arxiv"
        assert SourceType.YOUTUBE == "youtube"
        assert SourceType.GITHUB == "github"
        assert SourceType.WEB == "web"


class TestCitation:
    """Test Citation model"""
    
    def test_citation_creation(self):
        """Test creating a citation"""
        citation = Citation(
            source_type=SourceType.ARXIV,
            title="Test Paper",
            url="https://arxiv.org/abs/1234.5678",
            authors=["John Doe", "Jane Smith"],
            date="2024-01-01",
            snippet="This is a test paper"
        )
        
        assert citation.source_type == SourceType.ARXIV
        assert citation.title == "Test Paper"
        assert len(citation.authors) == 2
        assert citation.date == "2024-01-01"
    
    def test_citation_markdown_formatting(self):
        """Test citation markdown formatting"""
        citation = Citation(
            source_type=SourceType.ARXIV,
            title="Test Paper",
            url="https://arxiv.org/abs/1234.5678",
            authors=["John Doe", "Jane Smith", "Bob Wilson", "Alice Brown"],
            date="2024-01-01"
        )
        
        markdown = citation.to_markdown()
        assert "Test Paper" in markdown
        assert "https://arxiv.org/abs/1234.5678" in markdown
        assert "et al." in markdown  # Should truncate authors
    
    def test_citation_youtube_formatting(self):
        """Test YouTube citation formatting"""
        citation = Citation(
            source_type=SourceType.YOUTUBE,
            title="Tutorial Video",
            url="https://youtube.com/watch?v=123"
        )
        
        markdown = citation.to_markdown()
        assert "📺" in markdown
        assert "Tutorial Video" in markdown
    
    def test_citation_github_formatting(self):
        """Test GitHub citation formatting"""
        citation = Citation(
            source_type=SourceType.GITHUB,
            title="Awesome Repo",
            url="https://github.com/user/repo"
        )
        
        markdown = citation.to_markdown()
        assert "💻" in markdown
        assert "Awesome Repo" in markdown


class TestToolResult:
    """Test ToolResult model"""
    
    def test_successful_result(self):
        """Test successful tool result"""
        result = ToolResult(
            success=True,
            data={"key": "value"},
            citations=[]
        )
        
        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.error is None
    
    def test_failed_result(self):
        """Test failed tool result"""
        result = ToolResult(
            success=False,
            data=None,
            error="Something went wrong"
        )
        
        assert result.success is False
        assert result.error == "Something went wrong"
    
    def test_result_with_citations(self):
        """Test result with citations"""
        citation = Citation(
            source_type=SourceType.ARXIV,
            title="Test",
            url="https://test.com"
        )
        
        result = ToolResult(
            success=True,
            data={"papers": []},
            citations=[citation]
        )
        
        assert len(result.citations) == 1
        assert result.citations[0].title == "Test"


class TestBaseToolkit:
    """Test BaseToolkit abstract class"""
    
    def test_base_toolkit_is_abstract(self):
        """Test that BaseToolkit cannot be instantiated directly"""
        with pytest.raises(TypeError):
            BaseToolkit()
    
    def test_base_toolkit_interface(self):
        """Test that BaseToolkit defines required methods"""
        # Check abstract methods exist
        assert hasattr(BaseToolkit, 'create_tools')
        assert hasattr(BaseToolkit, 'is_available')
        assert hasattr(BaseToolkit, 'get_source_type')
        assert hasattr(BaseToolkit, '_create_citation')

