from fastapi import APIRouter, Depends, HTTPException, Response

from research_copilot.app.deps import get_research
from research_copilot.app.presenters import present_event, present_record
from research_copilot.app.schemas import LastResearchOut, ResearchRequest
from research_copilot.app.security import require_csrf
from research_copilot.app.sse import event_stream
from research_copilot.core.research_service import ResearchBusy

router = APIRouter()


async def _presented(events, service):
    async for event in events:
        yield present_event(event, service)


@router.post('/research', dependencies=[Depends(require_csrf)])
async def start_research(body: ResearchRequest, service=Depends(get_research)):
    try:
        run = service.start_research(body.message)
    except ResearchBusy as exc:
        raise HTTPException(409, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return event_stream(_presented(run.subscribe(), service))


@router.get('/research/events')
async def research_events(service=Depends(get_research)):
    if service.run is None:
        raise HTTPException(404, 'No research has run yet.')
    return event_stream(_presented(service.run.subscribe(), service))


@router.get('/research/last', response_model=LastResearchOut)
async def last_research(service=Depends(get_research)):
    record = service.last
    return LastResearchOut(running=service.running,
                           result=present_record(record, service) if record else None)


@router.post('/session/reset', status_code=204, dependencies=[Depends(require_csrf)])
async def reset_session(service=Depends(get_research)):
    try:
        await service.reset()
    except ResearchBusy as exc:
        raise HTTPException(409, str(exc)) from None
    return Response(status_code=204)
