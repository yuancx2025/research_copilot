import asyncio
import time
from urllib.parse import parse_qs
import httpx
import pytest
from research_copilot.tools.mcp.oauth import ConnectionService, StoredTokenAuth, NOTION_URL
from research_copilot.tools.mcp.client import AuthorizationRequired, MCPConnectionError
from research_copilot.storage.oauth_store import ConnectionRecord


class MemoryStore:
    def __init__(self, record=None):
        self.record = record
    async def load(self):
        return self.record.model_copy(deep=True) if self.record else None
    async def save(self, record):
        self.record = record.model_copy(deep=True)
    async def delete(self):
        self.record = None


def record():
    return ConnectionRecord(connection_id='c', generation='g', server_url=NOTION_URL,
        client_info={'client_id':'client','redirect_uris':['http://127.0.0.1:7860/oauth/notion/callback'], 'token_endpoint_auth_method':'none'},
        tokens={'access_token':'old-secret', 'refresh_token':'refresh-secret'}, expires_at=time.time()-1,
        issuer='https://mcp.notion.com', token_endpoint='https://mcp.notion.com/oauth/token', resource=NOTION_URL)


def factory(handler):
    return lambda **kwargs: httpx.AsyncClient(transport=httpx.MockTransport(handler), **kwargs)


@pytest.mark.asyncio
async def test_restart_and_single_refresh_rotates_atomically():
    count = 0
    async def handler(request):
        nonlocal count
        count += 1
        assert str(request.url) == 'https://mcp.notion.com/oauth/token'
        await asyncio.sleep(.01)
        return httpx.Response(200,json={'access_token':'new-secret','refresh_token':'new-refresh','expires_in':3600})
    store = MemoryStore(record())
    service = ConnectionService(store, http_factory=factory(handler))
    await service.initialize()
    assert await asyncio.gather(*(service.token('g') for _ in range(5))) == ['new-secret']*5
    assert count == 1 and store.record.tokens['refresh_token'] == 'new-refresh'
    restarted = ConnectionService(store, http_factory=factory(handler))
    await restarted.initialize()
    assert await restarted.token('g') == 'new-secret' and count == 1


@pytest.mark.asyncio
async def test_invalid_grant_and_transient_error():
    service = ConnectionService(MemoryStore(record()), http_factory=factory(lambda r:httpx.Response(503,json={'error':'temporarily_unavailable'})))
    await service.initialize()
    with pytest.raises(MCPConnectionError):
        await service.token('g')
    assert service.connected
    service.http_factory = factory(lambda r:httpx.Response(400,json={'error':'invalid_grant'}))
    with pytest.raises(AuthorizationRequired):
        await service.token('g')
    assert service.status()['status'] == 'reconnect_required'


@pytest.mark.asyncio
async def test_runtime_auth_never_opens_browser_and_stale_generation_fails():
    service = ConnectionService(MemoryStore(record()))
    await service.initialize()
    service.record.expires_at = time.time()+3600
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(401)), auth=StoredTokenAuth(service,'g')) as client:
        with pytest.raises(AuthorizationRequired):
            await client.post(NOTION_URL)
    await service.disconnect()
    with pytest.raises(AuthorizationRequired):
        await service.token('g')
    assert service.store.record is None


class OAuthServer:
    def __init__(self):
        self.refreshes = 0
    def __call__(self, request):
        url = str(request.url)
        if 'oauth-protected-resource' in url:
            return httpx.Response(200,json={'resource':NOTION_URL, 'authorization_servers':['https://mcp.notion.com']})
        if 'oauth-authorization-server' in url:
            return httpx.Response(200,json={'issuer':'https://mcp.notion.com',
                'authorization_endpoint':'https://mcp.notion.com/authorize',
                'token_endpoint':'https://mcp.notion.com/oauth/token',
                'registration_endpoint':'https://mcp.notion.com/register',
                'response_types_supported':['code'], 'code_challenge_methods_supported':['S256'],
                'grant_types_supported':['authorization_code','refresh_token']})
        if url.endswith('/register'):
            import json
            return httpx.Response(201,json={**json.loads(request.content),'client_id':'registered-client'})
        if url.endswith('/oauth/token'):
            body = parse_qs(request.content.decode())
            assert body['code_verifier'] and body['code'] == ['test-code']
            return httpx.Response(200,json={'access_token':'granted-secret','refresh_token':'refresh','expires_in':3600})
        if request.headers.get('authorization') == 'Bearer granted-secret':
            return httpx.Response(200,json={'jsonrpc':'2.0','id':1,'result':{}})
        return httpx.Response(401,headers={'WWW-Authenticate': 'Bearer resource_metadata="https://mcp.notion.com/.well-known/oauth-protected-resource"'})


@pytest.mark.asyncio
async def test_sdk_grant_state_session_replay_and_persistence():
    service = ConnectionService(MemoryStore(), http_factory=factory(OAuthServer()))
    url = await service.start('browser-one')
    assert 'code_challenge=' in url
    state = service.pending.state
    with pytest.raises(ValueError):
        await service.complete('browser-two','test-code',state)
    with pytest.raises(ValueError):
        await service.complete('browser-one','test-code','wrong-state')
    await service.complete('browser-one','test-code',state)
    assert service.connected
    assert service.store.record.expires_at > time.time()
    assert service.store.record.token_endpoint.endswith('/oauth/token')
    with pytest.raises(ValueError):
        await service.complete('browser-one','test-code',state)
    assert 'granted-secret' not in str(service.status())


@pytest.mark.asyncio
async def test_denied_and_expired_grants():
    service = ConnectionService(MemoryStore(), http_factory=factory(OAuthServer()), timeout=.1)
    await service.start('browser')
    with pytest.raises(AuthorizationRequired):
        await service.complete('browser','',service.pending.state,error='access_denied')
    assert not service.connected
    await service.start('browser')
    await service.pending.task
    assert service.status()['status'] == 'failed'
    with pytest.raises(ValueError):
        await service.complete('browser','test-code',service.pending.state)
