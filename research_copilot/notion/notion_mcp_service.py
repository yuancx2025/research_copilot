"""Notion-specific operations over discovered MCP tools, with no model credentials."""
import asyncio
import json
import logging
import re
import time
import uuid
from urllib.parse import urlsplit
import httpx
from langchain_core.messages import ToolMessage
from langchain_core.tools import ToolException
from research_copilot.tools.mcp.client import create_client, AuthorizationRequired, MCPToolError
from research_copilot.tools.mcp.config import HttpConfig
from research_copilot.tools.mcp.oauth import NOTION_URL, StoredTokenAuth

logger = logging.getLogger(__name__)


def payload(result):
    """Decode a structured artifact or JSON text, keeping all content blocks."""
    if isinstance(result, ToolMessage):
        if result.status == 'error':
            raise MCPToolError('Notion reported a tool error.')
        artifact = result.artifact
        if isinstance(artifact, dict) and artifact:
            return artifact.get('structured_content', artifact)
        result = result.content
    if isinstance(result, list):
        texts = [v.get('text', '') for v in result if isinstance(v, dict) and v.get('type') == 'text']
        decoded = []
        for text in texts:
            try:
                decoded.append(json.loads(text))
            except (ValueError, TypeError):
                decoded.append({'text': text})
        return decoded[0] if len(decoded) == 1 else {'content': decoded}
    if isinstance(result, str):
        try:
            return json.loads(result)
        except ValueError:
            return {'text': result}
    return result


def page_id(value):
    value = value.strip()
    if '://' in value:
        parsed = urlsplit(value)
        host = parsed.hostname or ''
        if parsed.scheme != 'https' or not any(host == h or host.endswith('.'+h) for h in ('notion.so','notion.com','notion.site')):
            raise ValueError('Use a Notion page URL or page UUID.')
        value = parsed.path.rstrip('/').split('/')[-1]
    match = re.search(r'([0-9a-fA-F]{32}|[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})$', value)
    if not match:
        raise ValueError('A valid Notion page UUID is required.')
    return str(uuid.UUID(match.group(1)))


class NotionMCPService:
    def __init__(self, connection):
        self.connection = connection
        self.generation = None
        self.tools = {}
        self.identity = {}
        self.lock = asyncio.Lock()
        self.limit = asyncio.Semaphore(2)
        connection.listeners.append(self.invalidate)

    async def invalidate(self):
        self.generation = None
        self.tools = {}
        self.identity = {}

    async def prepare(self):
        if not self.connection.connected:
            raise AuthorizationRequired('Use Connect Notion to authorize your workspace.')
        async with self.lock:
            generation = self.connection.generation
            if self.generation == generation:
                return
            client = create_client('notion', HttpConfig(url=NOTION_URL,
                                  auth=StoredTokenAuth(self.connection, generation)))
            async with asyncio.timeout(30):
                tools = await client.get_tools(server_name='notion')
            self.tools = {t.name.removeprefix('notion_'): t for t in tools}
            self.generation = generation
            try:
                data = await self.call('notion-fetch', {'id': 'self'}, prepare=False)
                self.identity = data.get('self', data)
                await self.connection.label_workspace(self.identity)
            except BaseException:
                await self.invalidate()
                raise

    async def call(self, name, arguments, *, read=True, prepare=True, generation=None):
        if prepare:
            await self.prepare()
        expected = generation or self.generation
        if not self.connection.connected or expected != self.connection.generation:
            raise AuthorizationRequired('Notion connection changed. Start a new request.')
        tool = self.tools.get(name)
        if tool is None:
            raise MCPToolError(f'The connected workspace does not offer {name}.')
        task = asyncio.current_task()
        self.connection.active_tasks.add(task)
        started = time.monotonic()
        outcome = 'error'
        try:
            async with self.limit:
                for attempt in range(3 if read else 1):
                    try:
                        if expected != self.connection.generation or not self.connection.connected:
                            raise AuthorizationRequired('Notion connection changed.')
                        async with asyncio.timeout(30):
                            result = await tool.ainvoke({'name': tool.name, 'args': arguments,
                                                       'id': str(uuid.uuid4()), 'type': 'tool_call'})
                        if expected != self.connection.generation or not self.connection.connected:
                            raise AuthorizationRequired('Notion connection changed.')
                        value = payload(result)
                        if isinstance(value, dict) and (value.get('error') or value.get('isError')):
                            raise MCPToolError('Notion reported an operation error.')
                        outcome = 'success'
                        return value
                    except (httpx.TransportError, TimeoutError):
                        if not read or attempt == 2:
                            raise
                        await asyncio.sleep(0.5 * 2**attempt)
                    except ToolException:
                        raise MCPToolError('Notion rejected the operation. Check page permissions and connection status.') from None
        finally:
            self.connection.active_tasks.discard(task)
            logger.info('notion tool=%s connection=%s outcome=%s duration=%.3f',
                        name, expected, outcome, time.monotonic()-started)

    async def search(self, query, generation=None):
        await self.prepare()
        access = self.identity.get('current_tool_access', {}).get('ai_search', {}).get('status')
        name = 'notion-ai-search' if access == 'available' else 'notion-search'
        data = await self.call(name, {'query': query}, generation=generation)
        return data

    async def fetch(self, id, generation=None):
        return await self.call('notion-fetch', {'id': id}, generation=generation)

    async def destination(self, value):
        id = page_id(value)
        data = await self.fetch(id)
        kind = data.get('type') or data.get('metadata', {}).get('type')
        if kind != 'page':
            raise ValueError('Select a page as the destination, not a database or data source.')
        if data.get('is_archived') or data.get('in_trash'):
            raise ValueError('The destination is archived.')
        return id

    async def create_page(self, destination, title, markdown, generation):
        return await self.call('notion-create-pages', {
            'parent': {'page_id': destination},
            'pages': [{'properties': {'title': title}, 'content': markdown}],
        }, read=False, generation=generation)
