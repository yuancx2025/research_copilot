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

## Retrieval (BEIR SciFact, no API calls)

This suite runs the app's own retrieval stack: the `Chunker` (parent-child, child 500/100 by default), a Qdrant collection built like `VectorDbManager.create_collection` (mpnet dense vectors plus BM25 sparse vectors), and `Retriever.retrieve`, the same call the local agent's search tool makes when reranking is off.

```bash
# One-time download (2.8 MB) into its own folder
mkdir -p evals/.cache/beir/scifact-download
curl -sSL -o evals/.cache/beir/scifact-download/scifact.zip \
  https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/scifact.zip
(cd evals/.cache/beir/scifact-download && unzip -q scifact.zip)

research-copilot-admin eval retrieval --verbose                          # production chunking
research-copilot-admin eval retrieval --chunk-size 1000 --chunk-overlap 200  # chunking ablation
```

- **Index:** built once per chunk setting and reused while the dataset fingerprint, chunking, and models match. Indexes live in `evals/.cache/qdrant`.
- **Metrics:** computed per unique BEIR document; each chunk carries its document id as `corpus_id`.
  - hit@k, recall@k, MRR, and nDCG@k count each relevant document once.
  - precision@k counts chunks, because two relevant chunks really do use two slots of the agent's context.
- **Configurations:** dense, BM25 (`sparse`), hybrid, plus two settings tested against the defaults:
  - `fetch_k` is how many candidates each search leg returns before truncating to k.
  - The production threshold (`score_threshold=0.7`) is tested on and off.
- **Score separation:** uses the routing queries that aren't about research papers as off-topic probes. It reports whether a top-1 score threshold can separate answerable questions from off-topic ones (AUROC), and sweeps dense thresholds to show the trade-off between keeping hits and returning nothing for off-topic questions.

## Tracing real runs

Set `RUN_TRACE_DIR=~/research-traces` before starting the server. Each research run then appends one line to `runs.jsonl` containing:

- LLM calls, tokens, and latency per node (`web_agent/agent`, `aggregate`, and so on)
- tool calls and errors
- agents that exhausted their tool budget
- the routing decision, including any keyword fallback

Set `LLM_REQUESTS_PER_MINUTE` to throttle every model the app creates, including the reranker, under a single limit.
