from types import SimpleNamespace
import pytest
from langchain_core.messages import AIMessage
from research_copilot.core.chat_interface import ChatInterface, graph_config


def _rag(chunks, values):
    async def astream(state, config, stream_mode):
        assert stream_mode == 'updates'
        for chunk in chunks:
            yield chunk

    async def aget_state(config):
        return SimpleNamespace(values=values, config={'configurable': {'checkpoint_id': 'cp-1'}})

    async def prepare_run(notion):
        return None

    return SimpleNamespace(
        llm=object(), notion_service=None, _graph_generation=None, prepare_run=prepare_run,
        tool_registry=SimpleNamespace(available_ids=lambda: ['arxiv', 'web']),
        agent_graph=SimpleNamespace(astream=astream, aget_state=aget_state), get_config=lambda: {},
    )


async def _collect(rag, message='q', **kwargs):
    return [event async for event in ChatInterface(rag).chat_stream(message, graph_config('thread-1'), **kwargs)]


@pytest.mark.asyncio
async def test_progress_events_map_graph_nodes():
    rag = _rag(
        [{'summarize': {}}, {'analyze_rewrite': {'questionIsClear': True}},
         {'classify_intent': {'research_intent': ['arxiv', 'web']}},
         {'arxiv_agent': {'agent_answers': []}}, {'web_agent': {}}, {'aggregate': {}}],
        {'messages': [AIMessage(content=[{'type': 'text', 'text': 'answer'}])], 'questionIsClear': True,
         'citations': [{'title': 't'}], 'agent_results': {'arxiv': [1]}},
    )
    events = await _collect(rag)
    assert events[:-1] == [
        {'type': 'progress', 'node': 'prepare'},
        {'type': 'progress', 'node': 'summarize'},
        {'type': 'progress', 'node': 'analyze_rewrite', 'clear': True},
        {'type': 'progress', 'node': 'classify_intent', 'agents': ['arxiv', 'web']},
        {'type': 'progress', 'node': 'arxiv_agent', 'source': 'arxiv'},
        {'type': 'progress', 'node': 'web_agent', 'source': 'web'},
        {'type': 'progress', 'node': 'aggregate'},
    ]
    result = events[-1]
    assert result['type'] == 'result' and result['answer'] == 'answer'
    assert result['needs_clarification'] is False
    assert result['checkpoint_id'] == 'cp-1'
    assert result['research_data']['sources'] == ['arxiv']
    assert result['research_data']['citation_count'] == 1


@pytest.mark.asyncio
async def test_resume_continues_from_human_input():
    seen = {}

    async def aupdate_state(config, values, as_node):
        seen['as_node'] = as_node
        seen['reply'] = values['messages'][-1].content
        return {'configurable': {**config['configurable'], 'checkpoint_id': 'cp-2'}}

    async def astream(inputs, config, stream_mode):
        seen['inputs'] = inputs
        seen['checkpoint'] = config['configurable']['checkpoint_id']
        yield {'aggregate': {}}

    rag = _rag([], {'messages': [AIMessage(content='answer')], 'questionIsClear': True,
                    'citations': [], 'agent_results': {}})
    rag.agent_graph.aupdate_state = aupdate_state
    rag.agent_graph.astream = astream
    events = await _collect(rag, 'the NLP one', resume=True)
    assert seen == {'as_node': 'human_input', 'reply': 'the NLP one', 'inputs': None, 'checkpoint': 'cp-2'}
    assert events[-1]['type'] == 'result'


@pytest.mark.asyncio
async def test_interrupt_becomes_clarification():
    rag = _rag(
        [{'summarize': {}}, {'analyze_rewrite': {'questionIsClear': False}}, {'__interrupt__': ()}],
        {'messages': [AIMessage(content='Which model family?')], 'questionIsClear': False},
    )
    events = await _collect(rag, 'compare them')
    assert events[-1]['type'] == 'result'
    assert events[-1]['answer'] == 'Which model family?'
    assert events[-1]['needs_clarification'] is True
    assert all(e.get('node') != '__interrupt__' for e in events)


@pytest.mark.asyncio
async def test_graph_failure_yields_error_event():
    async def astream(state, config, stream_mode):
        raise RuntimeError('boom')
        yield
    rag = _rag([], {})
    rag.agent_graph.astream = astream
    events = await _collect(rag)
    assert events[-1] == {'type': 'error', 'message': 'Research could not complete. Check the model and source connections, then retry.'}
