from typing import TypedDict

import pytest
from langchain_core.caches import InMemoryCache
from langchain_core.globals import get_llm_cache, set_llm_cache
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph

from research_copilot.evals.tracing import RunTracer, node_label
from tests.evals.fakes import FakeChat


@pytest.fixture
def llm_cache():
    previous = get_llm_cache()
    set_llm_cache(InMemoryCache())
    yield
    set_llm_cache(previous)


def test_node_label_includes_parent_agent_for_subgraphs():
    assert node_label({"langgraph_node": "classify_intent",
                       "langgraph_checkpoint_ns": "classify_intent:abc"}) == "classify_intent"
    assert node_label({"langgraph_node": "agent",
                       "langgraph_checkpoint_ns": "web_agent:abc|agent:def"}) == "web_agent/agent"
    assert node_label({}, default="eval") == "eval"


class _State(TypedDict, total=False):
    text: str


def test_tracer_attributes_llm_tool_and_node_measurements():
    llm = FakeChat(reply="hi", input_tokens=7, output_tokens=2)

    @tool
    def lookup(q: str) -> str:
        """Look something up."""
        return "found " + q

    @tool
    def broken(q: str) -> str:
        """Always fails."""
        raise ValueError("boom")

    def agent(state):
        llm.invoke([HumanMessage(content=state.get("text", ""))])
        lookup.invoke({"q": "x"})
        try:
            broken.invoke({"q": "x"})
        except ValueError:
            pass
        return {"text": "done"}

    def finalize(state):
        return {}

    sub = StateGraph(_State)
    sub.add_node("agent", agent)
    sub.add_node("finalize", finalize)
    sub.add_edge(START, "agent")
    sub.add_edge("agent", "finalize")
    sub.add_edge("finalize", END)

    main = StateGraph(_State)
    main.add_node("web_agent", sub.compile())
    main.add_edge(START, "web_agent")
    main.add_edge("web_agent", END)

    tracer = RunTracer()
    main.compile().invoke({"text": "question"}, config={"callbacks": [tracer]})
    summary = tracer.summary()

    assert summary["llm"]["calls"] == 1 and summary["llm"]["api_calls"] == 1
    assert summary["llm"]["input_tokens"] == 7 and summary["llm"]["output_tokens"] == 2
    assert summary["by_node"]["web_agent/agent"]["llm_calls"] == 1
    assert summary["by_node"]["web_agent/agent"]["runs"] == 1
    assert summary["tools"]["by_name"] == {"lookup": {"calls": 1, "errors": 0},
                                           "broken": {"calls": 1, "errors": 1}}
    assert summary["tool_budget_exhausted"] == ["web_agent"]


def test_cache_hits_are_counted_but_not_as_api_calls(llm_cache):
    llm = FakeChat()
    tracer = RunTracer(default_node="classify_intent")
    node = RunnableLambda(lambda _: llm.invoke([HumanMessage(content="same prompt")]))
    node.invoke({}, config={"callbacks": [tracer]})
    node.invoke({}, config={"callbacks": [tracer]})

    assert llm.calls == 1
    summary = tracer.summary()
    assert summary["llm"]["calls"] == 2
    assert summary["llm"]["api_calls"] == 1 and summary["llm"]["cached_calls"] == 1
    assert tracer.api_calls == 1
    assert summary["by_node"]["classify_intent"]["llm_calls"] == 2


def test_latency_excludes_time_waiting_on_our_rate_limiter():
    import time
    from langchain_core.rate_limiters import BaseRateLimiter
    from research_copilot.evals.tracing import MeasuredRateLimiter

    class SlowLimiter(BaseRateLimiter):
        def acquire(self, *, blocking=True):
            time.sleep(0.3)
            return True

        async def aacquire(self, *, blocking=True):
            return self.acquire(blocking=blocking)

    llm = FakeChat(rate_limiter=MeasuredRateLimiter(SlowLimiter()))
    tracer = RunTracer(default_node="n")
    llm.invoke([HumanMessage(content="x")], config={"callbacks": [tracer]})
    summary = tracer.summary()
    assert summary["llm"]["throttle_wait_s"] >= 0.3
    assert summary["llm"]["latency_s"]["p50"] < 0.1


@pytest.mark.asyncio
async def test_async_latency_excludes_throttle_wait():
    import asyncio
    from langchain_core.rate_limiters import BaseRateLimiter
    from research_copilot.evals.tracing import MeasuredRateLimiter

    class SlowLimiter(BaseRateLimiter):
        def acquire(self, *, blocking=True):
            return True

        async def aacquire(self, *, blocking=True):
            await asyncio.sleep(0.3)
            return True

    llm = FakeChat(rate_limiter=MeasuredRateLimiter(SlowLimiter()))
    tracer = RunTracer(default_node="n")
    await llm.ainvoke([HumanMessage(content="x")], config={"callbacks": [tracer]})
    summary = tracer.summary()
    assert summary["llm"]["throttle_wait_s"] >= 0.3
    assert summary["llm"]["latency_s"]["p50"] < 0.1


def test_llm_errors_are_recorded():
    tracer = RunTracer(default_node="n")
    with pytest.raises(RuntimeError):
        FakeChat(fail=True).invoke([HumanMessage(content="x")], config={"callbacks": [tracer]})
    summary = tracer.summary()
    assert summary["llm"]["errors"] == 1 and summary["llm"]["api_calls"] == 1
    assert summary["llm"]["latency_s"]["p50"] is None
