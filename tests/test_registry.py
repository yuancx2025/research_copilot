"""
Tests for tools/registry.py - Tool registry and initialization
"""
import pytest
from unittest.mock import Mock, MagicMock
from tools.registry import ToolRegistry, initialize_registry
from tools.base import BaseToolkit, SourceType


class MockToolkit(BaseToolkit):
    """Mock toolkit for testing"""
    source_type = SourceType.LOCAL
    
    def __init__(self, config, available=True):
        self.config = config
        self._available = available
    
    def create_tools(self):
        from langchain_core.tools import tool
        @tool
        def mock_tool():
            """Mock tool for testing."""
            return "mock"
        return [mock_tool]
    
    def is_available(self):
        return self._available


class TestToolRegistry:
    """Test ToolRegistry class"""
    
    def test_singleton_pattern(self):
        """Test that ToolRegistry is a singleton"""
        registry1 = ToolRegistry()
        registry2 = ToolRegistry()
        
        assert registry1 is registry2
    
    def test_register_toolkit(self):
        """Test registering a toolkit"""
        registry = ToolRegistry()
        registry.clear()  # Clear for clean test
        
        config = Mock()
        toolkit = MockToolkit(config, available=True)
        
        registry.register(toolkit)
        
        assert SourceType.LOCAL in registry._toolkits
        assert registry.get_toolkit(SourceType.LOCAL) == toolkit
    
    def test_register_unavailable_toolkit(self):
        """Test that unavailable toolkits are not registered"""
        registry = ToolRegistry()
        registry.clear()
        
        config = Mock()
        toolkit = MockToolkit(config, available=False)
        
        registry.register(toolkit)
        
        assert SourceType.LOCAL not in registry._toolkits
    
    def test_get_all_tools(self):
        """Test getting all tools from registry"""
        registry = ToolRegistry()
        registry.clear()
        
        config = Mock()
        toolkit1 = MockToolkit(config, available=True)
        toolkit1.source_type = SourceType.LOCAL
        
        toolkit2 = MockToolkit(config, available=True)
        toolkit2.source_type = SourceType.ARXIV
        
        registry.register(toolkit1)
        registry.register(toolkit2)
        
        tools = registry.get_all_tools()
        
        assert len(tools) == 2  # One tool from each toolkit
    
    def test_get_tools_for_sources(self):
        """Test getting tools for specific sources"""
        registry = ToolRegistry()
        registry.clear()
        
        config = Mock()
        toolkit1 = MockToolkit(config, available=True)
        toolkit1.source_type = SourceType.LOCAL
        
        toolkit2 = MockToolkit(config, available=True)
        toolkit2.source_type = SourceType.ARXIV
        
        registry.register(toolkit1)
        registry.register(toolkit2)
        
        tools = registry.get_tools_for_sources([SourceType.LOCAL])
        
        assert len(tools) == 1
    
    def test_list_available_sources(self):
        """Test listing available sources"""
        registry = ToolRegistry()
        registry.clear()
        
        config = Mock()
        toolkit1 = MockToolkit(config, available=True)
        toolkit1.source_type = SourceType.LOCAL
        
        toolkit2 = MockToolkit(config, available=True)
        toolkit2.source_type = SourceType.ARXIV
        
        registry.register(toolkit1)
        registry.register(toolkit2)
        
        sources = registry.list_available_sources()
        
        assert SourceType.LOCAL in sources
        assert SourceType.ARXIV in sources
        assert len(sources) == 2
    
    def test_clear_registry(self):
        """Test clearing the registry"""
        registry = ToolRegistry()
        registry.clear()
        
        config = Mock()
        toolkit = MockToolkit(config, available=True)
        registry.register(toolkit)
        
        assert len(registry._toolkits) > 0
        
        registry.clear()
        
        assert len(registry._toolkits) == 0
        assert registry._tools_cache is None


class TestInitializeRegistry:
    """Test initialize_registry function"""
    
    def test_initialize_with_config(self):
        """Test initializing registry with config"""
        config = Mock()
        config.ENABLE_ARXIV_AGENT = True
        config.ENABLE_YOUTUBE_AGENT = False
        config.ENABLE_GITHUB_AGENT = False
        config.ENABLE_WEB_AGENT = False
        
        # This will try to import actual toolkits, so we'll mock them
        # In real usage, this would work with actual implementations
        registry = initialize_registry(config)
        
        assert isinstance(registry, ToolRegistry)
        # Local toolkit should always be registered
        assert SourceType.LOCAL in registry.list_available_sources()

