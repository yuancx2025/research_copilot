import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from research_copilot.evals.routing import (
    RoutingCase, evaluate, format_report, keyword_router, load_cases, make_llm_router, run_cli,
)
from research_copilot.evals.tracing import RunTracer
from tests.evals.fakes import FakeChat

DATASET = Path(__file__).resolve().parents[2] / "evals" / "datasets" / "routing.jsonl"


def _case(**overrides):
    base = dict(id="c1", query="papers on attention", required=frozenset({"arxiv"}),
                acceptable=frozenset({"web", "local"}), notion=False, tags=("paper",))
    base.update(overrides)
    return RoutingCase(**base)


def test_shipped_dataset_is_valid():
    cases = load_cases(DATASET)
    assert len(cases) >= 150
    assert len({c.id for c in cases}) == len(cases)


@pytest.mark.parametrize("line, message", [
    ({"id": "a", "query": "q", "required": []}, "no required sources"),
    ({"id": "a", "query": "q", "required": ["web"], "acceptable": ["web"]}, "both required and acceptable"),
    ({"id": "a", "query": "q", "required": ["notion"]}, "not available"),
])
def test_load_cases_rejects_bad_labels(tmp_path, line, message):
    path = tmp_path / "bad.jsonl"
    path.write_text(json.dumps(line) + "\n")
    with pytest.raises(ValueError, match=message):
        load_cases(path)


def test_keyword_baseline_report_shape():
    report = evaluate(load_cases(DATASET), keyword_router, router_name="keyword")
    m = report["metrics"]
    assert report["complete"] and report["trace"] is None
    assert 0 < m["micro"]["f1"] < 1
    assert m["notion_selected_while_disconnected"] == 0
    # The capitalised-"Notion" rule forces Notion for these idioms regardless of router.
    assert m["notion_idiom_forced_by_rule"] == ["idiom-02", "idiom-07"]
    assert "source" in format_report(report)


def test_llm_router_runs_real_node_and_traces_calls():
    llm = FakeChat(reply=json.dumps({"agents": ["arxiv", "youtube"], "reasoning": "r", "confidence": 0.8}))
    tracer = RunTracer(default_node="classify_intent")
    report = evaluate([_case(), _case(id="c2")], make_llm_router(llm, tracer),
                      router_name="llm", tracer=tracer)
    assert [row["predicted"] for row in report["cases"]] == [["arxiv", "youtube"]] * 2
    assert report["cases"][0]["false_positives"] == ["youtube"]
    assert report["cases"][0]["confidence"] == 0.8
    assert report["metrics"]["fallback_rate"] == 0.0
    assert report["trace"]["llm"]["api_calls"] == 2
    assert report["trace"]["by_node"]["classify_intent"]["input_tokens"] == 20


def test_llm_errors_are_left_unscored_not_scored_as_keyword_fallback():
    tracer = RunTracer()
    report = evaluate([_case()], make_llm_router(FakeChat(fail=True), tracer),
                      router_name="llm", tracer=tracer)
    assert report["metrics"]["unscored_llm_errors"] == ["c1"]
    assert report["metrics"]["fallbacks"] == {}
    assert report["cases"] == [] and not report["complete"]
    assert report["stop_reason"] == "llm_errors"


def test_repeated_llm_errors_stop_and_drop_unscored_cases():
    good = FakeChat(reply=json.dumps({"agents": ["arxiv"], "reasoning": "r", "confidence": 0.9}))
    bad = FakeChat(fail=True)
    calls = iter([good, bad, good, bad, bad, bad, good])
    tracer = RunTracer()

    def router(case):
        return make_llm_router(next(calls), tracer)(case)

    cases = [_case(id=f"c{i}", query=f"papers on topic {i}") for i in range(7)]
    report = evaluate(cases, router, router_name="llm", tracer=tracer, max_consecutive_llm_errors=3)
    assert not report["complete"] and report["stop_reason"] == "llm_errors"
    # c1 failed alone and is retried next run; c3-c5 failed in a row and stopped the run
    assert [row["id"] for row in report["cases"]] == ["c0", "c2"]
    assert report["metrics"]["unscored_llm_errors"] == ["c1", "c3", "c4", "c5"]
    assert report["metrics"]["fallbacks"] == {}


def test_api_budget_stops_early():
    llm = FakeChat(reply=json.dumps({"agents": ["arxiv"], "reasoning": "r", "confidence": 0.9}))
    tracer = RunTracer()
    cases = [_case(id=f"c{i}", query=f"papers on topic {i}") for i in range(5)]
    report = evaluate(cases, make_llm_router(llm, tracer), router_name="llm",
                      tracer=tracer, max_api_calls=2)
    assert not report["complete"]
    assert report["dataset"]["evaluated"] == 2


def test_cli_keyword_run_writes_report(tmp_path):
    args = SimpleNamespace(dataset=str(DATASET), limit=10, router="keyword", no_cache=True,
                           cache=str(tmp_path / "c.sqlite"), rpm=0, max_api_calls=5, verbose=False,
                           out=str(tmp_path), label="smoke")
    assert run_cli(args) == 0
    [written] = tmp_path.glob("routing-keyword-smoke-*.json")
    assert json.loads(written.read_text())["dataset"]["evaluated"] == 10
