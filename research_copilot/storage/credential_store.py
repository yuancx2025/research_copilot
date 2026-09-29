"""MCP credential bundles encrypted with AES-256-GCM and stored in PostgreSQL.

Plain columns hold routing metadata (provider, endpoints, workspace, status,
generation, expiry). Tokens and client registration (including any client
secret) live only in the ciphertext. The associated data binds each payload to
its connection ID, provider, and key version, so rows cannot be swapped.
There is no plaintext fallback: a missing or wrong key is an error.
"""
import json
import os
from typing import Optional

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select, text, update

from research_copilot.db.models import McpConnection
from research_copilot.runtime.auth.schemas import ConnectionRecord
from research_copilot.storage.credential_keys import CredentialError, CredentialKeyError, CredentialKeys

AAD_PREFIX = 'rc:mcp-cred:v1'
NONCE_BYTES = 12


class CredentialStorageError(CredentialError):
    """The database could not read or write the connection record."""


def associated_data(connection_id: str, provider: str, key_version: str) -> bytes:
    return f'{AAD_PREFIX}|{connection_id}|{provider}|{key_version}'.encode()


class PostgresCredentialStore:
    def __init__(self, db, provider: str = 'notion', key_file=None, keys: Optional[CredentialKeys] = None):
        self.db = db
        self.provider = provider
        self.key_file = key_file
        self._keys = keys
        self._versions: dict[str, int] = {}

    def keys(self) -> CredentialKeys:
        if self._keys is None:
            self._keys = CredentialKeys.load(self.key_file)
        return self._keys

    def _encrypt(self, record: ConnectionRecord):
        keys = self.keys()
        nonce = os.urandom(NONCE_BYTES)
        bundle = json.dumps({'tokens': record.tokens, 'client_info': record.client_info}).encode()
        aad = associated_data(record.connection_id, self.provider, keys.active)
        return keys.active, nonce, AESGCM(keys.active_key).encrypt(nonce, bundle, aad)

    def _decrypt(self, row: McpConnection) -> dict:
        key = self.keys().key(row.key_version)
        try:
            plain = AESGCM(key).decrypt(row.nonce, row.ciphertext,
                                        associated_data(row.id, row.provider, row.key_version))
        except InvalidTag:
            raise CredentialKeyError(
                'Saved Notion credentials could not be decrypted with the configured key file. '
                'Restore the original key file, or reconnect Notion.') from None
        return json.loads(plain)

    async def check(self):
        """Verify the key file and database before starting an authorization."""
        self.keys()
        try:
            async with self.db.session() as session:
                await session.execute(text('SELECT 1'))
        except Exception as exc:
            raise CredentialStorageError('The database is unavailable, so Notion credentials cannot be saved.') from exc

    async def load(self) -> Optional[ConnectionRecord]:
        try:
            async with self.db.session() as session:
                row = await session.scalar(select(McpConnection).where(
                    McpConnection.provider == self.provider, McpConnection.status != 'disconnected'))
        except Exception as exc:
            raise CredentialStorageError('Unable to read the Notion connection from the database.') from exc
        if row is None:
            return None
        bundle = self._decrypt(row) if row.ciphertext is not None else {'tokens': {}, 'client_info': {}}
        self._versions[row.id] = row.record_version
        return ConnectionRecord(
            connection_id=row.id, generation=row.generation, server_url=row.server_url,
            client_info=bundle.get('client_info') or {}, tokens=bundle.get('tokens') or {},
            expires_at=row.expires_at, issuer=row.issuer, token_endpoint=row.token_endpoint,
            resource=row.resource, workspace_id=row.workspace_id, workspace_name=row.workspace_name,
            status=row.status)

    async def save(self, record: ConnectionRecord):
        # A reconnect with no tokens drops the payload. Client secrets travel in the
        # same bundle, so they are removed together rather than stored in plaintext.
        if record.tokens:
            key_version, nonce, ciphertext = self._encrypt(record)
        else:
            key_version = nonce = ciphertext = None
        values = dict(
            provider=self.provider, server_url=record.server_url, issuer=record.issuer,
            token_endpoint=record.token_endpoint, resource=record.resource, workspace_id=record.workspace_id,
            workspace_name=record.workspace_name, status=record.status, generation=record.generation,
            expires_at=record.expires_at, key_version=key_version, nonce=nonce, ciphertext=ciphertext)
        try:
            async with self.db.transaction() as session:
                row = await session.get(McpConnection, record.connection_id)
                if row is None:
                    await session.execute(update(McpConnection).where(
                        McpConnection.provider == self.provider, McpConnection.status != 'disconnected',
                    ).values(**_disconnected()))
                    session.add(McpConnection(id=record.connection_id, record_version=1, **values))
                    version = 1
                else:
                    expected = self._versions.get(record.connection_id, row.record_version)
                    result = await session.execute(update(McpConnection).where(
                        McpConnection.id == record.connection_id, McpConnection.record_version == expected,
                        McpConnection.status != 'disconnected',
                    ).values(record_version=expected + 1, **values))
                    if result.rowcount != 1:
                        raise CredentialStorageError(
                            'The saved Notion connection changed or was removed elsewhere. Reconnect Notion.')
                    version = expected + 1
        except CredentialError:
            raise
        except Exception as exc:
            raise CredentialStorageError('Unable to save the Notion connection in the database.') from exc
        self._versions[record.connection_id] = version

    async def delete(self):
        """Remove the credential payload; the row remains as a disconnected audit record."""
        try:
            async with self.db.transaction() as session:
                await session.execute(update(McpConnection).where(
                    McpConnection.provider == self.provider, McpConnection.status != 'disconnected',
                ).values(**_disconnected()))
        except Exception as exc:
            raise CredentialStorageError('Unable to remove the Notion connection from the database.') from exc


def _disconnected():
    return dict(status='disconnected', nonce=None, ciphertext=None, key_version=None, expires_at=None,
                record_version=McpConnection.record_version + 1)
