"""Retrieval benchmark on a BEIR-format dataset, through the app's own retrieval code.

Documents go through the production ``Chunker`` (parent-child), into a Qdrant
collection built exactly like ``VectorDbManager.create_collection`` (dense
cosine vector plus a BM25 sparse vector), and queries run through
``Retriever.retrieve``, the same call the local agent's search tool makes when
reranking is off. No LLM is involved, so this suite costs no API quota.

Metrics come from ``RAGEvaluator`` keyed on the BEIR document id, which every
child chunk carries as ``corpus_id``.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Callable, Optional, Union

from langchain_qdrant import QdrantVectorStore, RetrievalMode

from research_copilot.evals.metrics import percentile
from research_copilot.rag.evaluator import RAGEvaluator

INDEX_FORMAT = 1


# --- data ------------------------------------------------------------------
@dataclass
class BeirData:
    name: str
    corpus: dict  # doc id -> text (title + body)
    queries: dict  # query id -> text, only those with qrels in the split
    qrels: dict  # query id -> {doc id: grade}
    fingerprint: str  # corpus only: the index depends on documents, not on which split is scored
    qrels_fingerprint: str = ""


def load_beir(data_dir: Path, split: str = "test") -> BeirData:
    data_dir = Path(data_dir)
    digest = hashlib.sha256()
    corpus = {}
    with open(data_dir / "corpus.jsonl", "rb") as handle:
        for raw in handle:
            digest.update(raw)
            row = json.loads(raw)
            title, text = (row.get("title") or "").strip(), (row.get("text") or "").strip()
            corpus[str(row["_id"])] = f"{title}\n\n{text}" if title else text

    qrels: dict = {}
    qrels_path = data_dir / "qrels" / f"{split}.tsv"
    qrels_digest = hashlib.sha256(qrels_path.read_bytes()).hexdigest()[:16]
    for lineno, line in enumerate(qrels_path.read_text(encoding="utf-8").splitlines()):
        parts = line.split("\t")
        if lineno == 0 and not parts[-1].strip().lstrip("-").isdigit():
            continue  # header
        qid, did, grade = parts[0], parts[1], float(parts[2])
        if grade > 0:
            qrels.setdefault(str(qid), {})[str(did)] = grade

    queries = {}
    for raw in (data_dir / "queries.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(raw)
        if str(row["_id"]) in qrels:
            queries[str(row["_id"])] = row["text"]
    return BeirData(data_dir.name, corpus, queries, qrels, digest.hexdigest()[:16], qrels_digest)


# --- index -----------------------------------------------------------------
def default_embeddings():
    """The production embedding models from settings."""
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_qdrant import FastEmbedSparse
    from research_copilot.config import settings as config
    return (HuggingFaceEmbeddings(model_name=config.DENSE_MODEL),
            FastEmbedSparse(model_name=config.SPARSE_MODEL))


def make_chunker(chunk_size: int, chunk_overlap: int):
    """The production Chunker with child-size settings overridden for this build only."""
    from research_copilot.config import settings as config
    from research_copilot.rag.chunker import Chunker
    saved = config.CHILD_CHUNK_SIZE, config.CHILD_CHUNK_OVERLAP
    config.CHILD_CHUNK_SIZE, config.CHILD_CHUNK_OVERLAP = chunk_size, chunk_overlap
    try:
        return Chunker()
    finally:
        config.CHILD_CHUNK_SIZE, config.CHILD_CHUNK_OVERLAP = saved


def chunk_corpus(data: BeirData, chunk_size: int, chunk_overlap: int) -> list:
    chunker = make_chunker(chunk_size, chunk_overlap)
    children = []
    for doc_id, text in data.corpus.items():
        _, doc_children = chunker.create_chunks_from_text(
            text, {"source_id": doc_id, "corpus_id": doc_id, "source_type": "local"})
        children.extend(doc_children)
    return children


def create_collection(client, name: str, dense, sparse_vector_name: str) -> None:
    """The production collection setup (VectorDbManager uses the same function)."""
    from research_copilot.storage.qdrant_client import create_or_upgrade_collection
    create_or_upgrade_collection(client, name, dense_size=len(dense.embed_query("test")),
                                 sparse_vector_name=sparse_vector_name)


def legacy_copy_without_idf(client, name: str, sparse_vector_name: str = "sparse") -> str:
    """A copy of ``name`` whose sparse vector lacks the IDF modifier, as collections were before the fix.

    Stored vectors are identical (FastEmbed BM25 stores term frequencies; IDF is applied at query
    time), so copying points reproduces the old scoring exactly without re-embedding.
    """
    from qdrant_client import models as qm
    target = f"{name}-noidf"
    count = client.count(name).count
    if client.collection_exists(target) and client.count(target).count == count:
        return target
    if client.collection_exists(target):
        client.delete_collection(target)
    client.create_collection(target, vectors_config=client.get_collection(name).config.params.vectors,
                             sparse_vectors_config={sparse_vector_name: qm.SparseVectorParams()})
    offset = None
    while True:
        points, offset = client.scroll(name, limit=1000, offset=offset, with_payload=True, with_vectors=True)
        if points:
            client.upsert(target, [qm.PointStruct(id=pt.id, vector=pt.vector, payload=pt.payload) for pt in points])
        if offset is None:
            break
    return target


def make_store(client, name: str, dense, sparse, mode: RetrievalMode,
               sparse_vector_name: str = "sparse") -> QdrantVectorStore:
    return QdrantVectorStore(client=client, collection_name=name, embedding=dense, sparse_embedding=sparse,
                             retrieval_mode=mode, sparse_vector_name=sparse_vector_name)


def collection_name(data: BeirData, chunk_size: int, chunk_overlap: int) -> str:
    return f"{data.name}-c{chunk_size}-o{chunk_overlap}"


def build_index(client, data: BeirData, dense, sparse, *, chunk_size: int, chunk_overlap: int,
                sparse_vector_name: str = "sparse", batch_size: int = 256,
                manifest_dir: Optional[Path] = None,
                progress: Optional[Callable[[int, int], None]] = None) -> dict:
    """Index the corpus once per chunking setting; reuse it when the saved manifest matches.

    The manifest (dataset fingerprint, chunking, embedding models, chunk count)
    is written next to the index only after every chunk is stored, so an
    interrupted build is rebuilt rather than half-reused.
    """
    name = collection_name(data, chunk_size, chunk_overlap)
    manifest = {"format": INDEX_FORMAT, "dataset": data.name, "fingerprint": data.fingerprint,
                "chunk_size": chunk_size, "chunk_overlap": chunk_overlap,
                "dense_model": getattr(dense, "model_name", type(dense).__name__),
                "sparse_model": getattr(sparse, "model_name", type(sparse).__name__)}
    manifest_path = Path(manifest_dir) / f"{name}.manifest.json" if manifest_dir else None
    if client.collection_exists(name):
        saved = json.loads(manifest_path.read_text()) if manifest_path and manifest_path.exists() else None
        count = client.count(name).count
        if saved and saved.get("manifest") == manifest and saved.get("chunks") == count:
            from research_copilot.storage.qdrant_client import ensure_sparse_idf
            upgraded = ensure_sparse_idf(client, name, sparse_vector_name)
            return {**manifest, "collection": name, "chunks": count, "reused": True, "idf_enabled_now": upgraded}
        client.delete_collection(name)

    children = chunk_corpus(data, chunk_size, chunk_overlap)
    create_collection(client, name, dense, sparse_vector_name)
    store = make_store(client, name, dense, sparse, RetrievalMode.HYBRID, sparse_vector_name)
    started = time.perf_counter()
    for start in range(0, len(children), batch_size):
        store.add_documents(children[start:start + batch_size], batch_size=batch_size)
        if progress:
            progress(min(start + batch_size, len(children)), len(children))
    if manifest_path:
        manifest_path.write_text(json.dumps({"manifest": manifest, "chunks": len(children)}, indent=2))
    return {**manifest, "collection": name, "chunks": len(children), "reused": False,
            "build_s": round(time.perf_counter() - started, 1)}


# --- evaluation ------------------------------------------------------------
@dataclass(frozen=True)
class RetrievalConfig:
    """One retrieval setting. ``None`` / "default" fields use the app's current production defaults."""
    name: str
    mode: str  # dense | sparse | hybrid
    k: int = 5
    fetch_k: Optional[int] = None  # chunk candidates per search leg; None = k * RETRIEVAL_FETCH_MULTIPLIER
    score_threshold: Optional[float] = None
    collapse: Optional[bool] = None  # one chunk per parent; None = RETRIEVAL_COLLAPSE_PARENTS
    min_relevance: Union[float, None, str] = "default"  # dense gate; "default" = RETRIEVAL_MIN_DENSE_SCORE
    bm25_idf: bool = True  # False = query a copy without Qdrant's IDF modifier (pre-fix BM25 scoring)
    fusion: Optional[str] = None  # hybrid fusion "rrf" | "dbsf"; None = RETRIEVAL_HYBRID_FUSION


def legacy(name: str, mode: str, k: int = 5, **changes) -> RetrievalConfig:
    """Retrieval exactly as before the fixes (k chunks, k candidates per leg, no gate, BM25 without
    IDF), plus ``changes``."""
    base = dict(fetch_k=k, score_threshold=0.7 if mode == "hybrid" else None, collapse=False,
                min_relevance=None, bm25_idf=False, fusion="rrf")
    base.update(changes)
    return RetrievalConfig(name, mode, k=k, **base)


PRODUCTION = RetrievalConfig("after", "hybrid", k=5)
# Cumulative steps from the original retrieval to the current production defaults.
DEFAULT_CONFIGS = (
    legacy("before", "hybrid"),
    legacy("+fetch20+collapse", "hybrid", fetch_k=20, collapse=True),
    legacy("+bm25-idf", "hybrid", fetch_k=20, collapse=True, bm25_idf=True),
    legacy("+dbsf-fetch40", "hybrid", fetch_k=40, collapse=True, bm25_idf=True, fusion="dbsf"),
    PRODUCTION,  # = previous step + dense relevance gate
    legacy("dense", "dense"),
    legacy("bm25", "sparse"),
    legacy("bm25-idf", "sparse", bm25_idf=True),
    legacy("before@10", "hybrid", k=10),
    RetrievalConfig("after@10", "hybrid", k=10),
)
_MODES = {"dense": RetrievalMode.DENSE, "sparse": RetrievalMode.SPARSE, "hybrid": RetrievalMode.HYBRID}


def _retrieve_kwargs(config: RetrievalConfig) -> dict:
    kwargs = {"k": config.k, "score_threshold": config.score_threshold}
    if config.fetch_k is not None:
        kwargs["fetch_k"] = config.fetch_k
    if config.collapse is not None:
        kwargs["collapse"] = config.collapse
    if config.min_relevance != "default":
        kwargs["min_relevance"] = config.min_relevance
    if config.fusion is not None:
        kwargs["fusion"] = config.fusion
    return kwargs


def evaluate_config(stores: dict, data: BeirData, config: RetrievalConfig,
                    query_ids: Optional[list] = None, off_topic: Optional[list] = None) -> dict:
    from research_copilot.rag.retriever import Retriever

    store = stores.get((config.mode, config.bm25_idf)) or stores[config.mode]
    retriever = Retriever(collection=store, parent_store=None, reranker=None, enable_reranking=False)
    kwargs = _retrieve_kwargs(config)
    evaluator = RAGEvaluator(id_key="corpus_id")
    rows, latencies = [], []
    for qid in query_ids or list(data.queries):
        started = time.perf_counter()
        docs = retriever.retrieve(data.queries[qid], **kwargs)
        latencies.append(time.perf_counter() - started)
        metrics = evaluator.evaluate_retrieval(data.queries[qid], docs, data.qrels[qid], k=config.k)
        rows.append({"query_id": qid, "retrieved": evaluator.ranked_ids(docs), "chunks": len(docs), **metrics})

    def avg(key):
        return round(mean(r[key] for r in rows), 4) if rows else None

    off_topic_empty = None
    if off_topic:
        off_topic_empty = round(sum(1 for q in off_topic if not retriever.retrieve(q, **kwargs)) / len(off_topic), 4)

    return {
        "config": asdict(config),
        "queries": len(rows),
        f"hit@{config.k}": avg("hit_rate@k"),
        f"recall@{config.k}": avg("recall@k"),
        f"mrr@{config.k}": avg("mrr"),
        f"ndcg@{config.k}": avg("ndcg@k"),
        f"precision@{config.k}": avg("precision@k"),
        "avg_chunks_returned": avg("chunks"),
        "avg_unique_docs": round(mean(len(r["retrieved"]) for r in rows), 3) if rows else None,
        "empty_result_rate": round(sum(1 for r in rows if not r["chunks"]) / len(rows), 4) if rows else None,
        "off_topic_empty_rate": off_topic_empty,
        "latency_ms": {"p50": _ms(percentile(latencies, 50)), "p95": _ms(percentile(latencies, 95))},
        "per_query": [{"query_id": r["query_id"], "retrieved": r["retrieved"]} for r in rows],
    }


def _ms(seconds):
    return None if seconds is None else round(seconds * 1000, 1)


def auroc(positives: list, negatives: list) -> Optional[float]:
    """Probability a random positive outscores a random negative (ties count half)."""
    if not positives or not negatives:
        return None
    wins = 0.0
    for p in positives:
        for n in negatives:
            wins += 1.0 if p > n else 0.5 if p == n else 0.0
    return round(wins / (len(positives) * len(negatives)), 4)


def score_separation(stores: dict, data: BeirData, off_topic: list, query_ids: Optional[list] = None,
                     thresholds=(0.3, 0.4, 0.5, 0.6, 0.7), k: int = 5) -> dict:
    """Can a top-score threshold tell answerable questions from off-topic ones?

    For each mode: AUROC of the top-1 score (in-corpus vs off-topic queries),
    and for dense, the trade-off at each threshold between keeping the gold
    document (hit@k) and returning nothing for off-topic queries.
    """
    query_ids = query_ids or list(data.queries)
    result = {"off_topic_queries": len(off_topic)}
    for mode in ("dense", "hybrid"):
        store = stores[mode]
        in_scored = {qid: store.similarity_search_with_score(data.queries[qid], k=k) for qid in query_ids}
        off_top = [store.similarity_search_with_score(q, k=1) for q in off_topic]
        in_top = [s[0][1] for s in in_scored.values() if s]
        off_top = [s[0][1] for s in off_top if s]
        entry = {"auroc_top1": auroc(in_top, off_top),
                 "top1_in_corpus": {"p50": percentile(in_top, 50), "p5": percentile(in_top, 5)},
                 "top1_off_topic": {"p50": percentile(off_top, 50), "p95": percentile(off_top, 95)}}
        if mode == "dense":
            sweep = []
            for t in thresholds:
                kept_hits = sum(
                    1 for qid, scored in in_scored.items()
                    if any(score >= t and doc.metadata.get("corpus_id") in data.qrels[qid] for doc, score in scored))
                sweep.append({"threshold": t,
                              f"hit@{k}": round(kept_hits / len(in_scored), 4),
                              "off_topic_abstain_rate": round(sum(1 for s in off_top if s < t) / len(off_top), 4)
                              if off_top else None})
            entry["threshold_sweep"] = sweep
        result[mode] = entry
    return result


def load_off_topic(path: Optional[Path], exclude_tags=("paper",)) -> list:
    """Off-topic probes: routing-dataset queries outside research-paper topics."""
    if not path or not Path(path).exists():
        return []
    queries = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            if not set(row.get("tags", [])) & set(exclude_tags) and "arxiv" not in row.get("required", []):
                queries.append(row["query"])
    return queries


# --- reporting -------------------------------------------------------------
def format_report(report: dict) -> str:
    def f(v):
        return "   -  " if v is None else f"{v:.3f}"

    idx = report["index"]
    lines = [
        f"Retrieval eval · {report['dataset']['name']} · {report['dataset']['queries']} queries · "
        f"{idx['chunks']} chunks (child {idx['chunk_size']}/{idx['chunk_overlap']})"
        + (" · index reused" if idx.get("reused") else f" · indexed in {idx.get('build_s')} s"),
        "",
        f"{'config':<18} {'k':>2} {'hit':>6} {'recall':>6} {'MRR':>6} {'nDCG':>6} {'P':>6} "
        f"{'docs':>5} {'empty':>6} {'offtop':>6} {'p50ms':>6} {'p95ms':>6}",
    ]
    for r in report["configs"]:
        k = r["config"]["k"]
        lines.append(
            f"{r['config']['name']:<18} {k:>2} {f(r[f'hit@{k}'])} {f(r[f'recall@{k}'])} {f(r[f'mrr@{k}'])} "
            f"{f(r[f'ndcg@{k}'])} {f(r[f'precision@{k}'])} {r['avg_unique_docs']:>5} "
            f"{f(r['empty_result_rate'])} {f(r.get('off_topic_empty_rate'))} "
            f"{r['latency_ms']['p50']:>6} {r['latency_ms']['p95']:>6}")
    sep = report.get("score_separation")
    if sep and sep.get("off_topic_queries"):
        lines += ["", f"Score separation vs {sep['off_topic_queries']} off-topic queries (AUROC of top-1 score):"]
        for mode in ("dense", "hybrid"):
            s = sep[mode]
            lines.append(f"  {mode:<7} AUROC {f(s['auroc_top1'])}   in-corpus top1 p50 {f(s['top1_in_corpus']['p50'])}"
                         f"   off-topic top1 p50 {f(s['top1_off_topic']['p50'])}")
        lines.append("  dense threshold sweep: " + ", ".join(
            f"t={row['threshold']}: hit {row['hit@5']:.2f} / off-topic abstain {row['off_topic_abstain_rate']:.2f}"
            for row in sep["dense"]["threshold_sweep"]))
    return "\n".join(lines)


def run_cli(args) -> int:
    from qdrant_client import QdrantClient
    from research_copilot.config import settings as config
    from research_copilot.evals.routing import _git_revision

    data = load_beir(Path(args.data_dir), split=args.split)
    query_ids = list(data.queries)[: args.limit] if args.limit else None
    dense, sparse = default_embeddings()
    index_dir = Path(args.index_dir)
    index_dir.mkdir(parents=True, exist_ok=True)
    client = QdrantClient(path=str(index_dir))
    sparse_name = getattr(config, "SPARSE_VECTOR_NAME", "sparse")

    def progress(done, total):
        print(f"  indexed {done}/{total} chunks", flush=True)

    index = build_index(client, data, dense, sparse, chunk_size=args.chunk_size, chunk_overlap=args.chunk_overlap,
                        sparse_vector_name=sparse_name, manifest_dir=index_dir,
                        progress=progress if args.verbose else None)
    noidf = legacy_copy_without_idf(client, index["collection"], sparse_name)
    stores = {}
    for mode, rm in _MODES.items():
        stores[mode] = stores[(mode, True)] = make_store(client, index["collection"], dense, sparse, rm, sparse_name)
        stores[(mode, False)] = make_store(client, noidf, dense, sparse, rm, sparse_name)

    configs = DEFAULT_CONFIGS
    if args.configs:
        wanted = set(args.configs.split(","))
        configs = tuple(c for c in DEFAULT_CONFIGS if c.name in wanted)
    off_topic = load_off_topic(Path(args.off_topic)) if args.off_topic else []
    results = [evaluate_config(stores, data, c, query_ids, off_topic) for c in configs]
    separation = score_separation(stores, data, off_topic, query_ids) if off_topic else None

    report = {
        "suite": "retrieval",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git": _git_revision(),
        "dataset": {"name": data.name, "split": args.split, "fingerprint": data.fingerprint,
                    "qrels_fingerprint": data.qrels_fingerprint,
                    "documents": len(data.corpus), "queries": len(query_ids or data.queries)},
        "models": {"dense": getattr(config, "DENSE_MODEL", None), "sparse": getattr(config, "SPARSE_MODEL", None)},
        "index": index,
        "configs": results,
        "score_separation": separation,
    }
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    label = f"-{args.label}" if args.label else ""
    out_path = out_dir / f"retrieval-{data.name}-c{args.chunk_size}{label}-{stamp}.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(format_report(report))
    print(f"\nWrote {out_path}")
    client.close()
    return 0
