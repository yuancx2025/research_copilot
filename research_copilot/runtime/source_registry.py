"""Source catalog container. Does not import source packages."""
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from langchain_core.tools import BaseTool
from research_copilot.runtime.base_toolkit import BaseToolkit
import logging

logger = logging.getLogger(__name__)


@dataclass
class SourceContext:
    llm: Any
    config: Any
    collection: Any = None
    retriever: Any = None
    extras: dict = field(default_factory=dict)


@dataclass
class SourceDescriptor:
    id: str
    node_name: str
    is_default: bool
    is_available: Callable[[SourceContext], bool]
    create_toolkit: Optional[Callable[[SourceContext], BaseToolkit]]
    create_agent: Callable[[SourceContext, List[BaseTool]], Any]


class SourceRegistry:
    """Holds descriptors and one toolkit per registered source."""

    def __init__(self):
        self._descriptors: Dict[str, SourceDescriptor] = {}
        self._order: List[str] = []
        self._toolkits: Dict[str, BaseToolkit] = {}
        self._tools_cache: Dict[str, List[BaseTool]] = {}

    def register(self, descriptor: SourceDescriptor) -> None:
        if descriptor.id not in self._descriptors:
            self._order.append(descriptor.id)
        self._descriptors[descriptor.id] = descriptor

    def clear(self) -> None:
        self._descriptors.clear()
        self._order.clear()
        self._toolkits.clear()
        self._tools_cache.clear()

    def ensure_toolkits(self, context: SourceContext) -> None:
        for source_id in list(self._toolkits):
            desc = self._descriptors.get(source_id)
            if desc is None or not desc.is_available(context):
                self._toolkits.pop(source_id, None)
                self._tools_cache.pop(source_id, None)
        for source_id in self._order:
            desc = self._descriptors[source_id]
            if source_id in self._toolkits or not desc.is_available(context):
                continue
            if desc.create_toolkit is None:
                continue
            try:
                toolkit = desc.create_toolkit(context)
            except Exception as exc:
                logger.warning("Failed to initialize %s toolkit: %s", source_id, exc)
                continue
            if not toolkit.is_available():
                logger.warning("Toolkit %s not available (missing config?)", source_id)
                continue
            self._toolkits[source_id] = toolkit
            self._tools_cache.pop(source_id, None)

    def get_toolkit(self, source_id: str) -> Optional[BaseToolkit]:
        return self._toolkits.get(source_id)

    def tools_for(self, source_id: str) -> List[BaseTool]:
        if source_id not in self._tools_cache:
            toolkit = self._toolkits.get(source_id)
            self._tools_cache[source_id] = toolkit.create_tools() if toolkit else []
        return self._tools_cache[source_id]

    def available_ids(self, context: Optional[SourceContext] = None) -> List[str]:
        if context is None:
            return [source_id for source_id in self._order if source_id in self._toolkits]
        return [source_id for source_id in self._order if self._descriptors[source_id].is_available(context)]

    def default_ids(self, available: Optional[List[str]] = None) -> List[str]:
        pool = set(available if available is not None else self._toolkits)
        return [source_id for source_id in self._order
                if self._descriptors[source_id].is_default and source_id in pool]

    def node_name(self, source_id: str) -> str:
        return self._descriptors[source_id].node_name

    def list_available_sources(self) -> List[str]:
        return list(self.available_ids())

    async def initialize_mcp(self):
        for source_id, toolkit in self._toolkits.items():
            if getattr(toolkit, "use_mcp", False):
                try:
                    await toolkit._ensure_mcp_initialized()
                except Exception:
                    logger.warning("MCP unavailable for %s", source_id)
        self._tools_cache.clear()

    def create_agent_graphs(self, context: SourceContext) -> dict:
        self.ensure_toolkits(context)
        graphs = {}
        for source_id in self._order:
            desc = self._descriptors[source_id]
            if not desc.is_available(context) or source_id not in self._toolkits:
                continue
            try:
                agent = desc.create_agent(context, self.tools_for(source_id))
                graphs[desc.node_name] = agent.create_agent_subgraph()
                logger.info("Initialized agent: %s", desc.node_name)
            except Exception as exc:
                logger.warning("Failed to initialize %s agent: %s", source_id, exc)
        if not graphs:
            raise RuntimeError("No agents could be initialized. Check configuration and dependencies.")
        return graphs
