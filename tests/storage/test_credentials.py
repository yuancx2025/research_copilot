import os
import stat

import pytest

from research_copilot.runtime.auth.connection import ConnectionService
from research_copilot.sources.notion.oauth import NotionAuthProvider
from research_copilot.storage.credential_keys import CredentialKeyError, init_key_file, key_file_path
from research_copilot.storage.credential_store import PostgresCredentialStore
from tests.runtime.auth.test_oauth import factory, record


def test_key_file_is_private_and_never_replaced(tmp_path, monkeypatch):
    path = tmp_path / 'private' / 'credential-keys.json'
    created = init_key_file(path)
    assert created == path
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    with pytest.raises(CredentialKeyError, match='already exists'):
        init_key_file(path)
    loose = tmp_path / 'loose'
    loose.mkdir()
    os.chmod(loose, 0o755)
    with pytest.raises(CredentialKeyError, match='private'):
        init_key_file(loose / 'credential-keys.json')
    os.chmod(path, 0o644)
    with pytest.raises(CredentialKeyError, match='chmod 600'):
        PostgresCredentialStore(None, key_file=path).keys()
    monkeypatch.setenv('MCP_CREDENTIAL_KEY_FILE', str(path))
    assert key_file_path() == path


@pytest.mark.asyncio
async def test_credentials_roundtrip_encrypted_and_refresh_persists(adb, tmp_path):
    import httpx
    path = init_key_file(tmp_path / 'credential-keys.json')
    store = PostgresCredentialStore(adb, key_file=path)
    await store.save(record())
    loaded = await store.load()
    assert loaded.tokens['access_token'] == 'old-secret'
    assert loaded.client_info['client_id'] == 'client'

    from sqlalchemy import text
    async with adb.session() as session:
        raw = (await session.execute(text(
            "SELECT server_url || workspace_name || COALESCE(encode(ciphertext, 'escape'), '') FROM mcp_connections"
        ))).scalar()
    assert 'old-secret' not in raw and 'refresh-secret' not in raw and 'client_secret' not in raw

    calls = {'n': 0}

    def handler(request):
        calls['n'] += 1
        return httpx.Response(200, json={'access_token': 'new-secret', 'refresh_token': 'rotated', 'expires_in': 3600})

    service = ConnectionService(NotionAuthProvider(), store, http_factory=factory(handler))
    await service.initialize()
    assert await service.token('g') == 'new-secret'
    restarted = ConnectionService(NotionAuthProvider(), PostgresCredentialStore(adb, key_file=path),
                                  http_factory=factory(handler))
    await restarted.initialize()
    assert await restarted.token('g') == 'new-secret'
    assert calls['n'] == 1
    assert restarted.record.tokens['refresh_token'] == 'rotated'


@pytest.mark.asyncio
async def test_missing_or_wrong_key_blocks_credentials_without_plaintext(adb, tmp_path):
    good = init_key_file(tmp_path / 'good.json')
    await PostgresCredentialStore(adb, key_file=good).save(record())
    wrong = init_key_file(tmp_path / 'wrong.json')
    with pytest.raises(CredentialKeyError, match='could not be decrypted'):
        await PostgresCredentialStore(adb, key_file=wrong).load()
    with pytest.raises(CredentialKeyError, match='not found'):
        await PostgresCredentialStore(adb, key_file=tmp_path / 'missing.json').load()
    from sqlalchemy import text
    async with adb.session() as session:
        raw = (await session.execute(text("SELECT encode(ciphertext, 'escape') FROM mcp_connections"))).scalar()
    assert 'old-secret' not in raw


@pytest.mark.asyncio
async def test_reconnect_drops_ciphertext_and_disconnect_keeps_the_row(adb, tmp_path):
    path = init_key_file(tmp_path / 'credential-keys.json')
    store = PostgresCredentialStore(adb, key_file=path)
    saved = record().model_copy(update={'tokens': {}, 'expires_at': None, 'status': 'reconnect_required'})
    await store.save(saved)
    from sqlalchemy import text
    async with adb.session() as session:
        ciphertext, status = (await session.execute(text(
            'SELECT ciphertext IS NULL, status FROM mcp_connections'))).one()
    assert ciphertext and status == 'reconnect_required'
    loaded = await store.load()
    assert loaded.tokens == {} and loaded.status == 'reconnect_required'
    await store.delete()
    assert await store.load() is None
    async with adb.session() as session:
        row = (await session.execute(text(
            'SELECT status, ciphertext IS NULL FROM mcp_connections'))).one()
    assert row == ('disconnected', True)
