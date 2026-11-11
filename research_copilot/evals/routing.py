"""Intent-routing evaluation: LLM router vs. the keyword baseline.

Each case names the sources a query *requires* and the extra sources that
are *acceptable*. Selecting a required source is a true positive, missing
one is a false negative, and selecting anything outside both sets is a
false positive. See evals/README.md for the labelling rules.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from langchain_core.runnables import RunnableLambda

from research_copilot.evals.metrics import LabelledPrediction, score_multilabel
from research_copilot.evals.tracing import RunTracer
from research_copilot.orchestrator.intent import ensure_notion, explicit_notion_request, keyword_agents

BASE_SOURCES = ("arxiv", "youtube", "github", "web", "local")
ALL_SOURCES = (*BASE_SOURCES, "notion")


@dataclass(frozen=True)
class RoutingCase:
    id: str
    query: str
    required: frozenset
    acceptable: frozenset
    notion: bool = False
    tags: tuple = ()

    @property
    def available(self) -> list[str]:
        return [*BASE_SOURCES, "notion"] if self.notion else list(BASE_SOURCES)


def load_cases(path: Path) -> list[RoutingCase]:
    cases, seen = [], set()
    for lineno, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        raw = json.loads(line)
        case = RoutingCase(
            id=raw["id"], query=raw["query"],
            required=frozenset(raw["required"]), acceptable=frozenset(raw.get("acceptable", [])),
            notion=bool(raw.get("notion", False)), tags=tuple(raw.get("tags", [])),
        )
        problems = []
        if case.id in seen:
            problems.append("duplicate id")
        if not case.required:
            problems.append("no required sources")
        if case.required & case.acceptable:
            problems.append("a source is both required and acceptable")
        unknown = (case.required | case.acceptable) - set(case.available)
        if unknown:
            problems.append(f"labels not available for this case: {sorted(unknown)}")
        if problems:
            raise ValueError(f"{path}:{lineno} ({case.id}): " + "; ".join(problems))
        seen.add(case.id)
        cases.append(case)
    return cases


@dataclass
class Decision:
    agents: list[str]
    fallback: Optional[str] = None
    confidence: Optional[float] = None
    error: Optional[str] = None


Router = Callable[[RoutingCase], Decision]


def keyword_router(case: RoutingCase) -> Decision:
    """The production keyword fallback, used as the baseline."""
    agents = ensure_notion(case.query, keyword_agents(case.query, case.available), case.available)
    return Decision(agents=agents)


def make_llm_router(llm, tracer: RunTracer) -> Router:
    """Run the real classify_intent node, with callbacks reporting to ``tracer``."""
    from research_copilot.orchestrator.nodes import classify_research_intent

    node = RunnableLambda(lambda state: classify_research_intent(state, llm), name="classify_intent")

    def route(case: RoutingCase) -> Decision:
        state = {"originalQuery": case.query, "available_sources": case.available, "messages": []}
        result = node.invoke(state, config={
            "callbacks": [tracer], "metadata": {"eval_node": "classify_intent", "case_id": case.id}})
        decision = result.get("routing_decision", {})
        return Decision(agents=list(result.get("research_intent", [])),
                        fallback=decision.get("fallback"), confidence=decision.get("confidence"))

    return route


def _git_revision() -> dict:
    def git(*args):
        try:
            return subprocess.run(["git", *args], capture_output=True, text=True, timeout=5,
                                  check=True).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return None
    return {"commit": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain"))}


def evaluate(cases: list[RoutingCase], router: Router, *, router_name: str,
             tracer: Optional[RunTracer] = None, max_api_calls: Optional[int] = None,
             dataset_path: Optional[Path] = None, model: Optional[str] = None,
             progress: Optional[Callable[[int, int, RoutingCase], None]] = None,
             max_consecutive_llm_errors: Optional[int] = 3) -> dict:
    """Route every case and score the decisions.

    A case whose LLM call failed (``fallback == "llm_error"``, usually a quota
    or network error) is listed under ``unscored`` instead of being scored as
    the keyword fallback it degraded to: an outage is not a routing decision.
    Failures are not cached, so a rerun retries exactly those cases while
    finished ones replay from the cache. Stops early once the API-call budget
    is spent or after several LLM errors in a row.
    """
    rows, predictions, unscored = [], [], []
    stopped_early = False
    stop_reason = None
    consecutive_errors = 0
    for index, case in enumerate(cases):
        if tracer is not None and max_api_calls is not None and tracer.api_calls >= max_api_calls:
            stopped_early, stop_reason = True, "api_budget"
            break
        if max_consecutive_llm_errors and consecutive_errors >= max_consecutive_llm_errors:
            stopped_early, stop_reason = True, "llm_errors"
            break
        if progress:
            progress(index, len(cases), case)
        try:
            decision = router(case)
        except Exception as exc:  # record and continue; one bad case should not sink the run
            decision = Decision(agents=[], error=f"{type(exc).__name__}: {exc}")
        if decision.fallback == "llm_error":
            consecutive_errors += 1
            unscored.append(case.id)
            continue
        consecutive_errors = 0
        item = LabelledPrediction(frozenset(decision.agents), case.required, case.acceptable)
        predictions.append((case, item, decision))
        rows.append({
            "id": case.id, "query": case.query, "tags": list(case.tags), "notion_connected": case.notion,
            "required": sorted(case.required), "acceptable": sorted(case.acceptable),
            "predicted": sorted(decision.agents),
            "false_positives": sorted(item.false_positives), "false_negatives": sorted(item.false_negatives),
            "correct": item.correct, "fallback": decision.fallback, "confidence": decision.confidence,
            "error": decision.error,
        })

    scored = [item for _, item, _ in predictions]
    labels = [s for s in ALL_SOURCES if any(s in c.available for c in cases)]
    metrics = score_multilabel(scored, labels)

    by_tag: dict[str, list[bool]] = defaultdict(list)
    for case, item, _ in predictions:
        for tag in case.tags:
            by_tag[tag].append(item.correct)
    metrics["case_accuracy_by_tag"] = {
        tag: {"accuracy": round(sum(v) / len(v), 4), "cases": len(v)} for tag, v in sorted(by_tag.items())}

    fallbacks = Counter(d.fallback for _, _, d in predictions if d.fallback)
    metrics["fallback_rate"] = round(sum(fallbacks.values()) / len(predictions), 4) if predictions else None
    metrics["fallbacks"] = dict(fallbacks)
    metrics["errors"] = sum(1 for _, _, d in predictions if d.error)
    metrics["unscored_llm_errors"] = unscored

    # Notion invariants: never chosen while disconnected, never forced by an idiomatic "notion".
    metrics["notion_selected_while_disconnected"] = sum(
        1 for c, _, d in predictions if not c.notion and "notion" in d.agents)
    idioms = [(c, d) for c, _, d in predictions if "notion-idiom" in c.tags]
    metrics["notion_idiom_false_positive_rate"] = (
        round(sum(1 for _, d in idioms if "notion" in d.agents) / len(idioms), 4) if idioms else None)
    metrics["notion_idiom_forced_by_rule"] = sorted(
        c.id for c, _ in idioms if explicit_notion_request(c.query))

    stop_reason = stop_reason or ("llm_errors" if unscored else None)
    dataset = {"cases": len(cases), "evaluated": len(predictions)}
    if dataset_path:
        dataset.update(path=str(dataset_path),
                       sha256=hashlib.sha256(Path(dataset_path).read_bytes()).hexdigest()[:16])

    return {
        "suite": "routing",
        "router": router_name,
        "model": model,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git": _git_revision(),
        "dataset": dataset,
        "complete": not stopped_early and len(predictions) == len(cases),
        "stop_reason": stop_reason,
        "metrics": metrics,
        "trace": tracer.summary() if tracer is not None else None,
        "cases": rows,
    }


def format_report(report: dict) -> str:
    m = report["metrics"]

    def fmt(value):
        return "  -  " if value is None else f"{value:.3f}"

    lines = [
        f"Routing eval · router={report['router']} · model={report.get('model') or '-'}",
        f"cases {report['dataset']['evaluated']}/{report['dataset']['cases']}"
        + ("" if report["complete"] else {
            "api_budget": "  (INCOMPLETE: API budget reached; rerun to resume from cache)",
            "llm_errors": "  (INCOMPLETE: repeated LLM errors, likely quota; rerun after it resets)",
        }.get(report.get("stop_reason"), "  (INCOMPLETE)")),
        "",
        f"micro P/R/F1   {fmt(m['micro']['precision'])} / {fmt(m['micro']['recall'])} / {fmt(m['micro']['f1'])}",
        f"macro F1       {fmt(m['macro_f1'])}",
        f"case accuracy  {fmt(m['case_accuracy'])}    avg sources/query {m['avg_sources_selected']}",
        f"fallback rate  {fmt(m['fallback_rate'])}    {m['fallbacks'] or ''}"
        + (f"    unscored (LLM error): {len(m['unscored_llm_errors'])}" if m["unscored_llm_errors"] else ""),
        f"notion idiom FP rate {fmt(m['notion_idiom_false_positive_rate'])}"
        f"    selected while disconnected: {m['notion_selected_while_disconnected']}",
        "",
        f"{'source':<8} {'P':>6} {'R':>6} {'F1':>6} {'support':>8} {'FP':>4} {'FN':>4}",
    ]
    for label, s in m["per_label"].items():
        lines.append(f"{label:<8} {fmt(s['precision']):>6} {fmt(s['recall']):>6} {fmt(s['f1']):>6} "
                     f"{s['support']:>8} {s['fp']:>4} {s['fn']:>4}")
    lines.append("")
    lines.append("accuracy by tag: " + ", ".join(
        f"{tag} {v['accuracy']:.2f} (n={v['cases']})" for tag, v in m["case_accuracy_by_tag"].items()))
    trace = report.get("trace")
    if trace:
        llm = trace["llm"]
        lat = llm["latency_s"]
        lines.append(
            f"LLM calls {llm['calls']} (api {llm['api_calls']}, cached {llm['cached_calls']}, errors {llm['errors']})"
            f" · tokens in/out {llm['input_tokens']}/{llm['output_tokens']}"
            f" · latency p50/p95 {fmt(lat['p50'])}/{fmt(lat['p95'])} s")
    return "\n".join(lines)


def run_cli(args) -> int:
    """Entry point for ``research-copilot-admin eval routing``."""
    dataset_path = Path(args.dataset)
    cases = load_cases(dataset_path)
    if args.limit:
        cases = cases[: args.limit]

    tracer = RunTracer(default_node="classify_intent")
    model = None
    previous_cache = None
    restore_cache = False
    if args.router == "keyword":
        router = keyword_router
    else:
        from langchain_core.globals import get_llm_cache, set_llm_cache
        from langchain_core.rate_limiters import InMemoryRateLimiter
        from research_copilot.core.rag_system import create_llm

        if not args.no_cache:
            from langchain_community.cache import SQLiteCache
            cache_path = Path(args.cache)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            previous_cache, restore_cache = get_llm_cache(), True
            set_llm_cache(SQLiteCache(database_path=str(cache_path)))
        from research_copilot.evals.tracing import MeasuredRateLimiter
        limiter = MeasuredRateLimiter(InMemoryRateLimiter(
            requests_per_second=args.rpm / 60, check_every_n_seconds=0.1,
            max_bucket_size=1)) if args.rpm > 0 else None
        if getattr(args, "model", None):
            from research_copilot.config import settings as config
            config.LLM_MODEL = args.model
        llm = create_llm(rate_limiter=limiter)
        model = getattr(llm, "model", None) or getattr(llm, "model_name", None)
        router = make_llm_router(llm, tracer)

    def progress(i, total, case):
        if args.verbose:
            print(f"[{i + 1}/{total}] {case.id}", flush=True)

    try:
        report = evaluate(cases, router, router_name=args.router,
                          tracer=tracer if args.router == "llm" else None,
                          max_api_calls=args.max_api_calls if args.router == "llm" else None,
                          dataset_path=dataset_path, model=model, progress=progress)
    finally:
        if restore_cache:
            from langchain_core.globals import set_llm_cache
            set_llm_cache(previous_cache)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    label = f"-{args.label}" if args.label else ""
    out_path = out_dir / f"routing-{args.router}{label}-{stamp}.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(format_report(report))
    print(f"\nWrote {out_path}")
    return 0 if report["complete"] else 2
