import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import pytest
from langchain_core.messages import ToolMessage, AIMessage
from research_copilot.notion.notion_mcp_service import NotionMCPService, payload, page_id
from research_copilot.tools.notion_tools import NotionToolkit
from research_copilot.tools.mcp.client import AuthorizationRequired, MCPToolError
from research_copilot.agents.notion_agent import NotionAgent
from tests.mcp.test_oauth import MemoryStore, record
from research_copilot.tools.mcp.oauth import ConnectionService

PAGE = '11111111-2222-3333-4444-555555555555'
EVIDENCE = dict(id=PAGE, title='My notes', url=f'https://www.notion.so/{PAGE}', type='page', text='Fetched evidence')


def fake_tool(name, value):
    async def invoke(call):
        return ToolMessage(content=json.dumps(value), tool_call_id=call['id'])
    return SimpleNamespace(name='notion_'+name, ainvoke=AsyncMock(side_effect=invoke))


async def connected_service(access='available'):
    connection = ConnectionService(MemoryStore(record()))
    await connection.initialize()
    service = NotionMCPService(connection)
    tools = [fake_tool('notion-fetch', {'self':{'workspace':{'id':'workspace','name':'Notes'},
             'current_tool_access':{'ai_search':{'status':access}}}}),
             fake_tool('notion-search', {'results':[EVIDENCE]}),
             fake_tool('notion-ai-search', {'results':[EVIDENCE]}),
             fake_tool('notion-create-pages', {'pages':[EVIDENCE]})]
    with patch('research_copilot.notion.notion_mcp_service.create_client',
               return_value=SimpleNamespace(get_tools=AsyncMock(return_value=tools))):
        await service.prepare()
    return service, {t.name.removeprefix('notion_'):t for t in tools}


@pytest.mark.asyncio
@pytest.mark.parametrize('access, selected', [('available','notion-ai-search'), ('upgrade_required','notion-search')])
async def test_capabilities_and_read_only_exposure(access, selected):
    service, tools = await connected_service(access)
    await service.search('Notes')
    tools[selected].ainvoke.assert_awaited_once()
    assert service.connection.record.workspace_name == 'Notes'
    agent_tools = NotionToolkit(service).create_tools()
    assert {t.name for t in agent_tools} == {'notion_search', 'notion_fetch'}
    old_tool = agent_tools[0]
    await service.connection.disconnect()
    assert not service.tools and not service.identity
    with pytest.raises(AuthorizationRequired):
        await old_tool.ainvoke({'query':'Notes'})


@pytest.mark.asyncio
async def test_old_tool_cannot_use_replacement_connection():
    service, _ = await connected_service()
    old = NotionToolkit(service).create_tools()[0]
    service.connection.record = service.connection.record.model_copy(update={'generation':'new'})
    service.generation = 'new'
    with pytest.raises(AuthorizationRequired):
        await old.ainvoke({'query':'notes'})


def test_only_fetched_pages_become_citations():
    agent = NotionAgent(None, SimpleNamespace(connection=SimpleNamespace(generation='g')))
    assert agent.parse_citation('notion_search', {}, EVIDENCE) is None
    assert agent.parse_citation('notion_fetch', {}, {'title':'Search snippet'}) is None
    call = dict(name='notion_fetch', args={'id':PAGE}, id='fetch-1', type='tool_call')
    result = agent.extract_answer_with_citations({'messages':[
        AIMessage(content='', tool_calls=[call]),
        ToolMessage(content=json.dumps(EVIDENCE), tool_call_id='fetch-1'), AIMessage(content='Answer')]})
    citation = result['agent_answers'][0]['citations'][0]
    assert citation['metadata'] == {'page_id':PAGE, 'fetched':True}
    assert citation['url'] == EVIDENCE['url']


def test_structured_content_and_errors():
    assert payload(ToolMessage(content='text', artifact={'structured_content':EVIDENCE}, tool_call_id='id')) == EVIDENCE
    with pytest.raises(MCPToolError):
        payload(ToolMessage(content='rejected', status='error', tool_call_id='id'))
    assert page_id(EVIDENCE['url']) == PAGE
    with pytest.raises(ValueError):
        page_id('https://evil.test/'+PAGE)


@pytest.mark.asyncio
async def test_destination_requires_fetched_page():
    service, _ = await connected_service()
    service.fetch = AsyncMock(return_value=EVIDENCE)
    assert await service.destination(EVIDENCE['url']) == PAGE
    service.fetch.return_value = {'type':'database'}
    with pytest.raises(ValueError):
        await service.destination(PAGE)

