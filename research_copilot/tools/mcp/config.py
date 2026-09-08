"""Validated transport settings; credentials are excluded from serialization."""
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, HttpUrl


class StdioConfig(BaseModel):
    transport: Literal['stdio'] = 'stdio'
    command: str = Field(min_length=1)
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict, repr=False)


class HttpConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    transport: Literal['streamable_http'] = 'streamable_http'
    url: HttpUrl
    auth: object | None = Field(default=None, exclude=True, repr=False)
    httpx_client_factory: object | None = Field(default=None, exclude=True, repr=False)


def normalize_command(command, args=()):
    parts = command.split(',') if isinstance(command, str) else list(command or [])
    if not parts or not parts[0].strip():
        raise ValueError('MCP executable is required')
    return parts[0].strip(), [*parts[1:], *args]


def parse_server_config(value):
    if isinstance(value, (StdioConfig, HttpConfig)):
        return value
    data = dict(value)
    if data.get('transport') in ('http', 'streamable_http') or 'url' in data:
        data['transport'] = 'streamable_http'
        return HttpConfig.model_validate(data)
    data['command'], data['args'] = normalize_command(data.get('command'), data.get('args', []))
    return StdioConfig.model_validate(data)
