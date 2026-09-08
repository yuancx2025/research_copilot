"""Generate once, preview the draft, and publish only on explicit submission."""
import asyncio
import hashlib
import json
from .schemas import StudyPlanDraft, ExportResult
from .markdown_renderer import render_markdown
from .study_plan_generator import StudyPlanGenerator
from .notion_mcp_service import page_id
from research_copilot.storage.export_store import STALE_UNKNOWN
from research_copilot.tools.mcp.client import AuthorizationRequired, MCPToolError


async def generate_draft(research_data, query, llm, config, generation):
    if not research_data.get('citations'):
        raise ValueError('Research with citations is required before generating a plan.')
    plan = await asyncio.to_thread(StudyPlanGenerator(llm, config).generate_study_plan, research_data, query)
    return StudyPlanDraft(plan=plan, markdown=render_markdown(plan), connection_generation=generation)


class ExportService:
    def __init__(self, ledger, notion=None, config=None):
        self.ledger, self.notion, self.config = ledger, notion, config
        self._in_flight = set()

    async def publish(self, draft, destination):
        backend = getattr(self.config, 'NOTION_BACKEND', 'disabled')
        try:
            if backend == 'mcp':
                if not self.notion.connection.connected or draft.connection_generation != self.notion.connection.generation:
                    raise AuthorizationRequired('Connection changed. Generate a new preview.')
                destination = await self.notion.destination(destination)
            elif backend == 'rest' and draft.connection_generation == 'rest':
                destination = page_id(destination)
            else:
                raise ValueError('Notion export is disabled.')
        except Exception:
            return ExportResult(status='failure', message='Check the destination and connection, then generate a new preview.')
        key = hashlib.sha256(json.dumps([draft.draft_id, destination, draft.connection_generation]).encode()).hexdigest()
        existing = await asyncio.to_thread(self.ledger.claim, key)
        if existing:
            if existing.status == 'pending' and key not in self._in_flight:
                existing = STALE_UNKNOWN
                await asyncio.to_thread(self.ledger.finish, key, existing)
            return existing
        result = None
        self._in_flight.add(key)
        try:
            try:
                if backend == 'mcp':
                    data = await self.notion.create_page(destination, draft.plan.title, draft.markdown, draft.connection_generation)
                    pages = data.get('pages', data.get('results', []))
                    page = pages[0] if pages else data
                    id, url = page.get('id'), page.get('url')
                    if not id or not url:
                        raise ValueError('Write response lacked a page identifier')
                    result = ExportResult(status='success', page_id=id, url=url)
                else:
                    from .notion_client import create_page
                    from .notion_renderer import render_study_plan
                    data = await asyncio.to_thread(create_page, destination, draft.plan.title,
                                                   render_study_plan(draft.plan), self.config)
                    result = ExportResult(status='failure' if data.get('error') else 'success',
                                          page_id=data.get('page_id'), url=data.get('url'),
                                          message='REST export was incomplete.' if data.get('error') else '')
            except (AuthorizationRequired, MCPToolError):
                result = ExportResult(status='failure', message='Notion rejected the export. Check permissions.')
            except asyncio.CancelledError:
                result = STALE_UNKNOWN
                raise
            except Exception:
                result = STALE_UNKNOWN
        finally:
            self._in_flight.discard(key)
            if result is not None:
                await asyncio.to_thread(self.ledger.finish, key, result)
        return result
