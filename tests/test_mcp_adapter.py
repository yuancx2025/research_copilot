"""Compatibility facade tests; transport coverage is in tests/mcp/test_clients.py."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import pytest
from research_copilot.tools.mcp.adapter import MCPToolAdapter
from research_copilot.tools.mcp.client import MCPConnectionError, AuthorizationRequired


@pytest.mark.asyncio
async def test_cache_schema_and_disconnect():
    schema = {'type': 'object', 'properties': {'filter': {'anyOf':[{'type':'string'}, {'type':'null'}]}}}
    tool = SimpleNamespace(name='server_search', description='Search', args_schema=schema)
    client = SimpleNamespace(get_tools=AsyncMock(return_value=[tool]))
    with patch('research_copilot.tools.mcp.adapter.create_client', return_value=client):
        adapter = MCPToolAdapter('server', {'command': ['python', '-m', 'fixture']})
    assert not hasattr(adapter, 'session')
    assert await adapter.connect()
    assert await adapter.create_langchain_tools() == [tool]
    assert (await adapter.discover_tools())[0]['input_schema'] == schema
    client.get_tools.assert_awaited_once()
    await adapter.disconnect()
    await adapter.connect()
    assert client.get_tools.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize('error, expected', [(OSError('secret response'), MCPConnectionError),
                                            (AuthorizationRequired('Connect first'), AuthorizationRequired)])
async def test_discovery_errors(error, expected):
    with patch('research_copilot.tools.mcp.adapter.create_client') as create:
        create.return_value.get_tools = AsyncMock(side_effect=error)
        adapter = MCPToolAdapter('server', {'command':'python'})
        with pytest.raises(expected) as exc:
            await adapter.connect()
        assert 'secret response' not in str(exc.value)
