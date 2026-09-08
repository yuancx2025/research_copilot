from types import SimpleNamespace
from langchain_core.messages import AIMessage
import pytest
from research_copilot.orchestrator.intent import explicit_notion_request, keyword_agents
from research_copilot.orchestrator.nodes import classify_research_intent
from research_copilot.orchestrator.edges import route_to_agents
from research_copilot.core.chat_interface import ChatInterface


@pytest.mark.parametrize('message, expected', [
    ('I have a notion that transformers are useful', False),
    ('search my Notion notes about MCP', True),
    ('what did I write in Notion', True),
    ('Connect Notion', True),
    ('latest arxiv papers on attention', False),
])
def test_explicit_notion_request_ignores_idiom(message, expected):
    assert explicit_notion_request(message) is expected


def test_keyword_fallback_keeps_notion_off_when_disconnected():
    selected = keyword_agents('transformer papers', ['arxiv', 'web', 'local'])
    assert 'notion' not in selected
    assert 'arxiv' in selected


def test_keyword_fallback_includes_notion_for_workspace_queries():
    selected = keyword_agents('what did I write about MCP in Notion', ['arxiv', 'web', 'local', 'notion'])
    assert 'notion' in selected


class _NoneLLM:
    def with_config(self, **kwargs):
        return self
    def with_structured_output(self, schema):
        return self
    def invoke(self, messages):
        return None


class _NotionLLM:
    def with_config(self, **kwargs):
        return self
    def with_structured_output(self, schema):
        return self
    def invoke(self, messages):
        return SimpleNamespace(agents=['arxiv', 'web'], reasoning='public sources', confidence=0.9,
                               suggested_queries=None)


def test_classify_does_not_select_notion_when_unavailable():
    result = classify_research_intent({
        'originalQuery': 'what did I write about MCP in Notion',
        'available_sources': ['arxiv', 'web', 'local'],
        'messages': [],
    }, _NoneLLM())
    assert 'notion' not in result['research_intent']


def test_classify_adds_notion_when_connected_even_if_llm_omits_it():
    result = classify_research_intent({
        'originalQuery': 'compare arxiv papers on MCP with my Notion notes',
        'available_sources': ['arxiv', 'web', 'local', 'notion'],
        'messages': [],
    }, _NotionLLM())
    assert 'notion' in result['research_intent']
    assert 'arxiv' in result['research_intent']


def test_route_drops_notion_when_not_available():
    sends = route_to_agents({
        'research_intent': ['notion', 'web'],
        'available_sources': ['web', 'local'],
        'rewrittenQuestions': ['transformer papers'],
        'cache_enabled': False,
        'cached_results': {},
    })
    assert {send.node for send in sends} == {'web_agent'}


@pytest.mark.asyncio
async def test_disconnected_explicit_notion_request_does_not_run_research():
    rag = SimpleNamespace(
        llm=object(),
        notion_service=None,
        _graph_generation=None,
        tool_registry=SimpleNamespace(list_available_sources=lambda: []),
        agent_graph=SimpleNamespace(ainvoke=None),
        get_config=lambda: {},
    )
    async def prepare_run(notion):
        return None
    rag.prepare_run = prepare_run
    answer, data = await ChatInterface(rag).chat('search my Notion notes', [])
    assert 'Connect Notion' in answer
    assert data == {}


@pytest.mark.asyncio
async def test_ordinary_research_ignores_idiomatic_notion():
    invoked = {}
    async def ainvoke(state, config):
        invoked['state'] = state
        return {'messages': [AIMessage(content='ok')], 'citations': [], 'agent_results': {}}
    rag = SimpleNamespace(
        llm=object(),
        notion_service=None,
        _graph_generation=None,
        tool_registry=SimpleNamespace(list_available_sources=lambda: []),
        agent_graph=SimpleNamespace(ainvoke=ainvoke),
        get_config=lambda: {},
    )
    async def prepare_run(notion):
        return None
    rag.prepare_run = prepare_run
    answer, data = await ChatInterface(rag).chat('I have a notion that transformers are useful', [])
    assert answer == 'ok'
    assert 'notion' not in invoked['state']['available_sources']
