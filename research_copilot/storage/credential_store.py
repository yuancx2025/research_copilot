"""One local credential bundle in macOS Keychain; never a plaintext fallback.

Notion keeps the historical Keychain identity so existing grants still load.
"""
import asyncio
import sys
from research_copilot.runtime.auth.schemas import ConnectionRecord


class CredentialStorageError(RuntimeError):
    pass


class KeychainStore:
    def __init__(self, service='research-copilot.notion-mcp', account='local-profile'):
        self.service = service
        self.account = account

    def _backend(self):
        if sys.platform != 'darwin':
            raise CredentialStorageError('Local OAuth currently requires macOS Keychain.')
        try:
            from keyring.backends.macOS import Keyring
            return Keyring()
        except Exception as exc:
            raise CredentialStorageError('Install keyring and enable macOS Keychain.') from exc

    async def load(self):
        try:
            raw = await asyncio.to_thread(self._backend().get_password, self.service, self.account)
            return ConnectionRecord.model_validate_json(raw) if raw else None
        except CredentialStorageError:
            raise
        except Exception as exc:
            raise CredentialStorageError('Unable to read the Notion connection from Keychain.') from exc

    async def save(self, record):
        try:
            await asyncio.to_thread(self._backend().set_password, self.service, self.account,
                                    record.model_dump_json())
        except Exception as exc:
            raise CredentialStorageError('Unable to save the Notion connection in Keychain.') from exc

    async def delete(self):
        try:
            backend = self._backend()
            if await asyncio.to_thread(backend.get_password, self.service, self.account):
                await asyncio.to_thread(backend.delete_password, self.service, self.account)
        except Exception as exc:
            raise CredentialStorageError('Unable to remove the Notion connection from Keychain.') from exc
