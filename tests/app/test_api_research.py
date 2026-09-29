import asyncio

import pytest

pytest.importorskip('multipart')

from fastapi.testclient import TestClient
from tests.app.fakes import (FakeChat, fresh, make_app, make_service, parse_sse, result_event, run_to_end,
                             submit)


def _conversation(client):
    response = client.post('/api/conversations', json={})
    assert response.status_code == 201, response.text
    return response.json()['id']


def test_research_streams_progress_then_presented_result(db):
    service = make_service(db)
    with TestClient(make_app(service, db)) as client:
        conversation = _conversation(client)
        run, events = run_to_end(client, conversation, '  transformers  ', 'request-1')
        assert run['query'] == 'transformers'
        assert [e['type'] for e in events] == ['progress', 'progress', 'progress', 'result']
        assert [e['seq'] for e in events] == [1, 2, 3, 4]
        assert events[1]['agents'] == ['arxiv', 'github']
        result = events[-1]['run']['result']
        assert result['answer'] == 'Transformers use attention.'
        assert result['sources'] == {'arxiv': 2, 'github': 1}
        assert [c['source_type'] for c in result['citations']] == ['arxiv', 'github']
        assert result['citations'][0]['authors'] == ['Vaswani', 'Shazeer']
        assert result['citations'][1]['repo'] == 'huggingface/transformers'
        assert result['can_preview_plan'] is True
        saved = client.get(f"/api/runs/{run['id']}").json()
        assert saved['status'] == 'completed'
        assert saved['result']['answer'] == result['answer']
    assert service.chat.queries == ['transformers']


def test_two_conversations_keep_distinct_results(db):
    chat = FakeChat(script=[
        [result_event('Answer one.', citations=[{'source_type': 'arxiv', 'title': 'One', 'url': 'https://a.example'}])],
        [result_event('Answer two.', citations=[{'source_type': 'web', 'title': 'Two', 'url': 'https://b.example'}])],
    ])
    with TestClient(make_app(make_service(db, chat=chat), db)) as client:
        first = _conversation(client)
        second = _conversation(client)
        run_to_end(client, first, 'question one', 'request-1')
        run_to_end(client, second, 'question two', 'request-1')
        left = client.get(f'/api/conversations/{first}').json()
        right = client.get(f'/api/conversations/{second}').json()
    assert [m['content'] for m in left['messages']] == ['question one', 'Answer one.']
    assert [m['content'] for m in right['messages']] == ['question two', 'Answer two.']
    assert left['runs'][0]['result']['citations'][0]['title'] == 'One'
    assert right['runs'][0]['result']['citations'][0]['title'] == 'Two'
    assert left['runs'][0]['id'] != right['runs'][0]['id']


def test_request_id_is_idempotent_and_repeat_text_is_not(db):
    service = make_service(db)
    with TestClient(make_app(service, db)) as client:
        conversation = _conversation(client)
        first, _ = run_to_end(client, conversation, 'same question', 'request-1')
        again = submit(client, conversation, 'same question', 'request-1')
        assert again.status_code == 202
        assert again.json()['id'] == first['id']
        second, _ = run_to_end(client, conversation, 'same question', 'request-2')
        assert second['id'] != first['id']
        detail = client.get(f'/api/conversations/{conversation}').json()
    assert [run['id'] for run in detail['runs']] == [first['id'], second['id']]
    assert service.chat.queries == ['same question', 'same question']


def test_error_event_is_saved_on_the_run(db):
    chat = FakeChat(events=[{'type': 'error', 'message': 'Connect Notion before searching your workspace.'}])
    with TestClient(make_app(make_service(db, chat=chat), db)) as client:
        conversation = _conversation(client)
        run, events = run_to_end(client, conversation, 'my notion notes', 'request-1')
        assert events == [{'type': 'error', 'message': 'Connect Notion before searching your workspace.',
                           'status': 'failed', 'seq': 1, 'run_id': run['id']}]
        saved = client.get(f"/api/runs/{run['id']}").json()
    assert saved['status'] == 'failed'
    assert saved['result'] is None


def test_clarification_reply_resumes_the_same_run(db):
    chat = FakeChat(script=[
        [result_event('Which field do you mean?', citations=[], needs_clarification=True)],
        [result_event('Transformers use attention.')],
    ])
    service = make_service(db, chat=chat)
    with TestClient(make_app(service, db)) as client:
        conversation = _conversation(client)
        run, events = run_to_end(client, conversation, 'it', 'request-1')
        assert events[-1]['run']['status'] == 'awaiting_clarification'
        assert events[-1]['run']['result']['can_preview_plan'] is False
        reply = client.post(f"/api/runs/{run['id']}/reply",
                            json={'message': 'natural language processing', 'request_id': 'request-2'})
        assert reply.status_code == 202
        assert reply.json()['id'] == run['id']
        followed = parse_sse(client.get(f"/api/runs/{run['id']}/events").text)
        assert followed[-1]['run']['status'] == 'completed'
        detail = client.get(f'/api/conversations/{conversation}').json()
    assert [m['content'] for m in detail['messages']] == [
        'it', 'Which field do you mean?', 'natural language processing', 'Transformers use attention.']
    assert chat.calls[1][2] is True


def test_new_run_supersedes_a_waiting_clarification(db):
    chat = FakeChat(script=[
        [result_event('Which field?', citations=[], needs_clarification=True)],
        [result_event('A different answer.')],
    ])
    with TestClient(make_app(make_service(db, chat=chat), db)) as client:
        conversation = _conversation(client)
        waiting, _ = run_to_end(client, conversation, 'it', 'request-1')
        _run, events = run_to_end(client, conversation, 'a new question', 'request-2')
        assert events[-1]['run']['status'] == 'completed'
        old = client.get(f"/api/runs/{waiting['id']}").json()
    assert old['status'] == 'superseded'


def test_empty_message_rejected(db):
    with TestClient(make_app(make_service(db), db)) as client:
        conversation = _conversation(client)
        assert submit(client, conversation, '', 'request-1').status_code == 422
        assert submit(client, conversation, '   ', 'request-1').status_code == 422


def test_replay_after_seq_skips_events_already_seen(db):
    with TestClient(make_app(make_service(db), db)) as client:
        conversation = _conversation(client)
        run, events = run_to_end(client, conversation, 'q', 'request-1')
        replay = parse_sse(client.get(f"/api/runs/{run['id']}/events", params={'after': events[1]['seq']}).text)
    assert [e['seq'] for e in replay] == [e['seq'] for e in events[2:]]


@pytest.mark.asyncio
async def test_concurrent_research_rejected_and_late_subscriber_replays(adb):
    gate = asyncio.Event()
    service = make_service(adb, chat=FakeChat(gate=gate))
    conversation = await service.create_conversation()
    run, created = await service.submit(conversation.id, 'first', 'request-1')
    assert created
    with pytest.raises(Exception, match='already running'):
        await service.submit(conversation.id, 'second', 'request-2')
    gate.set()
    first = [e async for e in service.subscribe(run.id)]
    late = [e async for e in service.subscribe(run.id)]
    assert [e['seq'] for e in first] == [e['seq'] for e in late]
    assert first[-1]['type'] == 'result'
    assert not service.running


def test_restart_marks_unfinished_run_interrupted_and_retry_uses_stable_checkpoint(db):
    gate = asyncio.Event()
    first = make_service(db, chat=FakeChat(events=[result_event(checkpoint='cp-stable')]))
    with TestClient(make_app(first, db)) as client:
        conversation = _conversation(client)
        run_to_end(client, conversation, 'established context', 'request-1')
    hanging = make_service(fresh(db), chat=FakeChat(gate=gate))
    with TestClient(make_app(hanging, hanging.repo.db)) as client:
        started = submit(client, conversation, 'still running', 'request-2')
        assert started.status_code == 202
        run_id = started.json()['id']
    retry_chat = FakeChat()
    retry_db = fresh(db)
    with TestClient(make_app(make_service(retry_db, chat=retry_chat), retry_db)) as client:
        interrupted = client.get(f'/api/runs/{run_id}').json()
        assert interrupted['status'] == 'interrupted'
        assert 'interrupted' in interrupted['error']
        retried, events = run_to_end(client, conversation, '', 'request-3', retry_of_run_id=run_id)
        assert events[-1]['run']['status'] == 'completed'
        detail = client.get(f'/api/conversations/{conversation}').json()
    assert retried['query'] == 'still running'
    assert any(m['content'] == 'established context' for m in detail['messages'])
    _message, config, resume = retry_chat.calls[0]
    assert resume is False
    assert config['configurable']['checkpoint_id'] == 'cp-stable'


def test_startup_sweeps_a_queued_run_left_by_a_dead_process(db):
    import psycopg
    with psycopg.connect(db.url, autocommit=True) as conn:
        conn.execute(f'SET search_path TO "{db.schema}"')
        conn.execute("INSERT INTO conversations (id, title, thread_id) VALUES ('c-1', 'Kept', 'thread-1')")
        conn.execute("INSERT INTO research_runs (id, conversation_id, request_id, status, query, thread_id) "
                     "VALUES ('r-1', 'c-1', 'request-9', 'queued', 'unfinished question', 'thread-1')")
    with TestClient(make_app(make_service(db), db)) as client:
        saved = client.get('/api/runs/r-1').json()
        history = client.get('/api/conversations/c-1').json()
    assert saved['status'] == 'interrupted'
    assert saved['query'] == 'unfinished question'
    assert history['messages'][-1]['role'] == 'error'


def test_reload_replays_a_finished_run_without_executing_again(db):
    service = make_service(db)
    with TestClient(make_app(service, db)) as client:
        conversation = _conversation(client)
        run, _ = run_to_end(client, conversation, 'transformers', 'request-1')
    reloaded = fresh(db)
    with TestClient(make_app(make_service(reloaded, chat=FakeChat()), reloaded)) as client:
        replay = parse_sse(client.get(f"/api/runs/{run['id']}/events").text)
        assert replay[-1]['run']['result']['answer'] == 'Transformers use attention.'
    assert service.chat.queries == ['transformers']


@pytest.mark.asyncio
async def test_disconnect_keeps_history_and_rotates_the_next_thread(adb):
    from tests.app.fakes import fake_notion
    notion = fake_notion('g1')
    flags = []

    class Rag:
        llm = object()
        tool_registry = type('R', (), {'available_ids': lambda self: ['arxiv']})()

        def invalidate_graph(self):
            flags.append('invalidated')

    service = make_service(adb, backend='mcp', chat=FakeChat(), notion=notion)
    service.rag = Rag()
    conversation = await service.create_conversation()
    run, _ = await service.submit(conversation.id, 'notes about MCP', 'request-1')
    assert [e async for e in service.subscribe(run.id)][-1]['type'] == 'result'
    detail = await service.conversation_detail(conversation.id)
    assert [m.content for m in detail[1]] == ['notes about MCP', 'Transformers use attention.']
    thread_before = detail[0].thread_id
    notion.connection.connected = False
    notion.connection.generation = None
    await service.invalidate()
    assert flags == ['invalidated']
    assert (await service.conversation_detail(conversation.id))[1]
    notion.connection.connected = True
    notion.connection.generation = 'g2'
    run, _ = await service.submit(conversation.id, 'after reconnect', 'request-2')
    assert [e async for e in service.subscribe(run.id)][-1]['type'] == 'result'
    detail = await service.conversation_detail(conversation.id)
    assert detail[0].thread_id != thread_before
    assert [m.content for m in detail[1] if m.role == 'user'] == ['notes about MCP', 'after reconnect']
