"""Contract checks do not need PostgreSQL, credentials, or app lifespan."""
import json
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from research_copilot.app.export_contracts import contract_document
from research_copilot.app.schemas import ResearchEventOut, UploadEventOut, RunOut
from research_copilot.app.presenters import present_run


def test_export_is_deterministic_and_matches_snapshot(monkeypatch):
    from research_copilot.db.engine import Database
    from research_copilot.core.research_service import ResearchService
    def forbidden(*args, **kwargs):
        raise AssertionError('Contract export must not initialize application resources')
    monkeypatch.setattr(Database, '__init__', forbidden)
    monkeypatch.setattr(ResearchService, '__init__', forbidden)
    first = contract_document()
    assert first == contract_document()
    snapshot = Path(__file__).parents[2] / 'frontend/contracts/openapi.json'
    assert first == json.loads(snapshot.read_text())
    assert first['paths']['/oauth/notion/status']['get']['responses']['200']['content']['application/json']['schema']
    for path, method, model in [('/api/runs/{run_id}/events', 'get', 'ResearchEventOut'),
                                ('/api/documents', 'post', 'UploadEventOut')]:
        response = first['paths'][path][method]['responses']['200']
        assert set(response['content']) == {'text/event-stream'}
        assert response['x-event-schema']['$ref'].endswith(model)
        assert model in first['components']['schemas']


def test_presented_run_matches_result_event():
    now = datetime.now(timezone.utc)
    run = SimpleNamespace(id='r', conversation_id='c', request_id='request-1', status='completed', query='q',
                          retry_of_run_id=None, error=None, created_at=now, finished_at=now, result=None)
    payload = present_run(run, None, 2)
    parsed = RunOut.model_validate(payload)
    event = ResearchEventOut.model_validate({'type': 'result', 'seq': 2, 'run_id': 'r', 'run': payload})
    assert event.root.run == parsed
    assert RunOut.model_validate_json(parsed.model_dump_json()) == parsed


@pytest.mark.parametrize('payload', [
    {'type': 'progress', 'node': 'prepare', 'seq': 1, 'run_id': 'r'},
    {'type': 'progress', 'node': 'classify_intent', 'agents': ['web'], 'seq': 2, 'run_id': 'r'},
    {'type': 'error', 'message': 'failed', 'status': 'failed', 'seq': 3, 'run_id': 'r'},
])
def test_research_events_match_existing_emissions(payload):
    assert ResearchEventOut.model_validate(payload).root.type == payload['type']


@pytest.mark.parametrize('payload', [
    {'type': 'progress', 'fraction': 0.5, 'message': 'Indexing'},
    {'type': 'result', 'added': 1, 'skipped': 0, 'documents': ['paper.pdf']},
    {'type': 'error', 'message': 'Indexing failed'},
])
def test_upload_events_match_existing_emissions(payload):
    assert UploadEventOut.model_validate(payload).root.type == payload['type']


def test_research_protocol_requires_identity_and_sequence():
    with pytest.raises(ValidationError):
        ResearchEventOut.model_validate({'type': 'progress', 'node': 'prepare'})
