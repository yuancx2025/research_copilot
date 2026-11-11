"""L9: llm.with_config(temperature=...) never reached the model; nodes now use its configured temperature."""
import json

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableLambda

from research_copilot.orchestrator.nodes import (
    analyze_and_rewrite_query, analyze_chat_and_summarize, classify_research_intent,
)
from tests.evals.fakes import FakeChat


class ReportingChat(FakeChat):
    """Reports its temperature in invocation params, as real chat models do."""
    temperature: float = 0.0

    @property
    def _identifying_params(self):
        return {"temperature": self.temperature}


class TempChat(ReportingChat):
    def with_config(self, *args, **kwargs):  # the old no-op path must not be used any more
        raise AssertionError("nodes should not call with_config for temperature")


class Seen(BaseCallbackHandler):
    def __init__(self):
        self.temperatures = []

    def on_chat_model_start(self, serialized, messages, *, invocation_params=None, **kwargs):
        self.temperatures.append((invocation_params or {}).get("temperature"))


def test_with_config_temperature_was_a_no_op():
    """Documents the bug: the model never saw the requested temperature."""
    seen = Seen()
    ReportingChat(temperature=0.0).with_config(temperature=0.9).invoke(
        [HumanMessage(content="x")], config={"callbacks": [seen]})
    assert seen.temperatures == [0.0]  # 0.9 was requested, 0.0 was used


def test_nodes_run_at_the_models_configured_temperature():
    seen = Seen()
    run = lambda fn, state, llm: RunnableLambda(lambda s: fn(s, llm)).invoke(state, config={"callbacks": [seen]})

    intent = TempChat(temperature=0.3, reply=json.dumps({"agents": ["web"], "reasoning": "r", "confidence": 0.9}))
    out = run(classify_research_intent, {"originalQuery": "q", "available_sources": ["web", "local"], "messages": []}, intent)
    assert out["research_intent"] == ["web"] and out["routing_decision"]["fallback"] is None

    rewrite = TempChat(temperature=0.3, reply=json.dumps(
        {"is_clear": True, "questions": ["q"], "clarification_needed": ""}))
    run(analyze_and_rewrite_query, {"messages": [HumanMessage(content="q")], "conversation_summary": ""}, rewrite)

    summary = TempChat(temperature=0.3, reply="summary")
    run(analyze_chat_and_summarize, {"messages": [HumanMessage(content="a"), HumanMessage(content="b")],
                                     "conversation_summary": "", "originalQuery": "a"}, summary)

    assert seen.temperatures and all(t == 0.3 for t in seen.temperatures)
