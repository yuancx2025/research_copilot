"""Saved research conversations for the single local user.

PostgreSQL holds conversations, runs, events, results, and drafts; LangGraph's
checkpointer holds execution context per conversation thread. This service keeps
only live coordination in memory: the one executing task and the notifiers that
wake event subscribers after each committed event.
"""
import asyncio
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

from research_copilot.core.chat_interface import ChatInterface, graph_config
from research_copilot.db.models import ACTIVE_RUN_STATUSES
from research_copilot.db.repositories import (INTERRUPTED_MESSAGE, ActiveRunExists, ResearchRepository,
                                              RunStateError)
from research_copilot.rag.document_manager import DocumentManager
from research_copilot.storage.export_store import ExportResult
from research_copilot.study_plans import generate_draft
from research_copilot.study_plans.schemas import StudyPlan, StudyPlanDraft

logger = logging.getLogger(__name__)

ResearchBusy = ActiveRunExists
SUBSCRIBER_POLL_SECONDS = 15.0


class PlanError(Exception):
    pass


def stale_context(previous: Optional[str], current: Optional[str]) -> bool:
    """Context built under a Notion connection must not survive a change of connection."""
    return previous is not None and previous != current


class LiveRun:
    """Wakes subscribers after an event for this run has been committed."""

    def __init__(self):
        self.version = 0
        self.finished = False
        self._changed = asyncio.Condition()

    async def notify(self, finished=False):
        async with self._changed:
            self.version += 1
            self.finished = self.finished or finished
            self._changed.notify_all()

    async def wait(self, version, timeout=SUBSCRIBER_POLL_SECONDS):
        async with self._changed:
            try:
                await asyncio.wait_for(
                    self._changed.wait_for(lambda: self.version != version or self.finished), timeout)
            except TimeoutError:
                pass


class ResearchService:
    def __init__(self, rag_system, repo: ResearchRepository, notion_service=None, export_service=None,
                 config=None, documents=None, chat=None):
        self.rag = rag_system
        self.repo = repo
        self.notion = notion_service
        self.exporter = export_service
        self.config = config
        self.documents = documents or DocumentManager(rag_system)
        self.chat = chat or ChatInterface(rag_system)
        self.lock = asyncio.Lock()
        self.live: Dict[str, LiveRun] = {}
        self.tasks: set = set()
        if notion_service:
            notion_service.connection.listeners.append(self.invalidate)

    @property
    def notion_backend(self) -> str:
        return getattr(self.config, "NOTION_BACKEND", "disabled")

    @property
    def notion_enabled(self) -> bool:
        return self.notion_backend in ("rest", "mcp")

    @property
    def generation(self) -> Optional[str]:
        return self.notion.connection.generation if self.notion else "rest"

    @property
    def connected(self) -> bool:
        return not self.notion or self.notion.connection.connected

    @property
    def running(self) -> bool:
        return bool(self.live)

    def available_sources(self) -> List[str]:
        registry = getattr(self.rag, "tool_registry", None)
        return list(registry.available_ids()) if registry else []

    def can_preview(self, run) -> bool:
        return bool(self.notion_enabled and self.connected and run.status == "completed" and run.result
                    and run.result.get("citations") and run.connection_generation == self.generation)

    def draft_exportable(self, draft) -> bool:
        return bool(self.notion_enabled and self.connected and draft.connection_generation == self.generation)

    # Conversations

    async def create_conversation(self, title: Optional[str] = None):
        return await self.repo.create_conversation(title)

    async def list_conversations(self):
        return await self.repo.list_conversations()

    async def conversation_detail(self, conversation_id: str):
        return await self.repo.conversation_detail(conversation_id)

    # Research runs

    async def submit(self, conversation_id: str, message: str, request_id: str,
                     retry_of_run_id: Optional[str] = None):
        """Commit the user message and run, then execute outside the transaction.

        Returns ``(run, created)``; a repeated request ID returns its existing run.
        """
        message = (message or "").strip()
        if not message and not retry_of_run_id:
            raise ValueError("Enter a research question.")
        run, created = await self.repo.submit_run(conversation_id, message, request_id, self.generation,
                                                  retry_of_run_id, stale_context)
        if created:
            self._start(run.id, run.query, resume=False)
        return run, created

    async def reply(self, run_id: str, message: str, request_id: str):
        """Resume the identified run waiting on a clarification."""
        message = (message or "").strip()
        if not message:
            raise ValueError("Enter a reply.")
        run, created = await self.repo.reply_run(run_id, message, request_id, self.generation, stale_context)
        if created:
            self._start(run.id, message, resume=True)
        return run, created

    async def get_run(self, run_id: str):
        return await self.repo.get_run(run_id)

    def _start(self, run_id: str, message: str, resume: bool):
        self.live[run_id] = LiveRun()
        task = asyncio.create_task(self._execute(run_id, message, resume))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def _execute(self, run_id: str, message: str, resume: bool):
        live = self.live[run_id]
        try:
            async with self.lock:
                run = await self.repo.mark_running(run_id)
                checkpoint = run.result_checkpoint_id if resume else run.base_checkpoint_id
                config = graph_config(run.thread_id, checkpoint)
                async for event in self.chat.chat_stream(message, config, resume=resume):
                    kind = event["type"]
                    if kind == "progress":
                        await self.repo.add_event(run_id, event)
                        await live.notify()
                    elif kind == "result":
                        research_data = {**event["research_data"], "answer_text": event["answer"]}
                        await self.repo.complete_run(run_id, event["answer"], research_data,
                                                     event["needs_clarification"], event.get("checkpoint_id"))
                        return
                    elif kind == "error":
                        await self.repo.fail_run(run_id, event["message"])
                        return
                await self.repo.fail_run(run_id, "Research ended without a result. Retry.")
        except asyncio.CancelledError:
            try:
                await asyncio.shield(self.repo.fail_run(run_id, INTERRUPTED_MESSAGE, status="interrupted"))
            except Exception:
                logger.exception("Could not mark run %s interrupted; the next startup will", run_id)
            raise
        except Exception:
            logger.exception("Research run failed")
            try:
                await self.repo.fail_run(run_id, "Research could not complete. Retry.")
            except Exception:
                logger.exception("Could not record the failure of run %s", run_id)
        finally:
            self.live.pop(run_id, None)
            await live.notify(finished=True)

    async def subscribe(self, run_id: str, after: int = 0) -> AsyncIterator[Dict[str, Any]]:
        """Replay committed events after ``after``, then follow live ones until the run settles."""
        if await self.repo.get_run(run_id) is None:
            raise LookupError("Research run not found.")
        seen = after
        while True:
            live = self.live.get(run_id)
            version = live.version if live else None
            for row in await self.repo.events_after(run_id, seen):
                seen = row.seq
                yield await self._event(run_id, row)
            run = await self.repo.get_run(run_id)
            if run.status not in ACTIVE_RUN_STATUSES:
                for row in await self.repo.events_after(run_id, seen):
                    seen = row.seq
                    yield await self._event(run_id, row)
                return
            if live is None:
                await asyncio.sleep(0.5)
            else:
                await live.wait(version)

    async def _event(self, run_id, row) -> Dict[str, Any]:
        from research_copilot.app.presenters import present_run
        event = {**row.payload, "seq": row.seq, "run_id": run_id}
        if event.get("type") == "result":
            event["run"] = present_run(await self.repo.get_run(run_id), self, last_seq=row.seq)
        return event

    async def shutdown(self):
        tasks = list(self.tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def invalidate(self):
        """Drop connection-bound tools. Saved history stays; stale threads rotate on next use."""
        invalidate_graph = getattr(self.rag, "invalidate_graph", None)
        if invalidate_graph:
            invalidate_graph()

    # Study plans

    async def preview_plan(self, run_id: str):
        run = await self.repo.get_run(run_id)
        if run is None:
            raise LookupError("Research run not found.")
        generation = self.generation
        if self.notion and not self.notion.connection.connected:
            raise PlanError("Connect Notion first.")
        if not self.can_preview(run):
            raise PlanError("Run research with the current connection first.")
        research_data = {k: v for k, v in run.result.items() if k not in ("v", "answer")}
        research_data.setdefault("answer_text", run.result.get("answer", ""))
        try:
            draft = await generate_draft(research_data, run.query, self.rag.llm, self.config,
                                         generation or "disconnected")
        except Exception:
            logger.exception("Study plan generation failed")
            raise PlanError("Could not generate a draft. Run research with the current connection first.") from None
        if self.notion and (not self.notion.connection.connected or generation != self.notion.connection.generation):
            raise PlanError("Connection changed while generating the preview.")
        record = self.notion.connection.record if self.notion else None
        return await self.repo.save_draft(run, draft, record.connection_id if record else None)

    async def get_draft(self, draft_id: str):
        return await self.repo.get_draft(draft_id)

    async def search_destinations(self, query: str) -> List[Dict[str, str]]:
        if not self.notion:
            return []
        data = await self.notion.search(query)
        pages = data.get("results", []) if isinstance(data, dict) else []
        return [{"title": p.get("title") or "Untitled", "ref": p.get("url") or p.get("id")}
                for p in pages if p.get("url") or p.get("id")]

    async def export(self, draft_id: str, destination: str) -> ExportResult:
        row = await self.repo.get_draft(draft_id) if self.exporter else None
        if row is None:
            return ExportResult(status="failure", message="Generate a preview first.")
        plan = StudyPlan.model_validate({k: v for k, v in row.plan.items() if k != "v"})
        draft = StudyPlanDraft(draft_id=row.id, plan=plan, markdown=row.markdown,
                               connection_generation=row.connection_generation)
        try:
            return await self.exporter.publish(draft, destination)
        except Exception:
            logger.exception("Export failed")
            return ExportResult(status="failure", message="Export could not complete. Check the connection and destination.")

    # Documents

    def list_documents(self) -> List[str]:
        return self.documents.list_documents()

    def add_documents(self, paths, progress_callback=None):
        return self.documents.add_documents(paths, progress_callback=progress_callback)

    def clear_documents(self):
        self.documents.clear_all()


def build_research_service(config, notion=None, exporter=None, repo=None, checkpointer=None) -> ResearchService:
    from research_copilot.core.rag_system import RAGSystem
    rag = RAGSystem()
    rag.initialize(checkpointer=checkpointer)
    rag.notion_service = notion
    return ResearchService(rag, repo, notion, exporter, config)


__all__ = ["ResearchService", "ResearchBusy", "RunStateError", "PlanError", "build_research_service",
           "stale_context"]
