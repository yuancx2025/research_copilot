import pytest

pytest.importorskip('itsdangerous')
pytest.importorskip('multipart')

from fastapi.testclient import TestClient
from tests.app.fakes import make_app, make_service, parse_sse
from tests.runtime.auth.test_oauth import MemoryStore, OAuthServer, factory, ConnectionService


@pytest.fixture(autouse=True)
def _data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('RESEARCH_COPILOT_DATA_DIR', str(tmp_path))


def _local_client(service):
    connection = ConnectionService(MemoryStore(), http_factory=factory(OAuthServer()))
    app = make_app(service, backend='mcp', connection=connection)
    return TestClient(app, base_url='http://127.0.0.1:7860')


def test_local_api_writes_require_session_csrf():
    with _local_client(make_service(backend='mcp')) as client:
        assert client.post('/api/research', json={'message': 'q'}).status_code == 403
        assert client.post('/api/session/reset').status_code == 403
        assert client.delete('/api/documents').status_code == 403
        assert client.post('/api/study-plan/preview').status_code == 403

        config = client.get('/api/config')
        assert config.headers['cache-control'] == 'no-store'
        csrf = config.json()['csrf']
        assert csrf and csrf == client.get('/oauth/notion/status').json()['csrf']
        headers = {'X-CSRF-Token': csrf}
        assert client.post('/api/research', json={'message': 'q'}, headers={'X-CSRF-Token': 'wrong'}).status_code == 403
        events = parse_sse(client.post('/api/research', json={'message': 'q'}, headers=headers).text)
        assert events[-1]['type'] == 'result'

        foreign = client.post('/api/session/reset', headers={**headers, 'origin': 'http://127.0.0.1:5173'})
        assert foreign.status_code == 403
        same = client.post('/api/session/reset', headers={**headers, 'origin': 'http://127.0.0.1:7860'})
        assert same.status_code == 204


def test_local_mode_rejects_other_hosts():
    with _local_client(make_service(backend='mcp')) as client:
        assert client.get('/api/health', headers={'host': 'localhost:7860'}).status_code == 400


def test_hosted_mode_rejects_cross_site_writes_without_csrf():
    with TestClient(make_app(make_service()), base_url='http://copilot.example') as client:
        assert client.get('/api/config').json()['csrf'] is None
        assert client.post('/api/session/reset', headers={'origin': 'https://evil.test'}).status_code == 403
        assert client.post('/api/session/reset', headers={'sec-fetch-site': 'cross-site'}).status_code == 403
        assert client.post('/api/session/reset', headers={'origin': 'http://copilot.example'}).status_code == 204
        assert client.post('/api/session/reset').status_code == 204


def test_frontend_url_must_be_loopback():
    from types import SimpleNamespace
    from research_copilot.app.main import create_app
    config = SimpleNamespace(NOTION_BACKEND='mcp', OAUTH_BASE_URL='http://127.0.0.1:7860',
                             FRONTEND_URL='https://evil.test')
    with pytest.raises(ValueError, match='FRONTEND_URL'):
        create_app(config, research_factory=lambda **_: None)


def test_spa_fallback_and_legacy_redirect(tmp_path):
    dist = tmp_path / 'dist'
    (dist / 'assets').mkdir(parents=True)
    (dist / 'index.html').write_text('<div id="root"></div>')
    (dist / 'favicon.svg').write_text('<svg/>')
    (dist / 'assets' / 'app.js').write_text('console.log(1)')
    (tmp_path / 'secret.txt').write_text('secret')
    with TestClient(make_app(make_service(), tmp_path=dist)) as client:
        assert client.get('/research').text == '<div id="root"></div>'
        assert client.get('/oauth/done').text == '<div id="root"></div>'
        assert client.get('/favicon.svg').text == '<svg/>'
        assert client.get('/assets/app.js').text == 'console.log(1)'
        assert client.get('/api/missing').status_code == 404
        assert 'secret' not in client.get('/%2e%2e/secret.txt').text
        assert client.get('/ui', follow_redirects=False).headers['location'] == '/'
