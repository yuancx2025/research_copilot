"""Compatibility facade. Tools own configurations, never open sessions."""
from .client import create_client, MCPConnectionError, AuthorizationRequired
from .config import parse_server_config


class MCPToolAdapter:
    def __init__(self, server_name, server_config):
        self.server_name = server_name
        self.config = parse_server_config(server_config)
        self.client = create_client(server_name, self.config)
        self._tools_cache = None

    async def connect(self):
        await self.create_langchain_tools()
        return True

    async def create_langchain_tools(self):
        if self._tools_cache is None:
            import asyncio
            try:
                async with asyncio.timeout(30):
                    self._tools_cache = await self.client.get_tools(server_name=self.server_name)
            except AuthorizationRequired:
                raise
            except Exception as exc:
                raise MCPConnectionError(f"Cannot discover tools on {self.server_name}") from exc
        return self._tools_cache

    async def discover_tools(self):
        return [dict(name=t.name, description=t.description,
                     input_schema=t.args_schema if isinstance(t.args_schema, dict) else t.get_input_schema().model_json_schema())
                for t in await self.create_langchain_tools()]

    async def disconnect(self):
        self._tools_cache = None
