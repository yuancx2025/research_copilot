from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from research_copilot.app.contracts import stream_responses

from research_copilot.app.deps import get_research
from research_copilot.app.presenters import present_run
from research_copilot.app.schemas import ReplyCreate, RunOut
from research_copilot.app.security import require_csrf
from research_copilot.app.sse import event_stream
from research_copilot.core.research_service import ResearchBusy, RunStateError

router = APIRouter(prefix='/runs')


async def _run_or_404(service, run_id):
    run = await service.get_run(run_id)
    if run is None:
        raise HTTPException(404, 'Research run not found.')
    return run


@router.get('/{run_id}', response_model=RunOut)
async def get_run(run_id: str, service=Depends(get_research)):
    run = await _run_or_404(service, run_id)
    return present_run(run, service, await service.repo.last_seq(run_id))


@router.get('/{run_id}/events', response_class=StreamingResponse, responses=stream_responses('ResearchEventOut'))
async def run_events(run_id: str, after: int = Query(0, ge=0), service=Depends(get_research)):
    """Replay committed events with ``seq > after``, then follow until the run settles."""
    await _run_or_404(service, run_id)
    return event_stream(service.subscribe(run_id, after))


@router.post('/{run_id}/reply', status_code=202, response_model=RunOut, dependencies=[Depends(require_csrf)])
async def reply(run_id: str, body: ReplyCreate, service=Depends(get_research)):
    try:
        run, _ = await service.reply(run_id, body.message, body.request_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from None
    except (ResearchBusy, RunStateError) as exc:
        raise HTTPException(409, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return present_run(run, service)
