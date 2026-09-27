import asyncio
import pytest

pytest.importorskip('multipart')

from fastapi.testclient import TestClient
from tests.app.fakes import FakeChat, make_app, make_service, parse_sse


@pytest.fixture(autouse=True)
def _data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('RESEARCH_COPILOT_DATA_DIR', str(tmp_path))


def test_research_streams_progress_then_presented_result():
    service = make_service()
    with TestClient(make_app(service)) as client:
        response = client.post('/api/research', json={'message': '  transformers  '})
        assert response.status_code == 200
        assert response.headers['content-type'].startswith('text/event-stream')
        events = parse_sse(response.text)

    assert [e['type'] for e in events] == ['progress', 'progress', 'progress', 'result']
    assert events[1]['agents'] == ['arxiv', 'github']
    result = events[-1]
    assert result['answer'] == 'Transformers use attention.'
    assert result['sources'] == {'arxiv': 2, 'github': 1}
    assert [c['source_type'] for c in result['citations']] == ['arxiv', 'github']
    assert result['citations'][0]['authors'] == ['Vaswani', 'Shazeer']
    assert result['citations'][1]['repo'] == 'huggingface/transformers'
    assert result['can_preview_plan'] is True
    assert service.chat.queries == ['transformers']
    assert service.last.research_data['answer_text'] == 'Transformers use attention.'


def test_last_research_and_reset():
    service = make_service()
    with TestClient(make_app(service)) as client:
        assert client.get('/api/research/last').json() == {'running': False, 'result': None}
        client.post('/api/research', json={'message': 'q'})
        last = client.get('/api/research/last').json()
        assert last['running'] is False and last['result']['query'] == 'q'
        assert client.post('/api/session/reset').status_code == 204
        assert client.get('/api/research/last').json()['result'] is None
    assert service.chat.cleared == 1


def test_error_event_clears_last_result():
    chat = FakeChat(events=[{'type': 'error', 'message': 'Connect Notion before searching your workspace.'}])
    service = make_service(chat=chat)
    service.last = object()
    with TestClient(make_app(service)) as client:
        events = parse_sse(client.post('/api/research', json={'message': 'my notion notes'}).text)
    assert events == [{'type': 'error', 'message': 'Connect Notion before searching your workspace.'}]
    assert service.last is None


def test_clarification_is_flagged_and_not_previewable():
    chat = FakeChat(events=[{'type': 'result', 'answer': 'Which field do you mean?', 'needs_clarification': True,
                             'research_data': {'citations': [], 'agent_results': {}}}])
    with TestClient(make_app(make_service(chat=chat))) as client:
        result = parse_sse(client.post('/api/research', json={'message': 'it'}).text)[-1]
    assert result['needs_clarification'] is True
    assert result['can_preview_plan'] is False


def test_empty_message_rejected():
    with TestClient(make_app(make_service())) as client:
        assert client.post('/api/research', json={'message': ''}).status_code == 422
        assert client.post('/api/research', json={'message': '   '}).status_code == 422


@pytest.mark.asyncio
async def test_concurrent_research_rejected_and_late_subscriber_replays():
    gate = asyncio.Event()
    service = make_service(chat=FakeChat(gate=gate))
    run = service.start_research('first')
    with pytest.raises(Exception, match='already running'):
        service.start_research('second')
    with pytest.raises(Exception, match='Wait for the current research'):
        await service.reset()
    gate.set()
    first = [e async for e in run.subscribe()]
    late = [e async for e in run.subscribe()]
    assert [e['type'] for e in first] == [e['type'] for e in late]
    assert first[-1]['type'] == 'result'
    assert not service.running


@pytest.mark.asyncio
async def test_connection_invalidation_clears_research_and_drafts():
    reset = []
    service = make_service()
    service.rag.reset_thread = lambda: reset.append(True)
    run = service.start_research('q')
    [e async for e in run.subscribe()]
    service.drafts['d'] = object()
    await service.invalidate()
    assert service.last is None and service.drafts == {}
    assert reset == [True] and service.rag.agent_graph is None
