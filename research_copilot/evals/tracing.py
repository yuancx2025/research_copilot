"""Per-run tracing: LLM latency and tokens, node timings, and tool outcomes.

``RunTracer`` is a LangChain callback handler. Pass it in a runnable config
(``{"callbacks": [tracer]}``) and every chat model, tool, and LangGraph node
that runs underneath reports to it. Nested agent nodes are labelled
``<agent>/<node>``, for example ``web_agent/agent``.

Cached responses (served by a LangChain LLM cache) are counted separately:
their latency is not an API latency and they cost no quota.
"""
from __future__ import annotations

import contextvars
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.rate_limiters import BaseRateLimiter

from research_copilot.evals.metrics import percentile

# LangChain acquires the rate limiter inside the model run, so a model's measured latency
# would include our own throttling. RunTracer puts a fresh one-slot holder in this context
# when a model call starts; MeasuredRateLimiter adds its wait to whichever holder is current.
# A mutable holder (not a float) is needed because async model calls run in child tasks,
# whose context changes never reach the parent, while a shared object does.
_throttle_wait: contextvars.ContextVar[Optional[list]] = contextvars.ContextVar(
    "research_copilot_throttle_wait", default=None)


def _record_wait(seconds: float) -> None:
    holder = _throttle_wait.get()
    if holder is not None:
        holder[0] += seconds


class MeasuredRateLimiter(BaseRateLimiter):
    """Wraps a rate limiter and records how long callers waited on it."""

    def __init__(self, inner: BaseRateLimiter):
        self.inner = inner

    def acquire(self, *, blocking: bool = True) -> bool:
        started = time.perf_counter()
        try:
            return self.inner.acquire(blocking=blocking)
        finally:
            _record_wait(time.perf_counter() - started)

    async def aacquire(self, *, blocking: bool = True) -> bool:
        started = time.perf_counter()
        try:
            return await self.inner.aacquire(blocking=blocking)
        finally:
            _record_wait(time.perf_counter() - started)


@dataclass
class LLMCall:
    node: str
    latency_s: float  # provider latency: wall time minus time waiting on our own rate limiter
    input_tokens: int = 0
    output_tokens: int = 0
    cached: bool = False
    error: Optional[str] = None
    throttle_wait_s: float = 0.0


@dataclass
class ToolCall:
    node: str
    name: str
    latency_s: float
    error: bool = False


@dataclass
class NodeSpan:
    node: str
    latency_s: float
    error: bool = False


def node_label(metadata: Optional[dict], default: str = "") -> str:
    """Name the graph node a callback came from, including the parent agent for subgraphs."""
    md = metadata or {}
    node = md.get("langgraph_node") or ""
    ns = md.get("langgraph_checkpoint_ns") or ""
    top = ns.split("|")[0].split(":")[0] if ns else ""
    if top and node and top != node:
        return f"{top}/{node}"
    return node or top or md.get("eval_node") or default


def _usage(response) -> dict:
    try:
        message = response.generations[0][0].message
        return dict(getattr(message, "usage_metadata", None) or {})
    except (IndexError, AttributeError, TypeError):
        return {}


class RunTracer(BaseCallbackHandler):
    """Collects LLM, tool, and node measurements for one or more runs."""

    run_inline = True  # record in the caller's thread; we guard shared state with a lock

    def __init__(self, default_node: str = ""):
        self.default_node = default_node
        self.llm_calls: list[LLMCall] = []
        self.tool_calls: list[ToolCall] = []
        self.node_spans: list[NodeSpan] = []
        self._pending: dict[UUID, tuple[str, str, float, str, Optional[list]]] = {}
        self._lock = threading.Lock()
        self._started = time.perf_counter()

    # --- bookkeeping -------------------------------------------------------
    def _begin(self, run_id: UUID, kind: str, node: str, name: str = "") -> None:
        holder = None
        if kind == "llm":
            holder = [0.0]
            _throttle_wait.set(holder)
        with self._lock:
            self._pending[run_id] = (kind, node, time.perf_counter(), name, holder)

    def _end(self, run_id: UUID, kind: str):
        """Return (node, latency excluding throttle wait, name, throttle wait)."""
        with self._lock:
            entry = self._pending.pop(run_id, None)
        if not entry or entry[0] != kind:
            return None
        _, node, started, name, holder = entry
        waited = holder[0] if holder else 0.0
        return node, max(0.0, time.perf_counter() - started - waited), name, waited

    # --- chat models -------------------------------------------------------
    def on_chat_model_start(self, serialized, messages, *, run_id, metadata=None, **kwargs: Any):
        self._begin(run_id, "llm", node_label(metadata, self.default_node))

    def on_llm_start(self, serialized, prompts, *, run_id, metadata=None, **kwargs: Any):
        self._begin(run_id, "llm", node_label(metadata, self.default_node))

    def on_llm_end(self, response, *, run_id, **kwargs: Any):
        ended = self._end(run_id, "llm")
        if not ended:
            return
        node, latency, _, waited = ended
        usage = _usage(response)
        # LangChain marks cache hits by adding total_cost=0 to the cached message's usage.
        cached = usage.get("total_cost") == 0
        with self._lock:
            self.llm_calls.append(LLMCall(
                node=node, latency_s=latency,
                input_tokens=int(usage.get("input_tokens") or 0),
                output_tokens=int(usage.get("output_tokens") or 0),
                cached=cached, throttle_wait_s=waited,
            ))

    def on_llm_error(self, error, *, run_id, **kwargs: Any):
        ended = self._end(run_id, "llm")
        if ended:
            node, latency, _, waited = ended
            with self._lock:
                self.llm_calls.append(LLMCall(node=node, latency_s=latency, error=type(error).__name__,
                                              throttle_wait_s=waited))

    # --- tools -------------------------------------------------------------
    def on_tool_start(self, serialized, input_str, *, run_id, metadata=None, **kwargs: Any):
        name = (serialized or {}).get("name") or kwargs.get("name") or "tool"
        self._begin(run_id, "tool", node_label(metadata, self.default_node), name)

    def _tool_done(self, run_id: UUID, error: bool):
        ended = self._end(run_id, "tool")
        if ended:
            node, latency, name, _ = ended
            with self._lock:
                self.tool_calls.append(ToolCall(node=node, name=name, latency_s=latency, error=error))

    def on_tool_end(self, output, *, run_id, **kwargs: Any):
        self._tool_done(run_id, getattr(output, "status", None) == "error")

    def on_tool_error(self, error, *, run_id, **kwargs: Any):
        self._tool_done(run_id, True)

    # --- graph nodes -------------------------------------------------------
    def on_chain_start(self, serialized, inputs, *, run_id, metadata=None, **kwargs: Any):
        md = metadata or {}
        if kwargs.get("name") and kwargs.get("name") == md.get("langgraph_node"):
            self._begin(run_id, "node", node_label(md, self.default_node))

    def _node_done(self, run_id: UUID, error: bool):
        ended = self._end(run_id, "node")
        if ended:
            node, latency, _, _ = ended
            with self._lock:
                self.node_spans.append(NodeSpan(node=node, latency_s=latency, error=error))

    def on_chain_end(self, outputs, *, run_id, **kwargs: Any):
        self._node_done(run_id, False)

    def on_chain_error(self, error, *, run_id, **kwargs: Any):
        # LangGraph signals interrupts by raising; those are control flow, not failures.
        self._node_done(run_id, type(error).__name__ not in {"GraphInterrupt", "NodeInterrupt"})

    # --- results -----------------------------------------------------------
    @property
    def api_calls(self) -> int:
        """LLM requests that reached the provider (cache hits excluded, failed requests included)."""
        with self._lock:
            return sum(1 for call in self.llm_calls if not call.cached)

    def summary(self) -> dict:
        with self._lock:
            llm = list(self.llm_calls)
            tools = list(self.tool_calls)
            spans = list(self.node_spans)
        live = [c for c in llm if not c.cached and not c.error]
        latencies = [c.latency_s for c in live]

        by_node: dict[str, dict] = defaultdict(lambda: {
            "llm_calls": 0, "input_tokens": 0, "output_tokens": 0, "runs": 0, "latency_s": 0.0})
        for call in llm:
            entry = by_node[call.node or "unknown"]
            entry["llm_calls"] += 1
            entry["input_tokens"] += call.input_tokens
            entry["output_tokens"] += call.output_tokens
        for span in spans:
            entry = by_node[span.node or "unknown"]
            entry["runs"] += 1
            entry["latency_s"] = round(entry["latency_s"] + span.latency_s, 4)
        # Node spans are wall time; take out the throttling their model calls waited through.
        for call in llm:
            entry = by_node[call.node or "unknown"]
            if entry["runs"] and call.throttle_wait_s:
                entry["latency_s"] = round(max(0.0, entry["latency_s"] - call.throttle_wait_s), 4)

        by_tool: dict[str, dict] = defaultdict(lambda: {"calls": 0, "errors": 0})
        for call in tools:
            by_tool[call.name]["calls"] += 1
            by_tool[call.name]["errors"] += int(call.error)

        return {
            "wall_s": round(time.perf_counter() - self._started, 4),
            "llm": {
                "calls": len(llm),
                "api_calls": sum(1 for c in llm if not c.cached),
                "cached_calls": sum(1 for c in llm if c.cached),
                "errors": sum(1 for c in llm if c.error),
                "input_tokens": sum(c.input_tokens for c in llm),
                "output_tokens": sum(c.output_tokens for c in llm),
                "latency_s": {
                    "p50": percentile(latencies, 50),
                    "p95": percentile(latencies, 95),
                    "max": max(latencies) if latencies else None,
                },
                # Time spent waiting on our own client-side rate limiter, excluded from latency.
                "throttle_wait_s": round(sum(c.throttle_wait_s for c in llm), 4),
            },
            "tools": {
                "calls": len(tools),
                "errors": sum(1 for c in tools if c.error),
                "by_name": dict(by_tool),
            },
            # A finalize node only runs when an agent exhausted its tool budget.
            "tool_budget_exhausted": sorted({
                s.node.split("/")[0] for s in spans if s.node.endswith("/finalize")}),
            "by_node": dict(by_node),
        }
