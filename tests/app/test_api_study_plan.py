import pytest

pytest.importorskip('multipart')

from fastapi.testclient import TestClient
from research_copilot.study_plans.schemas import StudyPlan, StudyPlanDraft
from tests.app.fakes import make_app, make_service, run_to_end


@pytest.fixture
def fake_generate(monkeypatch):
    calls = []

    async def generate_draft(research_data, query, llm, config, generation):
        calls.append((query, generation, research_data['answer_text']))
        plan = StudyPlan(title='Transformers plan', overview='o', outcome_objectives=[], phases=[],
                         citations=[], next_steps=[])
        return StudyPlanDraft(plan=plan, markdown='# Transformers plan', connection_generation=generation)

    monkeypatch.setattr('research_copilot.core.research_service.generate_draft', generate_draft)
    return calls


def _conversation(client):
    return client.post('/api/conversations', json={}).json()['id']


def test_preview_requires_research_first(db, fake_generate):
    with TestClient(make_app(make_service(db), db)) as client:
        response = client.post('/api/study-plan/preview', json={'run_id': 'missing-run'})
    assert response.status_code == 404
    assert fake_generate == []


def test_saved_preview_reloads_and_exports_stored_markdown(db, fake_generate):
    service = make_service(db)
    with TestClient(make_app(service, db)) as client:
        conversation = _conversation(client)
        run, _events = run_to_end(client, conversation, 'transformers', 'request-1')
        missing = client.post('/api/study-plan/preview', json={'run_id': run['id']})
        draft = missing.json()
        assert missing.status_code == 200
        assert draft['title'] == 'Transformers plan' and draft['markdown'] == '# Transformers plan'
        assert draft['run_id'] == run['id']
        assert fake_generate == [('transformers', 'rest', 'Transformers use attention.')]

        stored = client.get(f"/api/study-plan/drafts/{draft['draft_id']}").json()
        assert stored['markdown'] == '# Transformers plan'

        forged = client.post('/api/study-plan/export', json={'draft_id': 'forged', 'destination': 'p'}).json()
        assert forged['status'] == 'failure' and forged['retryable'] is True

        result = client.post('/api/study-plan/export',
                             json={'draft_id': draft['draft_id'], 'destination': 'parent-page'}).json()
        assert result == {'status': 'success', 'page_id': 'page-1', 'url': 'https://notion.so/page-1',
                          'message': '', 'retryable': False}
        detail = client.get(f'/api/conversations/{conversation}').json()

    published, destination = service.exporter.published[0]
    assert published.draft_id == draft['draft_id'] and published.markdown == '# Transformers plan'
    assert destination == 'parent-page'
    assert detail['drafts'][0]['draft_id'] == draft['draft_id']


def test_stale_connection_blocks_preview_and_export_but_keeps_the_draft(db, fake_generate):
    from unittest.mock import AsyncMock
    from research_copilot.sources.notion.exporter import ExportService
    from research_copilot.storage.export_store import PostgresExportLedger
    from tests.app.fakes import fake_notion
    from types import SimpleNamespace
    notion = fake_notion('g1')
    notion.destination = AsyncMock(return_value='parent-page')
    notion.create_page = AsyncMock(return_value={'pages': [{'id': 'page-1', 'url': 'https://notion.so/page-1'}]})
    exporter = ExportService(PostgresExportLedger(db), notion, SimpleNamespace(NOTION_BACKEND='mcp'))
    service = make_service(db, backend='mcp', notion=notion, exporter=exporter)
    with TestClient(make_app(service, db)) as client:
        conversation = _conversation(client)
        run, _events = run_to_end(client, conversation, 'transformers', 'request-1')
        draft = client.post('/api/study-plan/preview', json={'run_id': run['id']}).json()
        notion.connection.generation = 'g2'
        blocked = client.post('/api/study-plan/preview', json={'run_id': run['id']})
        assert blocked.status_code == 409
        exported = client.post('/api/study-plan/export',
                               json={'draft_id': draft['draft_id'], 'destination': 'parent-page'}).json()
        assert exported['status'] == 'failure'
        stored = client.get(f"/api/study-plan/drafts/{draft['draft_id']}").json()
        history = client.get(f'/api/conversations/{conversation}').json()
    assert stored['markdown'] == '# Transformers plan' and stored['exportable'] is False
    assert history['messages']
    assert notion.create_page.await_count == 0


def test_study_plan_routes_disabled_without_notion(db, fake_generate):
    service = make_service(db, backend='disabled')
    with TestClient(make_app(service, db, backend='disabled')) as client:
        assert client.post('/api/study-plan/preview', json={'run_id': 'x'}).status_code == 404
        assert client.get('/api/config').json()['notion_backend'] == 'disabled'
        assert client.get('/api/notion/pages', params={'q': 'x'}).status_code == 404
