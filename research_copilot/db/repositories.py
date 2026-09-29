"""Transactions over saved conversations, research runs, events, and study-plan drafts."""
import json
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from research_copilot.db.models import (ACTIVE_RUN_STATUSES, PLAN_VERSION, RESULT_VERSION, Conversation,
                                        ExportRow, Message, ResearchRun, RunEvent, StudyPlanDraftRow, new_id)

DEFAULT_TITLE = 'New conversation'
TITLE_LENGTH = 80
INTERRUPTED_MESSAGE = 'Research was interrupted when the server stopped. Retry to run it again.'


class ActiveRunExists(Exception):
    pass


class RunStateError(Exception):
    pass


def to_json(value: Any) -> Any:
    """Normalize research payloads (pydantic models, datetimes) into plain JSON."""
    def default(obj):
        if hasattr(obj, 'model_dump'):
            return obj.model_dump(mode='json')
        if isinstance(obj, datetime):
            return obj.isoformat()
        return str(obj)
    return json.loads(json.dumps(value, default=default))


def _constraint(exc: IntegrityError) -> str:
    diag = getattr(getattr(exc, 'orig', None), 'diag', None)
    return getattr(diag, 'constraint_name', '') or ''


def _now():
    return datetime.now(timezone.utc)


def _title(query: str) -> str:
    query = ' '.join(query.split())
    return query if len(query) <= TITLE_LENGTH else query[:TITLE_LENGTH - 1] + '…'


class ResearchRepository:
    def __init__(self, db):
        self.db = db

    # Conversations

    async def create_conversation(self, title: Optional[str] = None) -> Conversation:
        async with self.db.transaction() as session:
            conversation = Conversation(id=new_id(), title=(title or '').strip() or DEFAULT_TITLE, thread_id=new_id())
            session.add(conversation)
        return conversation

    async def list_conversations(self) -> list[Conversation]:
        async with self.db.session() as session:
            rows = await session.scalars(select(Conversation).order_by(Conversation.updated_at.desc()))
            return list(rows)

    async def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        async with self.db.session() as session:
            return await session.get(Conversation, conversation_id)

    async def conversation_detail(self, conversation_id: str):
        async with self.db.session() as session:
            conversation = await session.get(Conversation, conversation_id)
            if conversation is None:
                return None
            messages = list(await session.scalars(
                select(Message).where(Message.conversation_id == conversation_id).order_by(Message.position)))
            runs = list(await session.scalars(
                select(ResearchRun).where(ResearchRun.conversation_id == conversation_id)
                .order_by(ResearchRun.created_at, ResearchRun.id)))
            drafts = list(await session.scalars(
                select(StudyPlanDraftRow).where(StudyPlanDraftRow.conversation_id == conversation_id)
                .order_by(StudyPlanDraftRow.created_at)))
            last_seq = dict((await session.execute(
                select(RunEvent.run_id, func.max(RunEvent.seq))
                .join(ResearchRun, ResearchRun.id == RunEvent.run_id)
                .where(ResearchRun.conversation_id == conversation_id)
                .group_by(RunEvent.run_id))).all())
            return conversation, messages, runs, drafts, last_seq

    # Runs

    async def get_run(self, run_id: str) -> Optional[ResearchRun]:
        async with self.db.session() as session:
            return await session.get(ResearchRun, run_id)

    async def last_seq(self, run_id: str) -> int:
        async with self.db.session() as session:
            return (await session.scalar(select(func.max(RunEvent.seq)).where(RunEvent.run_id == run_id))) or 0

    async def active_run(self) -> Optional[ResearchRun]:
        async with self.db.session() as session:
            return await session.scalar(select(ResearchRun).where(ResearchRun.status.in_(ACTIVE_RUN_STATUSES)))

    async def _next_position(self, session, conversation_id: str) -> int:
        current = await session.scalar(
            select(func.max(Message.position)).where(Message.conversation_id == conversation_id))
        return -1 if current is None else current

    async def _append_message(self, session, conversation_id, role, content, run_id=None, request_id=None,
                              clarification=False):
        position = await self._next_position(session, conversation_id) + 1
        message = Message(id=new_id(), conversation_id=conversation_id, run_id=run_id, request_id=request_id,
                          position=position, role=role, content=content, clarification=clarification)
        session.add(message)
        await session.flush()
        return message

    async def _add_event(self, session, run_id: str, payload: dict) -> int:
        seq = (await session.scalar(select(func.max(RunEvent.seq)).where(RunEvent.run_id == run_id)) or 0) + 1
        session.add(RunEvent(run_id=run_id, seq=seq, payload=to_json(payload)))
        await session.flush()
        return seq

    async def submit_run(self, conversation_id: str, query: str, request_id: str, generation: Optional[str],
                         retry_of_run_id: Optional[str] = None,
                         stale_context: Callable[[Optional[str], Optional[str]], bool] = lambda old, new: False):
        """Commit the user message and a queued run. Returns (run, created)."""
        try:
            async with self.db.transaction() as session:
                conversation = await session.get(Conversation, conversation_id, with_for_update=True)
                if conversation is None:
                    raise LookupError('Conversation not found.')
                existing = await session.scalar(select(ResearchRun).where(
                    ResearchRun.conversation_id == conversation_id, ResearchRun.request_id == request_id))
                if existing:
                    return existing, False
                if retry_of_run_id:
                    original = await session.get(ResearchRun, retry_of_run_id)
                    if original is None or original.conversation_id != conversation_id:
                        raise LookupError('The run to retry was not found in this conversation.')
                    if original.status not in ('interrupted', 'failed'):
                        raise RunStateError('Only interrupted or failed research can be retried.')
                    query = original.query
                if await session.scalar(select(ResearchRun.id).where(ResearchRun.status.in_(ACTIVE_RUN_STATUSES))):
                    raise ActiveRunExists('Research is already running.')
                if stale_context(conversation.context_generation, generation):
                    conversation.thread_id = new_id()
                    conversation.stable_checkpoint_id = None
                conversation.context_generation = generation
                if conversation.title == DEFAULT_TITLE:
                    conversation.title = _title(query)
                conversation.updated_at = _now()
                await session.execute(update(ResearchRun).where(
                    ResearchRun.conversation_id == conversation_id,
                    ResearchRun.status == 'awaiting_clarification').values(status='superseded'))
                run = ResearchRun(id=new_id(), conversation_id=conversation_id, request_id=request_id,
                                  retry_of_run_id=retry_of_run_id, status='queued', query=query,
                                  thread_id=conversation.thread_id, connection_generation=generation,
                                  base_checkpoint_id=conversation.stable_checkpoint_id)
                session.add(run)
                await session.flush()
                await self._append_message(session, conversation_id, 'user', query, run.id, request_id)
            return run, True
        except IntegrityError as exc:
            name = _constraint(exc)
            if name == 'uq_research_runs_one_active':
                raise ActiveRunExists('Research is already running.') from None
            if name in ('uq_research_runs_request', 'uq_messages_request'):
                async with self.db.session() as session:
                    run = await session.scalar(select(ResearchRun).where(
                        ResearchRun.conversation_id == conversation_id, ResearchRun.request_id == request_id))
                if run:
                    return run, False
            raise

    async def reply_run(self, run_id: str, content: str, request_id: str, generation: Optional[str],
                        stale_context: Callable[[Optional[str], Optional[str]], bool] = lambda old, new: False):
        """Queue a clarification reply on its waiting run. Returns (run, created)."""
        run = None
        try:
            async with self.db.transaction() as session:
                run = await session.get(ResearchRun, run_id, with_for_update=True)
                if run is None:
                    raise LookupError('Research run not found.')
                duplicate = await session.scalar(select(Message.id).where(
                    Message.conversation_id == run.conversation_id, Message.request_id == request_id))
                if duplicate:
                    return run, False
                if run.status != 'awaiting_clarification':
                    raise RunStateError('This research is not waiting for a reply.')
                if stale_context(run.connection_generation, generation):
                    run.status = 'superseded'
                    raise RunStateError('The Notion connection changed. Ask the question again.')
                if await session.scalar(select(ResearchRun.id).where(ResearchRun.status.in_(ACTIVE_RUN_STATUSES))):
                    raise ActiveRunExists('Research is already running.')
                run.status = 'queued'
                run.needs_clarification = False
                await session.execute(update(Conversation).where(Conversation.id == run.conversation_id)
                                      .values(updated_at=_now()))
                await self._append_message(session, run.conversation_id, 'user', content, run.id, request_id)
            return run, True
        except IntegrityError as exc:
            if _constraint(exc) == 'uq_research_runs_one_active':
                raise ActiveRunExists('Research is already running.') from None
            if _constraint(exc) == 'uq_messages_request':
                return await self.get_run(run_id), False
            raise
        except RunStateError:
            if run is not None and run.status == 'superseded':
                async with self.db.transaction() as session:
                    await session.execute(update(ResearchRun).where(ResearchRun.id == run_id)
                                          .values(status='superseded'))
            raise

    async def mark_running(self, run_id: str) -> ResearchRun:
        async with self.db.transaction() as session:
            run = await session.get(ResearchRun, run_id, with_for_update=True)
            run.status = 'running'
        return run

    async def add_event(self, run_id: str, payload: dict) -> int:
        async with self.db.transaction() as session:
            return await self._add_event(session, run_id, payload)

    async def events_after(self, run_id: str, after: int = 0) -> list[RunEvent]:
        async with self.db.session() as session:
            rows = await session.scalars(select(RunEvent).where(RunEvent.run_id == run_id, RunEvent.seq > after)
                                         .order_by(RunEvent.seq))
            return list(rows)

    async def complete_run(self, run_id: str, answer: str, research_data: dict, needs_clarification: bool,
                           checkpoint_id: Optional[str]) -> int:
        """Commit the result, assistant message, stable checkpoint, and terminal event together."""
        async with self.db.transaction() as session:
            run = await session.get(ResearchRun, run_id, with_for_update=True)
            run.status = 'awaiting_clarification' if needs_clarification else 'completed'
            run.needs_clarification = needs_clarification
            run.result = {'v': RESULT_VERSION, 'answer': answer, **to_json(research_data)}
            run.result_checkpoint_id = checkpoint_id
            run.error = None
            run.finished_at = _now()
            values = {'updated_at': _now()}
            if checkpoint_id:
                values['stable_checkpoint_id'] = checkpoint_id
            await session.execute(update(Conversation).where(
                Conversation.id == run.conversation_id, Conversation.thread_id == run.thread_id).values(**values))
            await self._append_message(session, run.conversation_id, 'assistant', answer, run.id,
                                       clarification=needs_clarification)
            return await self._add_event(session, run_id, {'type': 'result'})

    async def fail_run(self, run_id: str, message: str, status: str = 'failed') -> int:
        async with self.db.transaction() as session:
            run = await session.get(ResearchRun, run_id, with_for_update=True)
            run.status = status
            run.error = message
            run.finished_at = _now()
            await self._append_message(session, run.conversation_id, 'error', message, run.id)
            return await self._add_event(session, run_id, {'type': 'error', 'message': message, 'status': status})

    async def interrupt_unfinished(self) -> list[str]:
        """After a restart nothing is executing, so queued/running runs become interrupted."""
        async with self.db.session() as session:
            ids = list(await session.scalars(
                select(ResearchRun.id).where(ResearchRun.status.in_(ACTIVE_RUN_STATUSES))))
        for run_id in ids:
            await self.fail_run(run_id, INTERRUPTED_MESSAGE, status='interrupted')
        return ids

    async def expire_pending_exports(self, message: str) -> int:
        async with self.db.transaction() as session:
            result = await session.execute(update(ExportRow).where(ExportRow.status == 'pending')
                                           .values(status='unknown', message=message, updated_at=_now()))
            return result.rowcount

    # Drafts

    async def save_draft(self, run: ResearchRun, draft, connection_id: Optional[str]) -> StudyPlanDraftRow:
        async with self.db.transaction() as session:
            row = StudyPlanDraftRow(
                id=draft.draft_id, run_id=run.id, conversation_id=run.conversation_id, title=draft.plan.title,
                plan={'v': PLAN_VERSION, **to_json(draft.plan.model_dump(mode='json'))}, markdown=draft.markdown,
                connection_id=connection_id, connection_generation=draft.connection_generation)
            session.add(row)
        return row

    async def get_draft(self, draft_id: str) -> Optional[StudyPlanDraftRow]:
        async with self.db.session() as session:
            return await session.get(StudyPlanDraftRow, draft_id)
