import asyncio
import sqlite3
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
import pytest
from research_copilot.study_plans.schemas import StudyPlan, StudyPlanDraft
from research_copilot.study_plans.markdown_renderer import render_markdown
from research_copilot.sources.notion.exporter import ExportService
from research_copilot.study_plans import generate_draft
from research_copilot.storage.export_store import (ExportResult, PostgresExportLedger, STALE_UNKNOWN,
                                                  import_sqlite_ledger)

PAGE = '11111111-2222-3333-4444-555555555555'


def draft():
    plan = StudyPlan(title='Learn MCP', overview='OAuth and tools', outcome_objectives=['Understand'],
                     phases=[], citations=[], next_steps=['Test'])
    return StudyPlanDraft(plan=plan, markdown=render_markdown(plan), connection_generation='generation')


def exporter(db, response=None):
    notion = SimpleNamespace(connection=SimpleNamespace(connected=True, generation='generation'),
                             destination=AsyncMock(return_value=PAGE),
                             create_page=AsyncMock(return_value=response or {'pages':[{'id':PAGE,'url':'https://notion.so/'+PAGE}]}))
    return ExportService(PostgresExportLedger(db), notion, SimpleNamespace(NOTION_BACKEND='mcp'))


@pytest.mark.asyncio
async def test_preview_generated_once_and_published_exactly(adb):
    expected = draft().plan
    with patch('research_copilot.study_plans.generator.StudyPlanGenerator') as generator:
        generator.return_value.generate_study_plan.return_value = expected
        preview = await generate_draft({'citations':[{'title':'Notes'}]}, 'MCP', None, None, 'generation')
        service = exporter(adb)
        result = await service.publish(preview, PAGE)
        assert result.status == 'success'
        service.notion.create_page.assert_awaited_once_with(PAGE, expected.title, preview.markdown, 'generation')
        generator.return_value.generate_study_plan.assert_called_once()
        assert (await service.publish(preview, PAGE)).url == result.url
        service.notion.create_page.assert_awaited_once()


@pytest.mark.asyncio
async def test_duplicate_pending_and_unknown_persist_across_restart(adb):
    service = exporter(adb)
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
    restarted = exporter(adb)
    assert (await restarted.publish(preview, PAGE)).status == 'unknown'
    restarted.notion.create_page.assert_not_awaited()


@pytest.mark.asyncio
async def test_stale_generation_and_bad_destination_never_dispatch(adb):
    service = exporter(adb)
    preview = draft()
    service.notion.connection.generation = 'replacement'
    assert (await service.publish(preview, PAGE)).status == 'failure'
    service.notion.create_page.assert_not_awaited()
    service.notion.connection.generation = preview.connection_generation
    service.notion.destination.side_effect = ValueError('not a page')
    assert (await service.publish(preview, PAGE)).status == 'failure'
    service.notion.create_page.assert_not_awaited()


@pytest.mark.asyncio
async def test_sqlite_import_keeps_duplicate_protection(adb, tmp_path):
    path = tmp_path / 'exports.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE exports (key TEXT PRIMARY KEY, result TEXT NOT NULL)')
        pending = ExportResult(status='pending', message='Export is already in progress.')
        done = ExportResult(status='success', page_id=PAGE, url='https://notion.so/' + PAGE)
        db.execute('INSERT INTO exports VALUES (?, ?)', ('legacy-pending', pending.model_dump_json()))
        db.execute('INSERT INTO exports VALUES (?, ?)', ('legacy-done', done.model_dump_json()))
    imported, skipped = await import_sqlite_ledger(path, adb)
    assert (imported, skipped) == (2, 0)
    again = await import_sqlite_ledger(path, adb)
    assert again == (0, 2)
    ledger = PostgresExportLedger(adb)
    assert (await ledger.get('legacy-pending')).status == 'unknown'
    assert (await ledger.get('legacy-pending')).message == STALE_UNKNOWN.message
    preview = draft()
    preview.draft_id = 'new-draft'
    service = exporter(adb)
    # A legacy key is not a new draft's key, so the imported success still blocks that exact key.
    await ledger.finish('legacy-done', done)
    assert (await ledger.claim('legacy-done')).status == 'success'
    assert (await service.publish(preview, PAGE)).status == 'success'


def test_rest_partial_append_is_failure():
    from research_copilot.sources.notion.rest_client import create_page
    response = Mock(status_code=200)
    response.json.return_value = {'id':PAGE,'url':'https://notion.so/'+PAGE}
    config = SimpleNamespace(NOTION_API_KEY='test', NOTION_PARENT_PAGE_ID=PAGE)
    with patch('research_copilot.sources.notion.rest_client.requests.post', return_value=response), \
         patch('research_copilot.sources.notion.rest_client.append_blocks', return_value={'error':'rejected'}) as append:
        result = create_page(PAGE, 'Plan', [{}]*101, config)
    assert result['error'] and result['partial'] and result['page_id'] == PAGE
    append.assert_called_once()
