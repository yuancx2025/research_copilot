"""
Tests for tools/github_tools.py - GitHub repository tools
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import requests
from tools.github_tools import GitHubToolkit
from tools.base import SourceType


class TestGitHubToolkit:
    """Test GitHubToolkit class"""
    
    def test_source_type(self):
        """Test that GitHubToolkit has correct source type"""
        config = Mock()
        config.USE_GITHUB_MCP = False
        config.GITHUB_TOKEN = None
        toolkit = GitHubToolkit(config)
        
        assert toolkit.source_type == SourceType.GITHUB
    
    def test_is_always_available(self):
        """Test that GitHub is always available"""
        config = Mock()
        config.USE_GITHUB_MCP = False
        config.GITHUB_TOKEN = None
        toolkit = GitHubToolkit(config)
        
        assert toolkit.is_available() is True
    
    @patch('tools.github_tools.requests.get')
    def test_search_repositories(self, mock_get):
        """Test GitHub repository search"""
        config = Mock()
        config.USE_GITHUB_MCP = False
        config.GITHUB_TOKEN = None
        toolkit = GitHubToolkit(config)
        
        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "items": [
                {
                    "full_name": "user/repo",
                    "name": "repo",
                    "owner": {"login": "user"},
                    "description": "Test repo",
                    "html_url": "https://github.com/user/repo",
                    "stargazers_count": 100,
                    "forks_count": 50,
                    "language": "Python",
                    "topics": ["ai", "ml"],
                    "updated_at": "2024-01-01T00:00:00Z",
                    "default_branch": "main"
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        results = toolkit._search_repositories("langchain", max_results=5)
        
        assert len(results) > 0
        assert results[0]["full_name"] == "user/repo"
        assert results[0]["source_type"] == "github"
    
    @patch('tools.github_tools.requests.get')
    def test_get_readme(self, mock_get):
        """Test getting repository README"""
        config = Mock()
        config.USE_GITHUB_MCP = False
        config.GITHUB_TOKEN = None
        toolkit = GitHubToolkit(config)
        
        # Mock API response
        import base64
        content = base64.b64encode(b"# Test README\n\nThis is a test.").decode('utf-8')
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "content": content,
            "path": "README.md",
            "html_url": "https://github.com/user/repo/blob/main/README.md"
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = toolkit._get_readme("user/repo")
        
        assert "content" in result
        assert result["repo"] == "user/repo"
        assert result["source_type"] == "github"
    
    @patch('tools.github_tools.requests.get')
    def test_get_file_content(self, mock_get):
        """Test getting file content"""
        config = Mock()
        config.USE_GITHUB_MCP = False
        config.GITHUB_TOKEN = None
        toolkit = GitHubToolkit(config)
        
        import base64
        content = base64.b64encode(b"def hello():\n    print('hello')").decode('utf-8')
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "type": "file",
            "content": content,
            "size": 100,
            "html_url": "https://github.com/user/repo/blob/main/test.py"
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = toolkit._get_file_content("user/repo", "test.py")
        
        assert "content" in result
        assert result["path"] == "test.py"
        assert result["source_type"] == "github"
    
    @patch('tools.github_tools.requests.get')
    def test_get_repo_structure(self, mock_get):
        """Test getting repository structure"""
        config = Mock()
        config.USE_GITHUB_MCP = False
        config.GITHUB_TOKEN = None
        toolkit = GitHubToolkit(config)
        
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"name": "src", "type": "dir", "path": "src"},
            {"name": "README.md", "type": "file", "path": "README.md", "size": 100}
        ]
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = toolkit._get_repo_structure("user/repo")
        
        assert "contents" in result
        assert len(result["contents"]) == 2
        assert result["source_type"] == "github"
    
    def test_create_tools(self):
        """Test that tools are created correctly"""
        config = Mock()
        config.USE_GITHUB_MCP = False
        config.GITHUB_TOKEN = None
        toolkit = GitHubToolkit(config)
        
        tools = toolkit.create_tools()
        
        assert len(tools) == 4
        tool_names = [t.name for t in tools]
        assert "search_github" in tool_names
        assert "get_github_readme" in tool_names
        assert "get_github_file" in tool_names
        assert "get_repo_structure" in tool_names
    
    def test_error_handling(self):
        """Test error handling"""
        config = Mock()
        config.USE_GITHUB_MCP = False
        config.GITHUB_TOKEN = None
        toolkit = GitHubToolkit(config)
        
        with patch('tools.github_tools.requests.get') as mock_get:
            mock_get.side_effect = requests.exceptions.RequestException("API Error")
            
            results = toolkit._search_repositories("test")
            
            assert len(results) == 1
            assert "error" in results[0]

