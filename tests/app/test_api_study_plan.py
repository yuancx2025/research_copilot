import pytest

pytest.importorskip('multipart')

from fastapi.testclient import TestClient
from research_copilot.study_plans.schemas import StudyPlan, StudyPlanDraft
from tests.app.fakes import make_app, make_service


@pytest.fixture(autouse=True)
def _data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('RESEARCH_COPILOT_DATA_DIR', str(tmp_path))


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


def test_preview_requires_research_first(fake_generate):
    with TestClient(make_app(make_service())) as client:
        response = client.post('/api/study-plan/preview')
    assert response.status_code == 409
    assert 'Run research' in response.json()['detail']
    assert fake_generate == []


def test_preview_then_export_uses_server_side_draft(fake_generate):
    service = make_service()
    with TestClient(make_app(service)) as client:
        client.post('/api/research', json={'message': 'transformers'})
        draft = client.post('/api/study-plan/preview').json()
        assert draft['title'] == 'Transformers plan' and draft['markdown'] == '# Transformers plan'
        assert fake_generate == [('transformers', 'rest', 'Transformers use attention.')]

        missing = client.post('/api/study-plan/export', json={'draft_id': 'forged', 'destination': 'p'}).json()
        assert missing['status'] == 'failure' and missing['retryable'] is True

        result = client.post('/api/study-plan/export',
                             json={'draft_id': draft['draft_id'], 'destination': 'parent-page'}).json()
        assert result == {'status': 'success', 'page_id': 'page-1', 'url': 'https://notion.so/page-1',
                          'message': '', 'retryable': False}

    published, destination = service.exporter.published[0]
    assert published.draft_id == draft['draft_id'] and destination == 'parent-page'


def test_study_plan_routes_disabled_without_notion(fake_generate):
    service = make_service(backend='disabled')
    with TestClient(make_app(service, backend='disabled')) as client:
        assert client.post('/api/study-plan/preview').status_code == 404
        assert client.get('/api/config').json()['notion_backend'] == 'disabled'
        assert client.get('/api/notion/pages', params={'q': 'x'}).status_code == 404
