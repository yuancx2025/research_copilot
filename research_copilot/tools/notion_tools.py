"""Read-only product tools, using the current local Notion connection."""
from langchain_core.tools import StructuredTool
from .base import BaseToolkit, SourceType


class NotionToolkit(BaseToolkit):
    source_type = SourceType.NOTION

    def __init__(self, service):
        self.service = service

    def is_available(self):
        return self.service.connection.connected

    def create_tools(self):
        # A graph belongs to one connection generation. Old graphs cannot switch identity.
        generation = self.service.connection.generation

        async def search(query: str) -> dict:
            """Search the connected Notion workspace. Fetch relevant pages before citing them."""
            return await self.service.search(query, generation=generation)

        async def fetch(id: str) -> dict:
            """Read a Notion page by ID or URL and return its content and source metadata."""
            return await self.service.fetch(id, generation=generation)

        return [StructuredTool.from_function(coroutine=search, name='notion_search'),
                StructuredTool.from_function(coroutine=fetch, name='notion_fetch')]
