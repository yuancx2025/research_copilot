import sys
from pathlib import Path
import httpx
import pytest
from langchain_core.tools import ToolException
from research_copilot.tools.mcp.adapter import MCPToolAdapter
from research_copilot.tools.mcp.config import parse_server_config, HttpConfig
from research_copilot.tools.mcp.client import create_client


@pytest.mark.asyncio
async def test_real_stdio_schema_result_error_and_reuse():
    adapter = MCPToolAdapter('fixture', {'command': [sys.executable, str(Path(__file__).with_name('fixture_server.py'))]})
    tools = {t.name: t for t in await adapter.create_langchain_tools()}
    total = tools['fixture_total']
    assert '$defs' in total.args_schema
    await adapter.disconnect()
    # Connection-backed executors remain valid after discovery disconnects.
    for _ in range(2):
        result = await total.ainvoke({'type':'tool_call', 'id':'call-1', 'name':total.name,
                                     'args':{'items':[{'name':'a','count':2},{'name':'b','count':3}]}})
        assert result.artifact == {'structured_content': {'total':5}}
        assert '5' in str(result.content)
    with pytest.raises(ToolException):
        await tools['fixture_fail'].ainvoke({})


@pytest.mark.asyncio
async def test_http_transport_with_real_sdk():
    from tests.mcp.fixture_server import mcp
    app = mcp.streamable_http_app()
    def factory(**kwargs):
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), **kwargs)
    client = create_client('fixture', HttpConfig(url='http://127.0.0.1:8000/mcp', httpx_client_factory=factory))
    async with mcp.session_manager.run():
        tools = {t.name:t for t in await client.get_tools()}
        result = await tools['fixture_total'].ainvoke({'items':[{'name':'x','count':7}]})
    assert '7' in str(result)


def test_legacy_config_and_invalid_transport():
    config = parse_server_config({'command':'python,-m,server', 'args':['--flag']})
    assert config.command == 'python' and config.args == ['-m','server','--flag']
    with pytest.raises(ValueError):
        parse_server_config({'command':[]})
