"""Opt-in live Notion smoke test. Automated tests never export or disconnect.

Enable after connecting a workspace in the local UI:

    NOTION_LIVE_TEST=1 NOTION_LIVE_PAGE_ID=<page-uuid-or-url> pytest tests/notion/test_live_smoke.py -m live

Export only with an additional explicit flag:

    NOTION_LIVE_EXPORT=1
"""
import os
import pytest

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(os.getenv('NOTION_LIVE_TEST') != '1', reason='Set NOTION_LIVE_TEST=1 with a connected local workspace'),
]


@pytest.mark.asyncio
async def test_live_fetch_and_optional_export():
    page = os.getenv('NOTION_LIVE_PAGE_ID', '').strip()
    if not page:
        pytest.skip('Set NOTION_LIVE_PAGE_ID to a page the connected workspace can read')

    from research_copilot.tools.mcp.oauth import ConnectionService
    from research_copilot.notion.notion_mcp_service import NotionMCPService
    from research_copilot.notion.export_service import ExportService
    from research_copilot.notion.markdown_renderer import render_markdown
    from research_copilot.notion.schemas import StudyPlan, StudyPlanDraft
    from research_copilot.storage.export_store import ExportStore
    from types import SimpleNamespace
    from pathlib import Path

    connection = ConnectionService()
    await connection.initialize()
    assert connection.connected, 'Connect Notion in the local UI first, then rerun while the grant remains valid'
    service = NotionMCPService(connection)
    data = await service.fetch(page)
    assert data.get('title') and data.get('url'), 'Fetch must return page title and URL before treating it as evidence'
    if os.getenv('NOTION_LIVE_EXPORT') != '1':
        return

    destination = os.getenv('NOTION_LIVE_PARENT_PAGE_ID', page).strip()
    plan = StudyPlan(
        title='Live smoke test',
        overview='Created only because NOTION_LIVE_EXPORT=1 was set.',
        outcome_objectives=['Verify MCP page creation'],
        phases=[],
        citations=[],
        next_steps=['Inspect the created page, then disconnect from the UI'],
    )
    draft = StudyPlanDraft(plan=plan, markdown=render_markdown(plan), connection_generation=connection.generation)
    exporter = ExportService(
        ExportStore(Path(os.getenv('RESEARCH_COPILOT_DATA_DIR', str(Path.home() / '.local/share/research-copilot'))) / 'live-smoke.sqlite3'),
        service,
        SimpleNamespace(NOTION_BACKEND='mcp'),
    )
    result = await exporter.publish(draft, destination)
    assert result.status in {'success', 'unknown'}
    if result.status == 'success':
        assert result.page_id and result.url
