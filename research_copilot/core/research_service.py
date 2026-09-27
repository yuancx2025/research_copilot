"""Process-wide research state for the single local user.

Owns the RAG system, the one active research run, the last completed result,
and study-plan drafts. Drafts stay server-side so export publishes exactly the
previewed plan.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from research_copilot.core.chat_interface import ChatInterface
from research_copilot.rag.document_manager import DocumentManager
from research_copilot.storage.export_store import ExportResult
from research_copilot.study_plans import generate_draft
from research_copilot.study_plans.schemas import StudyPlanDraft

logger = logging.getLogger(__name__)

MAX_DRAFTS = 20


class ResearchBusy(Exception):
    pass


class PlanError(Exception):
    pass


@dataclass
class ResearchRecord:
    query: str
    answer: str
    research_data: Dict[str, Any]
    generation: Optional[str]
    needs_clarification: bool = False

    @property
    def citations(self) -> List[dict]:
        return self.research_data.get("citations", [])

    @property
    def agent_results(self) -> Dict[str, list]:
        return self.research_data.get("agent_results", {})


@dataclass
class ResearchRun:
    """One research invocation. Events are kept so late subscribers replay them."""
    query: str
    events: List[Dict[str, Any]] = field(default_factory=list)
    finished: bool = False
    task: Optional[asyncio.Task] = None

    def __post_init__(self):
        self._changed = asyncio.Condition()

    async def publish(self, event):
        async with self._changed:
            self.events.append(event)
            self._changed.notify_all()

    async def finish(self):
        async with self._changed:
            self.finished = True
            self._changed.notify_all()

    async def subscribe(self):
        seen = 0
        while True:
            async with self._changed:
                await self._changed.wait_for(lambda: seen < len(self.events) or self.finished)
                batch, done = self.events[seen:], self.finished
            for event in batch:
                yield event
            seen += len(batch)
            if done and seen >= len(self.events):
                return


class ResearchService:
    def __init__(self, rag_system, notion_service=None, export_service=None, config=None,
                 documents=None, chat=None):
        self.rag = rag_system
        self.notion = notion_service
        self.exporter = export_service
        self.config = config
        self.documents = documents or DocumentManager(rag_system)
        self.chat = chat or ChatInterface(rag_system)
        self.lock = asyncio.Lock()
        self.run: Optional[ResearchRun] = None
        self.last: Optional[ResearchRecord] = None
        self.drafts: Dict[str, StudyPlanDraft] = {}
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
    def running(self) -> bool:
        return bool(self.run and not self.run.finished)

    def available_sources(self) -> List[str]:
        registry = getattr(self.rag, "tool_registry", None)
        return list(registry.available_ids()) if registry else []

    def can_preview(self, record: Optional[ResearchRecord]) -> bool:
        return bool(self.notion_enabled and record and record.citations
                    and record.generation == self.generation)

    # Research

    def start_research(self, message: str) -> ResearchRun:
        message = (message or "").strip()
        if not message:
            raise ValueError("Enter a research question.")
        if self.running:
            raise ResearchBusy("Research is already running.")
        run = ResearchRun(message)
        self.run = run
        run.task = asyncio.create_task(self._execute(run))
        return run

    async def _execute(self, run: ResearchRun):
        try:
            async with self.lock:
                async for event in self.chat.chat_stream(run.query):
                    if event["type"] == "result":
                        self.last = ResearchRecord(
                            query=run.query,
                            answer=event["answer"],
                            research_data={**event["research_data"], "answer_text": event["answer"]},
                            generation=self.generation,
                            needs_clarification=event["needs_clarification"],
                        )
                        event = {"type": "result", "record": self.last}
                    elif event["type"] == "error":
                        self.last = None
                    await run.publish(event)
        except Exception:
            logger.exception("Research run failed")
            self.last = None
            await run.publish({"type": "error", "message": "Research could not complete. Retry."})
        finally:
            await run.finish()

    async def reset(self):
        if self.running:
            raise ResearchBusy("Wait for the current research to finish.")
        self.chat.clear_session()
        self.last = None
        self.drafts.clear()

    async def invalidate(self):
        self.last = None
        self.drafts.clear()
        self.rag._mcp_prepared = False
        self.rag.reset_thread()
        self.rag.agent_graph = None
        self.rag._graph_generation = None

    # Study plans

    async def preview_plan(self) -> StudyPlanDraft:
        generation = self.generation
        if self.notion and not self.notion.connection.connected:
            raise PlanError("Connect Notion first.")
        last = self.last
        if not last or last.generation != generation or not last.citations:
            raise PlanError("Run research with the current connection first.")
        try:
            draft = await generate_draft(last.research_data, last.query, self.rag.llm, self.config,
                                         generation or "disconnected")
        except Exception:
            logger.exception("Study plan generation failed")
            raise PlanError("Could not generate a draft. Run research with the current connection first.") from None
        if self.notion and (not self.notion.connection.connected or generation != self.notion.connection.generation):
            raise PlanError("Connection changed while generating the preview.")
        self.drafts[draft.draft_id] = draft
        while len(self.drafts) > MAX_DRAFTS:
            self.drafts.pop(next(iter(self.drafts)))
        return draft

    async def search_destinations(self, query: str) -> List[Dict[str, str]]:
        if not self.notion:
            return []
        data = await self.notion.search(query)
        pages = data.get("results", []) if isinstance(data, dict) else []
        return [{"title": p.get("title") or "Untitled", "ref": p.get("url") or p.get("id")}
                for p in pages if p.get("url") or p.get("id")]

    async def export(self, draft_id: str, destination: str) -> ExportResult:
        draft = self.drafts.get(draft_id)
        if not draft or not self.exporter:
            return ExportResult(status="failure", message="Generate a preview first.")
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


def build_research_service(config, notion=None, exporter=None) -> ResearchService:
    from research_copilot.core.rag_system import RAGSystem
    rag = RAGSystem()
    rag.initialize()
    rag.notion_service = notion
    return ResearchService(rag, notion, exporter, config)
