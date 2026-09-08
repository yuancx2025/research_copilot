"""Interactive SDK authorization and independent, durable runtime token refresh.

The SDK 1.25 context is inspected only in finish_authorization(), at the version
boundary. Runtime calls never depend on its in-memory expiry/discovery state.
"""
import asyncio
import secrets
import time
import uuid
from dataclasses import dataclass
from urllib.parse import urlsplit, parse_qs
import httpx
from mcp.client.auth import OAuthClientProvider
from mcp.shared.auth import OAuthClientMetadata, OAuthClientInformationFull, OAuthToken
from pydantic import AnyUrl
from research_copilot.storage.oauth_store import ConnectionRecord, KeychainStore
from .client import AuthorizationRequired, MCPConnectionError

NOTION_URL = 'https://mcp.notion.com/mcp'


def trusted_endpoint(url):
    parts = urlsplit(str(url))
    if parts.scheme != 'https' or not parts.hostname or not (
        parts.hostname == 'notion.com' or parts.hostname.endswith('.notion.com')
    ) or parts.username or parts.password:
        raise ValueError('Unexpected Notion authorization endpoint')
    return str(url)


class GrantStorage:
    """SDK TokenStorage during a pending grant. Commit only after validation."""
    def __init__(self, client_info=None):
        self.tokens = None
        self.client_info = client_info
        self.expires_at = None

    async def get_tokens(self):
        return self.tokens

    async def set_tokens(self, tokens):
        self.tokens = tokens
        self.expires_at = time.time() + tokens.expires_in if tokens.expires_in is not None else None

    async def get_client_info(self):
        return self.client_info

    async def set_client_info(self, client_info):
        self.client_info = client_info


@dataclass
class PendingGrant:
    session_id: str
    url: asyncio.Future
    callback: asyncio.Future
    expires_at: float
    task: asyncio.Task | None = None
    state: str | None = None
    consumed: bool = False


class ConnectionService:
    def __init__(self, store=None, base_url='http://127.0.0.1:7860', timeout=300,
                 http_factory=httpx.AsyncClient):
        self.store = store or KeychainStore()
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.http_factory = http_factory
        self.record = None
        self.pending = None
        self.error = None
        self.lock = asyncio.Lock()
        self._epoch = 0
        self._disconnecting = False
        self.start_lock = asyncio.Lock()
        self.active_tasks = set()
        self.listeners = []

    @property
    def generation(self):
        return self.record.generation if self.record else None

    @property
    def connected(self):
        return bool(not self._disconnecting and self.record and self.record.status == 'connected')

    async def initialize(self):
        try:
            self.record = await self.store.load()
        except Exception as exc:
            self.error = str(exc)

    async def changed(self):
        for listener in self.listeners:
            await listener()

    def status(self):
        state = ('connecting' if self.pending and not self.pending.task.done()
                 else self.record.status if self.record else 'failed' if self.error else 'disconnected')
        return dict(status=state, workspace=self.record.workspace_name if self.record else '',
                    generation=self.generation, error=self.error)

    async def start(self, session_id):
        async with self.start_lock:
            return await self._start(session_id)

    async def _start(self, session_id):
        if self._disconnecting:
            raise ValueError('Disconnect is still in progress.')
        if self.pending and not self.pending.task.done():
            raise ValueError('A connection attempt is already in progress.')
        # Probe secure storage before asking for consent.
        await self.store.load()
        loop = asyncio.get_running_loop()
        pending = PendingGrant(session_id, loop.create_future(), loop.create_future(),
                               time.time() + self.timeout)
        self.pending = pending
        self.error = None
        pending.task = asyncio.create_task(self._authorize(pending, self._epoch))
        try:
            return await asyncio.wait_for(asyncio.shield(pending.url), 30)
        except Exception:
            pending.task.cancel()
            await asyncio.gather(pending.task, return_exceptions=True)
            raise MCPConnectionError('Unable to start Notion authorization. Please retry.') from None

    async def _authorize(self, pending, epoch):
        previous = self.record.client_info if self.record else None
        # Preserve DCR identity across reauthorization instead of orphaning old grants.
        if previous and self.base_url + '/oauth/notion/callback' not in previous.get('redirect_uris', []):
            previous = None
        storage = GrantStorage(OAuthClientInformationFull.model_validate(previous) if previous else None)

        async def redirect(url):
            pending.state = parse_qs(urlsplit(url).query).get('state', [None])[0]
            trusted_endpoint(url)
            pending.url.set_result(url)

        async def callback():
            return await pending.callback

        provider = OAuthClientProvider(
            server_url=NOTION_URL,
            client_metadata=OAuthClientMetadata(
                client_name='Research Copilot',
                redirect_uris=[AnyUrl(self.base_url + '/oauth/notion/callback')],
                token_endpoint_auth_method='none'),
            storage=storage, redirect_handler=redirect, callback_handler=callback,
            timeout=self.timeout,
        )
        try:
            async with asyncio.timeout(self.timeout):
                # A finite initialize POST triggers SDK auth without opening a long-lived GET stream.
                async with self.http_factory(auth=provider, timeout=30, follow_redirects=False) as client:
                    response = await client.post(NOTION_URL, headers={
                        'Accept': 'application/json, text/event-stream',
                        'MCP-Protocol-Version': '2025-11-25',
                    }, json={'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
                        'protocolVersion': '2025-11-25', 'capabilities': {},
                        'clientInfo': {'name': 'research-copilot', 'version': '0.1.0'}}})
                    response.raise_for_status()
                await self.finish_authorization(provider, storage, epoch)
        except asyncio.CancelledError:
            if not pending.url.done():
                pending.url.cancel()
            raise
        except Exception:
            # SDK exceptions may contain token endpoint response bodies. Never surface them.
            self.error = 'Notion authorization failed, was denied, or timed out. Try connecting again.'
            if not pending.url.done():
                pending.url.set_exception(MCPConnectionError(self.error))

    async def finish_authorization(self, provider, storage, epoch):
        ctx = provider.context  # Isolated SDK 1.25 compatibility boundary.
        if not storage.tokens or not storage.client_info or not ctx.oauth_metadata:
            raise ValueError('Incomplete OAuth grant')
        record = ConnectionRecord(
            connection_id=str(uuid.uuid4()), generation=str(uuid.uuid4()), server_url=NOTION_URL,
            client_info=storage.client_info.model_dump(mode='json'),
            tokens=storage.tokens.model_dump(mode='json'), expires_at=storage.expires_at,
            issuer=trusted_endpoint(ctx.oauth_metadata.issuer),
            token_endpoint=trusted_endpoint(ctx.oauth_metadata.token_endpoint),
            resource=str(ctx.protected_resource_metadata.resource) if ctx.protected_resource_metadata else NOTION_URL,
        )
        async with self.lock:
            if epoch != self._epoch:
                raise AuthorizationRequired('Connection attempt was cancelled')
            self._epoch += 1
            await self.store.save(record)
            self.record = record
            self.error = None
        await self.changed()

    async def complete(self, session_id, code, state, error=None):
        pending = self.pending
        if not pending or pending.task.done() or pending.consumed or time.time() >= pending.expires_at:
            raise ValueError('Authorization attempt is missing or expired.')
        if session_id != pending.session_id or not state or not pending.state or not secrets.compare_digest(state, pending.state):
            raise ValueError('Authorization callback does not match this browser session.')
        pending.consumed = True
        if error or not code:
            pending.callback.set_exception(AuthorizationRequired('Consent was denied'))
        else:
            pending.callback.set_result((code, state))
        await pending.task
        if self.error:
            raise AuthorizationRequired(self.error)

    async def token(self, generation):
        async with self.lock:
            record = self.record
            if not self.connected or generation != self.generation:
                raise AuthorizationRequired('Connect Notion again before using this tool.')
            if record.expires_at is None or record.expires_at > time.time() + 60:
                return record.tokens['access_token']
            if not record.tokens.get('refresh_token'):
                await self._require_reconnect()
                raise AuthorizationRequired('Notion authorization expired. Reconnect.')
            data = dict(grant_type='refresh_token', refresh_token=record.tokens['refresh_token'],
                        client_id=record.client_info['client_id'], resource=record.resource)
            auth = None
            method = record.client_info.get('token_endpoint_auth_method')
            if method == 'client_secret_basic':
                auth = httpx.BasicAuth(data['client_id'], record.client_info['client_secret'])
            elif method == 'client_secret_post':
                data['client_secret'] = record.client_info['client_secret']
            try:
                async with self.http_factory(timeout=30, follow_redirects=False) as client:
                    response = await client.post(trusted_endpoint(record.token_endpoint), data=data, auth=auth)
                body = response.json()
            except Exception:
                raise MCPConnectionError('Notion token refresh is temporarily unavailable.') from None
            if body.get('error') == 'invalid_grant':
                await self._require_reconnect()
                raise AuthorizationRequired('Notion access was revoked or expired. Reconnect.')
            if response.is_error:
                raise MCPConnectionError('Notion token refresh is temporarily unavailable.')
            try:
                tokens = OAuthToken.model_validate(body)
            except Exception:
                raise MCPConnectionError('Notion returned an invalid token response.') from None
            if not tokens.refresh_token:
                tokens.refresh_token = record.tokens['refresh_token']
            updated = record.model_copy(update={
                'tokens': tokens.model_dump(mode='json'),
                'expires_at': time.time() + tokens.expires_in if tokens.expires_in is not None else None,
            })
            if not self.connected or generation != self.generation:
                raise AuthorizationRequired('Connection changed during refresh.')
            await self.store.save(updated)
            self.record = updated
            if not self.connected:
                raise AuthorizationRequired('Connection was disconnected during refresh.')
            return tokens.access_token

    async def _require_reconnect(self):
        self.record = self.record.model_copy(update={'status': 'reconnect_required', 'tokens': {}, 'expires_at': None})
        await self.store.save(self.record)
        await self.changed()

    async def reject_token(self, generation):
        async with self.lock:
            if self.record and generation == self.generation:
                await self._require_reconnect()

    async def label_workspace(self, identity):
        async with self.lock:
            if self.connected:
                workspace = identity.get('workspace', {})
                updated = self.record.model_copy(update={'workspace_id': workspace.get('id', ''),
                                                          'workspace_name': workspace.get('name', '')})
                await self.store.save(updated)
                self.record = updated

    async def disconnect(self):
        # Prevent all new calls before cancelling in-flight operations.
        self._disconnecting = True
        self._epoch += 1
        if self.pending and not self.pending.task.done():
            self.pending.task.cancel()
            await asyncio.gather(self.pending.task, return_exceptions=True)
        tasks = [t for t in self.active_tasks if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        try:
            async with self.lock:
                self.record = None
                self.pending = None
                self.error = None
                await self.store.delete()
        finally:
            await self.changed()
            self._disconnecting = False

    async def close(self):
        if self.pending and not self.pending.task.done():
            self.pending.task.cancel()
            await asyncio.gather(self.pending.task, return_exceptions=True)


class StoredTokenAuth(httpx.Auth):
    def __init__(self, service, generation):
        self.service = service
        self.generation = generation

    async def async_auth_flow(self, request):
        if str(request.url).split('?')[0] != NOTION_URL:
            raise AuthorizationRequired('Refusing to send Notion credentials to another endpoint.')
        request.headers['Authorization'] = 'Bearer ' + await self.service.token(self.generation)
        response = yield request
        if response.status_code == 401:
            await self.service.reject_token(self.generation)
            raise AuthorizationRequired('Notion rejected the connection. Reconnect.')
