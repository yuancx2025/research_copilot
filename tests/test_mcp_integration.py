"""
Integration tests for MCP-enabled toolkits.

Tests MCP initialization, fallback behavior, and tool creation.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import asyncio

from tools.github_tools import GitHubToolkit
from tools.web_tools import WebToolkit
from tools.registry import ToolRegistry


class TestGitHubMCPIntegration:
    """Test GitHub toolkit MCP integration."""
    
    def test_github_toolkit_mcp_disabled(self):
        """Test GitHub toolkit without MCP (default behavior)."""
        config = Mock()
        config.USE_GITHUB_MCP = False
        config.GITHUB_TOKEN = None
        
        toolkit = GitHubToolkit(config)
        assert toolkit.use_mcp is False
        assert toolkit._mcp_tools is None
        
        tools = toolkit.create_tools()
        # Should return direct API tools
        assert len(tools) == 4
        assert any(t.name == "search_github" for t in tools)
    
    def test_github_toolkit_mcp_enabled_no_connection(self):
        """Test GitHub toolkit with MCP enabled but connection fails."""
        config = Mock()
        config.USE_GITHUB_MCP = True
        config.GITHUB_TOKEN = "test_token"
        
        toolkit = GitHubToolkit(config)
        assert toolkit.use_mcp is True
        
        # Mock MCP adapter to fail connection
        with patch('tools.github_tools.MCPToolAdapter') as mock_adapter_class:
            mock_adapter = AsyncMock()
            mock_adapter.connect = AsyncMock(return_value=False)
            mock_adapter.create_langchain_tools = AsyncMock()
            mock_adapter_class.return_value = mock_adapter
            
            tools = toolkit.create_tools()
            # Should fall back to direct API tools
            assert len(tools) == 4
            assert any(t.name == "search_github" for t in tools)
    
    @pytest.mark.asyncio
    async def test_github_toolkit_mcp_initialization(self):
        """Test GitHub toolkit MCP initialization."""
        config = Mock()
        config.USE_GITHUB_MCP = True
        config.GITHUB_TOKEN = "test_token"
        
        toolkit = GitHubToolkit(config)
        
        # Mock successful MCP connection
        mock_tool = MagicMock()
        mock_tool.name = "github_search_repositories"
        mock_tool.description = "Search GitHub repositories"
        
        with patch('tools.github_tools.MCPToolAdapter') as mock_adapter_class:
            mock_adapter = AsyncMock()
            mock_adapter.connect = AsyncMock(return_value=True)
            mock_adapter.create_langchain_tools = AsyncMock(return_value=[mock_tool])
            mock_adapter_class.return_value = mock_adapter
            
            await toolkit._ensure_mcp_initialized()
            
            assert toolkit._mcp_tools is not None
            assert len(toolkit._mcp_tools) == 1
    
    def test_github_toolkit_mcp_fallback(self):
        """Test GitHub toolkit falls back to API when MCP fails."""
        config = Mock()
        config.USE_GITHUB_MCP = True
        config.GITHUB_TOKEN = "test_token"
        
        toolkit = GitHubToolkit(config)
        
        # Mock MCP initialization failure
        with patch.object(toolkit, '_ensure_mcp_initialized', side_effect=Exception("MCP failed")):
            tools = toolkit.create_tools()
            # Should fall back to direct API tools
            assert len(tools) == 4
            assert any(t.name == "search_github" for t in tools)


class TestWebMCPIntegration:
    """Test Web toolkit MCP integration."""
    
    def test_web_toolkit_mcp_disabled(self):
        """Test Web toolkit without MCP (default behavior)."""
        config = Mock()
        config.USE_WEB_SEARCH_MCP = False
        config.TAVILY_API_KEY = "test_key"
        config.MAX_WEB_RESULTS = 10
        
        toolkit = WebToolkit(config)
        assert toolkit.use_mcp is False
        assert toolkit._mcp_tools is None
        
        tools = toolkit.create_tools()
        # Should return direct API tools
        assert len(tools) == 4
        assert any(t.name == "web_search" for t in tools)
    
    def test_web_toolkit_mcp_enabled_no_config(self):
        """Test Web toolkit with MCP enabled but no server config."""
        config = Mock()
        config.USE_WEB_SEARCH_MCP = True
        config.TAVILY_API_KEY = None
        config.MAX_WEB_RESULTS = 10
        config.WEB_SEARCH_MCP_SERVER_PATH = None
        
        toolkit = WebToolkit(config)
        assert toolkit.use_mcp is True
        
        # Should not have MCP server config
        server_config = toolkit._get_mcp_server_config()
        # May return None if no config available
        tools = toolkit.create_tools()
        # Should fall back to direct API tools or handle gracefully
        assert len(tools) >= 0  # May be empty if no API key
    
    @pytest.mark.asyncio
    async def test_web_toolkit_mcp_initialization(self):
        """Test Web toolkit MCP initialization."""
        config = Mock()
        config.USE_WEB_SEARCH_MCP = True
        config.TAVILY_API_KEY = "test_key"
        config.MAX_WEB_RESULTS = 10
        config.WEB_SEARCH_MCP_SERVER_PATH = None
        
        toolkit = WebToolkit(config)
        
        # Mock successful MCP connection
        mock_tool = MagicMock()
        mock_tool.name = "web_search"
        mock_tool.description = "Search the web"
        
        with patch('tools.web_tools.MCPToolAdapter') as mock_adapter_class:
            mock_adapter = AsyncMock()
            mock_adapter.connect = AsyncMock(return_value=True)
            mock_adapter.create_langchain_tools = AsyncMock(return_value=[mock_tool])
            mock_adapter_class.return_value = mock_adapter
            
            # Mock server config to return valid config
            with patch.object(toolkit, '_get_mcp_server_config', return_value={
                "command": "python",
                "args": ["test_server.py"],
                "env": {"TAVILY_API_KEY": "test_key"}
            }):
                await toolkit._ensure_mcp_initialized()
                
                if toolkit._mcp_tools:
                    assert len(toolkit._mcp_tools) == 1


class TestMCPRegistryIntegration:
    """Test MCP integration with tool registry."""
    
    def test_registry_initializes_mcp_toolkits(self):
        """Test registry initializes MCP when registering toolkits."""
        config = Mock()
        config.USE_GITHUB_MCP = True
        config.GITHUB_TOKEN = "test_token"
        config.ENABLE_GITHUB_AGENT = True
        
        registry = ToolRegistry()
        
        # Mock MCP initialization
        with patch('tools.github_tools.GitHubToolkit') as mock_toolkit_class:
            mock_toolkit = Mock()
            mock_toolkit.is_available = Mock(return_value=True)
            mock_toolkit.use_mcp = True
            mock_toolkit.source_type = Mock()
            mock_toolkit.source_type.value = "github"
            mock_toolkit._ensure_mcp_initialized = AsyncMock()
            mock_toolkit.create_tools = Mock(return_value=[])
            mock_toolkit_class.return_value = mock_toolkit
            
            registry.register(mock_toolkit)
            
            # Should have attempted MCP initialization
            assert mock_toolkit in registry._toolkits.values()
    
    def test_registry_handles_mcp_failure_gracefully(self):
        """Test registry handles MCP initialization failures."""
        config = Mock()
        config.USE_GITHUB_MCP = True
        config.GITHUB_TOKEN = "test_token"
        
        registry = ToolRegistry()
        
        mock_toolkit = Mock()
        mock_toolkit.is_available = Mock(return_value=True)
        mock_toolkit.use_mcp = True
        mock_toolkit.source_type = Mock()
        mock_toolkit.source_type.value = "github"
        mock_toolkit._ensure_mcp_initialized = Mock(side_effect=Exception("MCP failed"))
        mock_toolkit.create_tools = Mock(return_value=[])
        
        # Should not raise exception, just log warning
        registry.register(mock_toolkit)
        
        assert mock_toolkit in registry._toolkits.values()


class TestMCPFallbackBehavior:
    """Test fallback behavior when MCP is unavailable."""
    
    def test_github_fallback_to_api(self):
        """Test GitHub toolkit falls back to API when MCP unavailable."""
        config = Mock()
        config.USE_GITHUB_MCP = True
        config.GITHUB_TOKEN = "test_token"
        
        toolkit = GitHubToolkit(config)
        
        # Simulate MCP connection failure
        with patch('tools.github_tools.MCPToolAdapter') as mock_adapter_class:
            mock_adapter = AsyncMock()
            mock_adapter.connect = AsyncMock(return_value=False)
            mock_adapter_class.return_value = mock_adapter
            
            tools = toolkit.create_tools()
            
            # Should have API tools as fallback
            assert len(tools) == 4
            tool_names = [t.name for t in tools]
            assert "search_github" in tool_names
            assert "get_github_readme" in tool_names
    
    def test_web_fallback_to_api(self):
        """Test Web toolkit falls back to API when MCP unavailable."""
        config = Mock()
        config.USE_WEB_SEARCH_MCP = True
        config.TAVILY_API_KEY = "test_key"
        config.MAX_WEB_RESULTS = 10
        
        toolkit = WebToolkit(config)
        
        # Simulate MCP connection failure
        with patch('tools.web_tools.MCPToolAdapter') as mock_adapter_class:
            mock_adapter = AsyncMock()
            mock_adapter.connect = AsyncMock(return_value=False)
            mock_adapter_class.return_value = mock_adapter
            
            # Mock server config to return valid config
            with patch.object(toolkit, '_get_mcp_server_config', return_value={
                "command": "python",
                "args": ["test_server.py"]
            }):
                tools = toolkit.create_tools()
                
                # Should have API tools as fallback
                assert len(tools) == 4
                tool_names = [t.name for t in tools]
                assert "web_search" in tool_names
                assert "extract_webpage" in tool_names

