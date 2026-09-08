"""Connection and pending-authorization records."""
from dataclasses import dataclass
import asyncio
from typing import Literal
from pydantic import BaseModel, Field


class ConnectionRecord(BaseModel):
    connection_id: str
    generation: str
    server_url: str
    client_info: dict = Field(repr=False)
    tokens: dict = Field(repr=False)
    expires_at: float | None = None
    issuer: str
    token_endpoint: str
    resource: str
    workspace_id: str = ''
    workspace_name: str = ''
    status: Literal['connected', 'reconnect_required'] = 'connected'


@dataclass
class PendingGrant:
    session_id: str
    url: asyncio.Future
    callback: asyncio.Future
    expires_at: float
    task: asyncio.Task | None = None
    state: str | None = None
    consumed: bool = False
