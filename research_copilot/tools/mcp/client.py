"""Official LangChain adapter wiring and bounded execution."""
import asyncio
import logging
import time
from datetime import timedelta
from langchain_mcp_adapters.client import MultiServerMCPClient
from .config import HttpConfig

logger = logging.getLogger(__name__)


class MCPConnectionError(RuntimeError):
    pass


class AuthorizationRequired(RuntimeError):
    pass


class MCPToolError(RuntimeError):
    pass


async def deadline(request, handler):
    start = time.monotonic()
    outcome = 'error'
    try:
        async with asyncio.timeout(30):
            result = await handler(request)
        outcome = 'success'
        return result
    finally:
        logger.info('mcp tool=%s outcome=%s duration=%.3f', request.name, outcome, time.monotonic()-start)


def create_client(name, config):
    if isinstance(config, HttpConfig):
        connection = dict(transport='streamable_http', url=str(config.url), auth=config.auth,
                          timeout=timedelta(seconds=30), sse_read_timeout=timedelta(seconds=30))
        if config.httpx_client_factory:
            connection['httpx_client_factory'] = config.httpx_client_factory
    else:
        connection = config.model_dump()
    return MultiServerMCPClient({name: connection}, tool_name_prefix=True,
                               tool_interceptors=[deadline])
