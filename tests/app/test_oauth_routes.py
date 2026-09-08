from types import SimpleNamespace
import pytest

pytest.importorskip('itsdangerous')

from fastapi.testclient import TestClient
from research_copilot.app.main import create_app
from research_copilot.tools.mcp.oauth import ConnectionService
from tests.mcp.test_oauth import MemoryStore, OAuthServer, factory


def _app(service):
    config = SimpleNamespace(
        NOTION_BACKEND='mcp',
        OAUTH_BASE_URL='http://127.0.0.1:7860',
        OAUTH_TIMEOUT=300,
    )
    return create_app(config, connection=service, mount_ui=False)


@pytest.fixture(autouse=True)
def _data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('RESEARCH_COPILOT_DATA_DIR', str(tmp_path))


def _client(service):
    return TestClient(_app(service), base_url='http://127.0.0.1')


def _csrf(client):
    response = client.get('/oauth/notion/status')
    assert response.status_code == 200
    body = response.json()
    assert 'access_token' not in str(body)
    return body['csrf']


def test_csrf_and_cross_origin_writes_rejected():
    service = ConnectionService(MemoryStore(), http_factory=factory(OAuthServer()))
    with _client(service) as client:
        assert client.post('/oauth/notion/start').status_code == 403
        csrf = _csrf(client)
        blocked = client.post(
            '/oauth/notion/start',
            headers={'X-CSRF-Token': csrf, 'origin': 'http://evil.test'},
        )
        assert blocked.status_code == 403


@pytest.mark.asyncio
async def test_callback_mismatch_replay_and_disconnect():
    service = ConnectionService(MemoryStore(), http_factory=factory(OAuthServer()))
    with _client(service) as client, TestClient(_app(service), base_url='http://127.0.0.1') as other:
        csrf = _csrf(client)
        started = client.post('/oauth/notion/start', headers={'X-CSRF-Token': csrf})
        assert started.status_code == 200
        url = started.json()['authorization_url']
        assert 'code_challenge=' in url
        state = service.pending.state
        other.get('/oauth/notion/status')
        mismatch = other.get('/oauth/notion/callback', params={'code': 'test-code', 'state': state})
        assert mismatch.status_code == 400
        wrong_state = client.get('/oauth/notion/callback', params={'code': 'test-code', 'state': 'nope'})
        assert wrong_state.status_code == 400
        success = client.get('/oauth/notion/callback', params={'code': 'test-code', 'state': state})
        assert success.status_code in (303, 307, 200)
        replay = client.get('/oauth/notion/callback', params={'code': 'test-code', 'state': state})
        assert replay.status_code == 400
        status = client.get('/oauth/notion/status').json()
        assert status['status'] == 'connected'
        assert 'granted-secret' not in str(status)
        csrf = status['csrf']
        gone = client.post('/oauth/notion/disconnect', headers={'X-CSRF-Token': csrf})
        assert gone.status_code == 200
        assert gone.json()['status'] == 'disconnected'
        assert 'revoke' in gone.json()['message'].lower()
        assert client.get('/oauth/notion/status').json()['status'] == 'disconnected'
