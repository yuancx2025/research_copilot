from typing import List

from fastapi import APIRouter, Depends, HTTPException

from research_copilot.app.deps import get_research
from research_copilot.app.presenters import present_conversation, present_conversation_detail, present_run
from research_copilot.app.schemas import ConversationCreate, ConversationDetailOut, ConversationOut, RunCreate, RunOut
from research_copilot.app.security import require_csrf
from research_copilot.core.research_service import ResearchBusy, RunStateError

router = APIRouter(prefix='/conversations')


@router.post('', status_code=201, response_model=ConversationOut, dependencies=[Depends(require_csrf)])
async def create_conversation(body: ConversationCreate | None = None, service=Depends(get_research)):
    return present_conversation(await service.create_conversation(body.title if body else None))


@router.get('', response_model=List[ConversationOut])
async def list_conversations(service=Depends(get_research)):
    return [present_conversation(c) for c in await service.list_conversations()]


@router.get('/{conversation_id}', response_model=ConversationDetailOut)
async def conversation_detail(conversation_id: str, service=Depends(get_research)):
    detail = await service.conversation_detail(conversation_id)
    if detail is None:
        raise HTTPException(404, 'Conversation not found.')
    return present_conversation_detail(detail, service)


@router.post('/{conversation_id}/runs', status_code=202, response_model=RunOut,
             dependencies=[Depends(require_csrf)])
async def submit_run(conversation_id: str, body: RunCreate, service=Depends(get_research)):
    try:
        run, _ = await service.submit(conversation_id, body.message, body.request_id, body.retry_of_run_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from None
    except (ResearchBusy, RunStateError) as exc:
        raise HTTPException(409, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return present_run(run, service)
