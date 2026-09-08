"""Authorization provider policy implemented by each OAuth source."""
from typing import Protocol


class AuthProvider(Protocol):
    id: str
    display_name: str
    server_url: str
    client_name: str
    callback_path: str

    def trusted_endpoint(self, url: str) -> str:
        ...
