# Evaluations

Offline suites that measure Research Copilot's decisions, plus opt-in tracing for real runs.

## Routing (`evals/datasets/routing.jsonl`)

There are 153 labelled queries. Each line has the following fields:

| field | meaning |
|---|---|
| `required` | Sources the query cannot be answered well without. Missing one is a false negative. |
| `acceptable` | Extra sources that are reasonable to search. Selecting them is not penalised. |
| `notion` | Whether a Notion workspace is connected for this case. When it is, `notion` is in the available list. |
| `tags` | Slices for error analysis: `explicit`, `implicit`, `multi`, `time`, `keyword-trap`, `notion-idiom`, and others. |

Selecting anything outside `required` ∪ `acceptable` is a false positive.

### Labelling rules

- `local` is required only when the query points at the user's uploaded or indexed files. Everywhere else it is acceptable, because local search is cheap and the knowledge base may hold relevant material. As a result, local precision is 1.0 by construction.
- `notion` is required when the query asks for the user's own notes, workspace, or wiki, with or without the word "Notion". It is never acceptable otherwise, because reading private notes unasked is a precision error. The `notion-idiom` cases use "notion" as an ordinary word (for example "the notion of convergence") or name the product without asking for the workspace.
- `web` is required for time-sensitive questions ("latest", "current", a year). `arxiv` is also required when the question is about research progress.
- `keyword-trap` cases contain words like *code*, *paper*, or *lecture* that mean something else in context.

The labels were drafted by Claude and need a human pass before they back any published number.

### Running

```bash
# Baseline: production keyword fallback, no API calls
research-copilot-admin eval routing --router keyword

# LLM router: runs the real classify_intent node
research-copilot-admin eval routing --router llm --rpm 8 --max-api-calls 200
```

- Responses are cached in `evals/.cache/llm_cache.sqlite`, keyed by prompt and model settings, so a rerun with an unchanged prompt is free and deterministic. Pass `--no-cache` to measure fresh latency, or to sample run-to-run variance.
- `--max-api-calls` stops the run before the daily quota is spent. The run exits with code 2 and the report is marked incomplete. Rerun after the quota resets and the cached cases replay instantly.
- Each report is written to `evals/results/routing-<router>[-label]-<timestamp>.json`. It records metrics, per-case predictions, the git commit, the dataset hash, and LLM calls, tokens, and p50/p95 latency.

## Tracing real runs

Set `RUN_TRACE_DIR=~/research-traces` before starting the server. Each research run then appends one line to `runs.jsonl` containing:

- LLM calls, tokens, and latency per node (`web_agent/agent`, `aggregate`, and so on)
- tool calls and errors
- agents that exhausted their tool budget
- the routing decision, including any keyword fallback

Set `LLM_REQUESTS_PER_MINUTE` to throttle every model the app creates, including the reranker, under a single limit.
