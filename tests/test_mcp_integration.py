"""Async startup owns connections; constructors only expose prepared tools."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import pytest
from research_copilot.sources.github.tools import GitHubToolkit
from research_copilot.sources.web.tools import WebToolkit
from research_copilot.runtime.source_registry import SourceRegistry, SourceDescriptor, SourceContext


def _wrap(kit):
    source_id = kit.source_type.value
    return SourceDescriptor(
        id=source_id,
        node_name=f"{source_id}_agent",
        is_default=True,
        is_available=lambda ctx: True,
        create_toolkit=lambda ctx: kit,
        create_agent=lambda ctx, tools: None,
    )


@pytest.mark.parametrize('toolkit, settings', [
    (GitHubToolkit, dict(USE_GITHUB_MCP=True, GITHUB_MCP_COMMAND=['python'])),
    (WebToolkit, dict(USE_WEB_SEARCH_MCP=True, WEB_SEARCH_MCP_COMMAND=['python'], TAVILY_API_KEY='fake')),
])
@pytest.mark.asyncio
async def test_prepare_once_without_constructor_io(toolkit, settings):
    kit = toolkit(SimpleNamespace(**settings))
    executor = SimpleNamespace(name='mcp_search')
    with patch('research_copilot.runtime.mcp.adapter.MCPToolAdapter') as cls:
        adapter = cls.return_value
        adapter.connect = AsyncMock(return_value=True)
        adapter.create_langchain_tools = AsyncMock(return_value=[executor])
        registry = SourceRegistry()
        registry.register(_wrap(kit))
        registry.ensure_toolkits(SourceContext(llm=None, config=None))
        kit.create_tools()
        cls.assert_not_called()
        await registry.initialize_mcp()
        assert kit.create_tools() == [executor]
        await registry.initialize_mcp()
        adapter.connect.assert_awaited_once()


@pytest.mark.asyncio
async def test_optional_github_failure_keeps_rest_fallback():
    kit = GitHubToolkit(SimpleNamespace(USE_GITHUB_MCP=True, GITHUB_MCP_COMMAND=['python']))
    registry = SourceRegistry()
    registry.register(_wrap(kit))
    registry.ensure_toolkits(SourceContext(llm=None, config=None))
    with patch.object(kit, '_ensure_mcp_initialized', AsyncMock(side_effect=OSError('offline'))):
        await registry.initialize_mcp()
    assert any(t.name == 'search_github' for t in kit.create_tools())
