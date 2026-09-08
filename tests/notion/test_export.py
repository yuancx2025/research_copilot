import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
import pytest
from research_copilot.notion.schemas import StudyPlan, StudyPlanDraft
from research_copilot.notion.markdown_renderer import render_markdown
from research_copilot.notion.export_service import ExportService, generate_draft
from research_copilot.storage.export_store import ExportStore

PAGE = '11111111-2222-3333-4444-555555555555'


def draft():
    plan = StudyPlan(title='Learn MCP', overview='OAuth and tools', outcome_objectives=['Understand'],
                     phases=[], citations=[], next_steps=['Test'])
    return StudyPlanDraft(plan=plan, markdown=render_markdown(plan), connection_generation='generation')


def exporter(tmp_path, response=None):
    notion = SimpleNamespace(connection=SimpleNamespace(connected=True, generation='generation'),
                             destination=AsyncMock(return_value=PAGE),
                             create_page=AsyncMock(return_value=response or {'pages':[{'id':PAGE,'url':'https://notion.so/'+PAGE}]}))
    return ExportService(ExportStore(tmp_path/'ledger.sqlite3'), notion, SimpleNamespace(NOTION_BACKEND='mcp'))


@pytest.mark.asyncio
async def test_preview_generated_once_and_published_exactly(tmp_path):
    expected = draft().plan
    with patch('research_copilot.notion.export_service.StudyPlanGenerator') as generator:
        generator.return_value.generate_study_plan.return_value = expected
        preview = await generate_draft({'citations':[{'title':'Notes'}]}, 'MCP', None, None, 'generation')
        service = exporter(tmp_path)
        result = await service.publish(preview, PAGE)
        assert result.status == 'success'
        service.notion.create_page.assert_awaited_once_with(PAGE, expected.title, preview.markdown, 'generation')
        generator.return_value.generate_study_plan.assert_called_once()
        assert (await service.publish(preview, PAGE)).url == result.url
        service.notion.create_page.assert_awaited_once()


@pytest.mark.asyncio
async def test_duplicate_pending_and_unknown_persist_across_restart(tmp_path):
    service = exporter(tmp_path)
    started, release = asyncio.Event(), asyncio.Event()
    async def timeout(*args):
        started.set()
        await release.wait()
        raise TimeoutError()
    service.notion.create_page.side_effect = timeout
    preview = draft()
    first = asyncio.create_task(service.publish(preview, PAGE))
    await started.wait()
    duplicate = await service.publish(preview, PAGE)
    assert duplicate.status == 'pending'
    assert duplicate.message.startswith('Export is already in progress')
    service.notion.create_page.assert_awaited_once()
    release.set()
    assert (await first).status == 'unknown'
    restarted = exporter(tmp_path)
    assert (await restarted.publish(preview, PAGE)).status == 'unknown'
    restarted.notion.create_page.assert_not_awaited()


@pytest.mark.asyncio
async def test_stale_generation_and_bad_destination_never_dispatch(tmp_path):
    service = exporter(tmp_path)
    preview = draft()
    service.notion.connection.generation = 'replacement'
    assert (await service.publish(preview, PAGE)).status == 'failure'
    service.notion.create_page.assert_not_awaited()
    service.notion.connection.generation = preview.connection_generation
    service.notion.destination.side_effect = ValueError('not a page')
    assert (await service.publish(preview, PAGE)).status == 'failure'
    service.notion.create_page.assert_not_awaited()


def test_rest_partial_append_is_failure():
    from research_copilot.notion.notion_client import create_page
    response = Mock(status_code=200)
    response.json.return_value = {'id':PAGE,'url':'https://notion.so/'+PAGE}
    config = SimpleNamespace(NOTION_API_KEY='test', NOTION_PARENT_PAGE_ID=PAGE)
    with patch('research_copilot.notion.notion_client.requests.post', return_value=response), \
         patch('research_copilot.notion.notion_client.append_blocks', return_value={'error':'rejected'}) as append:
        result = create_page(PAGE, 'Plan', [{}]*101, config)
    assert result['error'] and result['partial'] and result['page_id'] == PAGE
    append.assert_called_once()

