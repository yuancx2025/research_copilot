from fastapi import APIRouter, Depends, HTTPException

from research_copilot.app.deps import get_research
from research_copilot.app.presenters import present_draft, present_export
from research_copilot.app.schemas import DraftOut, ExportOut, ExportRequest
from research_copilot.app.security import require_csrf
from research_copilot.core.research_service import PlanError

router = APIRouter(prefix='/study-plan', dependencies=[Depends(require_csrf)])


def _require_notion(service):
    if not service.notion_enabled:
        raise HTTPException(404, 'Notion export is disabled.')


@router.post('/preview', response_model=DraftOut)
async def preview_plan(service=Depends(get_research)):
    _require_notion(service)
    try:
        draft = await service.preview_plan()
    except PlanError as exc:
        raise HTTPException(409, str(exc)) from None
    return present_draft(draft)


@router.post('/export', response_model=ExportOut)
async def export_plan(body: ExportRequest, service=Depends(get_research)):
    _require_notion(service)
    return present_export(await service.export(body.draft_id, body.destination))
