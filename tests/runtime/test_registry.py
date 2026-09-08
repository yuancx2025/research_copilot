"""Tests for the source-independent SourceRegistry."""
from unittest.mock import Mock
from langchain_core.tools import tool
from research_copilot.runtime.base_toolkit import BaseToolkit
from research_copilot.runtime.schemas import SourceType
from research_copilot.runtime.source_registry import SourceRegistry, SourceDescriptor, SourceContext
from research_copilot.core.source_setup import build_source_registry


class MockToolkit(BaseToolkit):
    source_type = SourceType.LOCAL

    def __init__(self, config, available=True):
        self.config = config
        self._available = available

    def create_tools(self):
        @tool
        def mock_tool():
            """Mock tool for testing."""
            return "mock"
        return [mock_tool]

    def is_available(self):
        return self._available


def _descriptor(source_id, toolkit, is_default=True):
    return SourceDescriptor(
        id=source_id,
        node_name=f"{source_id}_agent",
        is_default=is_default,
        is_available=lambda ctx: toolkit.is_available(),
        create_toolkit=lambda ctx: toolkit,
        create_agent=lambda ctx, tools: None,
    )


class TestSourceRegistry:
    def test_instances_are_independent(self):
        assert SourceRegistry() is not SourceRegistry()

    def test_register_and_build_toolkit(self):
        registry = SourceRegistry()
        toolkit = MockToolkit(Mock(), available=True)
        registry.register(_descriptor("local", toolkit))
        registry.ensure_toolkits(SourceContext(llm=None, config=Mock()))
        assert registry.get_toolkit("local") is toolkit
        assert len(registry.tools_for("local")) == 1

    def test_unavailable_toolkit_is_not_built(self):
        registry = SourceRegistry()
        toolkit = MockToolkit(Mock(), available=False)
        registry.register(_descriptor("local", toolkit))
        registry.ensure_toolkits(SourceContext(llm=None, config=Mock()))
        assert registry.get_toolkit("local") is None

    def test_tools_for_one_source(self):
        registry = SourceRegistry()
        local = MockToolkit(Mock(), available=True)
        arxiv = MockToolkit(Mock(), available=True)
        arxiv.source_type = SourceType.ARXIV
        registry.register(_descriptor("local", local))
        registry.register(_descriptor("arxiv", arxiv))
        registry.ensure_toolkits(SourceContext(llm=None, config=Mock()))
        assert len(registry.tools_for("local")) == 1
        assert registry.available_ids() == ["local", "arxiv"]

    def test_default_ids(self):
        registry = SourceRegistry()
        local = MockToolkit(Mock(), available=True)
        notion = MockToolkit(Mock(), available=True)
        notion.source_type = SourceType.NOTION
        registry.register(_descriptor("local", local, is_default=True))
        registry.register(_descriptor("notion", notion, is_default=False))
        registry.ensure_toolkits(SourceContext(llm=None, config=Mock()))
        assert registry.default_ids() == ["local"]

    def test_clear_registry(self):
        registry = SourceRegistry()
        registry.register(_descriptor("local", MockToolkit(Mock(), available=True)))
        registry.ensure_toolkits(SourceContext(llm=None, config=Mock()))
        registry.clear()
        assert registry.available_ids() == []
        assert registry.get_toolkit("local") is None


class TestBuildSourceRegistry:
    def test_local_is_registered_when_collection_present(self):
        config = Mock()
        config.ENABLE_ARXIV_AGENT = True
        config.ENABLE_YOUTUBE_AGENT = False
        config.ENABLE_GITHUB_AGENT = False
        config.ENABLE_WEB_AGENT = False
        config.ENABLE_LOCAL_AGENT = True
        registry = build_source_registry()
        ctx = SourceContext(llm=None, config=config, collection=object())
        registry.ensure_toolkits(ctx)
        assert "local" in registry.available_ids()
        assert "youtube" not in registry.available_ids()
