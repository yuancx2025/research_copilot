"""Local AES-256 key file for MCP credentials, kept outside the repository and the database.

Format: ``{"active": "k1", "keys": {"k1": "<base64 32 bytes>"}}``. Older versions
stay listed so rows encrypted before a rotation remain readable. The key file
is only ever created by ``research-copilot-admin keys init``; startup never
generates a replacement.
"""
import base64
import json
import os
import secrets
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

DEFAULT_KEY_FILE = Path.home() / '.config' / 'research-copilot' / 'credential-keys.json'
KEY_BYTES = 32
SETUP_HINT = 'Run `research-copilot-admin keys init`, or restore your backed-up key file'


class CredentialError(RuntimeError):
    """Base for credential storage failures; messages never include secrets."""


class CredentialKeyError(CredentialError):
    """The key file is missing, unreadable, too permissive, or cannot decrypt stored credentials."""


def key_file_path(env=None) -> Path:
    value = (env if env is not None else os.environ).get('MCP_CREDENTIAL_KEY_FILE', '').strip()
    return Path(value).expanduser() if value else DEFAULT_KEY_FILE


def _check_permissions(path: Path):
    if os.name != 'posix':
        return
    file_mode = stat.S_IMODE(path.stat().st_mode)
    dir_mode = stat.S_IMODE(path.parent.stat().st_mode)
    if file_mode & 0o077:
        raise CredentialKeyError(f'Credential key file {path} must not be readable by others (chmod 600).')
    if dir_mode & 0o077:
        raise CredentialKeyError(f'Credential key directory {path.parent} must be private (chmod 700).')


@dataclass(frozen=True)
class CredentialKeys:
    active: str
    keys: Dict[str, bytes]

    @property
    def active_key(self) -> bytes:
        return self.keys[self.active]

    def key(self, version: str) -> bytes:
        try:
            return self.keys[version]
        except KeyError:
            raise CredentialKeyError(
                f'Key version {version!r} is not in the credential key file. {SETUP_HINT}, '
                'or reconnect Notion.') from None

    @classmethod
    def load(cls, path: Path | None = None) -> 'CredentialKeys':
        path = Path(path) if path else key_file_path()
        if not path.exists():
            raise CredentialKeyError(f'Credential key file {path} was not found. {SETUP_HINT}.')
        _check_permissions(path)
        try:
            data = json.loads(path.read_text())
            keys = {str(v): base64.b64decode(k, validate=True) for v, k in data['keys'].items()}
            active = str(data['active'])
        except Exception:
            raise CredentialKeyError(f'Credential key file {path} is malformed. {SETUP_HINT}.') from None
        if active not in keys:
            raise CredentialKeyError(f'Credential key file {path} has no entry for its active version.')
        if any(len(k) != KEY_BYTES for k in keys.values()):
            raise CredentialKeyError(f'Credential key file {path} must contain 32-byte keys.')
        return cls(active, keys)


def init_key_file(path: Path | None = None) -> Path:
    """Create a new key file with a random key. Refuses to overwrite an existing file."""
    path = Path(path) if path else key_file_path()
    if path.exists():
        raise CredentialKeyError(f'{path} already exists; refusing to replace an existing key.')
    if not path.parent.exists():
        path.parent.mkdir(mode=0o700, parents=True)
        os.chmod(path.parent, 0o700)
    if os.name == 'posix' and stat.S_IMODE(path.parent.stat().st_mode) & 0o077:
        raise CredentialKeyError(f'{path.parent} is readable by others; choose a private directory (chmod 700).')
    body = json.dumps({'active': 'k1', 'keys': {'k1': base64.b64encode(secrets.token_bytes(KEY_BYTES)).decode()}},
                      indent=2)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as handle:
        handle.write(body + '\n')
    return path
