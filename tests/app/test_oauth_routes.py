from types import SimpleNamespace
import pytest

pytest.importorskip('itsdangerous')

from fastapi.testclient import TestClient
from research_copilot.app.main import create_app
from tests.runtime.auth.test_oauth import MemoryStore, OAuthServer, factory, ConnectionService


def _app(service, db, frontend_url=''):
    config = SimpleNamespace(
        NOTION_BACKEND='mcp',
        OAUTH_BASE_URL='http://127.0.0.1:7860',
        OAUTH_TIMEOUT=300,
        FRONTEND_URL=frontend_url,
    )
    return create_app(config, connection=service, research_factory=lambda **_: None, database=db)


def _client(service, db):
    return TestClient(_app(service, db), base_url='http://127.0.0.1')


def _csrf(client):
    response = client.get('/oauth/notion/status')
    assert response.status_code == 200
    body = response.json()
    assert 'access_token' not in str(body)
    return body['csrf']


def test_csrf_and_cross_origin_writes_rejected(db):
    service = ConnectionService(MemoryStore(), http_factory=factory(OAuthServer()))
    with _client(service, db) as client:
        assert client.post('/oauth/notion/start').status_code == 403
        csrf = _csrf(client)
        blocked = client.post(
            '/oauth/notion/start',
            headers={'X-CSRF-Token': csrf, 'origin': 'http://evil.test'},
        )
        assert blocked.status_code == 403


def test_callback_mismatch_replay_and_disconnect(db):
    from tests.app.fakes import fresh
    service = ConnectionService(MemoryStore(), http_factory=factory(OAuthServer()))
    with _client(service, db) as client, TestClient(_app(service, fresh(db)), base_url='http://127.0.0.1') as other:
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
        success = client.get('/oauth/notion/callback', params={'code': 'test-code', 'state': state},
                             follow_redirects=False)
        assert success.status_code == 303
        assert success.headers['location'] == '/oauth/done'
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
