from fastapi import APIRouter, Depends, HTTPException

from research_copilot.app.deps import get_research
from research_copilot.app.presenters import present_draft, present_export
from research_copilot.app.schemas import DraftOut, ExportOut, ExportRequest, PreviewRequest
from research_copilot.app.security import require_csrf
from research_copilot.core.research_service import PlanError

router = APIRouter(prefix='/study-plan')


def _require_notion(service):
    if not service.notion_enabled:
        raise HTTPException(404, 'Notion export is disabled.')


@router.post('/preview', response_model=DraftOut, dependencies=[Depends(require_csrf)])
async def preview_plan(body: PreviewRequest, service=Depends(get_research)):
    """Generate a plan from a saved run and store the exact preview before returning it."""
    _require_notion(service)
    try:
        draft = await service.preview_plan(body.run_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from None
    except PlanError as exc:
        raise HTTPException(409, str(exc)) from None
    return present_draft(draft, service)


@router.get('/drafts/{draft_id}', response_model=DraftOut)
async def get_draft(draft_id: str, service=Depends(get_research)):
    _require_notion(service)
    draft = await service.get_draft(draft_id)
    if draft is None:
        raise HTTPException(404, 'Draft not found.')
    return present_draft(draft, service)


@router.post('/export', response_model=ExportOut, dependencies=[Depends(require_csrf)])
async def export_plan(body: ExportRequest, service=Depends(get_research)):
    _require_notion(service)
    return present_export(await service.export(body.draft_id, body.destination))
