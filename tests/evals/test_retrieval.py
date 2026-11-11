"""Retrieval benchmark plumbing on a tiny BEIR-format corpus with deterministic fake embeddings."""
import json

import pytest
from langchain_qdrant import RetrievalMode
from qdrant_client import QdrantClient

from tests.evals.fakes import BagOfWords, HashSparse
from research_copilot.evals.retrieval import (
    PRODUCTION, RetrievalConfig, auroc, build_index, evaluate_config, load_beir, load_off_topic,
    make_store, score_separation,
)

@pytest.fixture
def beir_dir(tmp_path):
    corpus = {
        "d1": ("Rank fusion", "Reciprocal rank fusion merges rank lists. " * 30),
        "d2": ("BM25", "BM25 is a lexical ranking function. " * 5),
        "d3": ("Graphs", "A neighbour graph supports approximate search. " * 5),
        "d4": ("Chunking", "Parent chunk retrieval returns the parent of a chunk. " * 5),
        "d5": ("Clipping", "Gradient clip limits the gradient norm. " * 5),
    }
    (tmp_path / "qrels").mkdir()
    (tmp_path / "corpus.jsonl").write_text("\n".join(
        json.dumps({"_id": k, "title": t, "text": b}) for k, (t, b) in corpus.items()))
    (tmp_path / "queries.jsonl").write_text("\n".join(json.dumps(q) for q in [
        {"_id": "q1", "text": "rank fusion"}, {"_id": "q2", "text": "lexical bm25"},
        {"_id": "q3", "text": "gradient clip"}, {"_id": "q9", "text": "no qrels for me"}]))
    (tmp_path / "qrels" / "test.tsv").write_text(
        "query-id\tcorpus-id\tscore\nq1\td1\t1\nq2\td2\t1\nq3\td5\t1\nq3\td3\t0\n")
    return tmp_path


def test_load_beir_keeps_labelled_queries_and_positive_grades(beir_dir):
    data = load_beir(beir_dir)
    assert set(data.queries) == {"q1", "q2", "q3"}
    assert data.qrels["q3"] == {"d5": 1.0}
    assert data.corpus["d2"].startswith("BM25\n\nBM25 is")


def test_index_build_is_reused_and_long_docs_split_into_children(beir_dir, tmp_path):
    data = load_beir(beir_dir)
    client = QdrantClient(location=":memory:")
    dense, sparse = BagOfWords(), HashSparse()
    first = build_index(client, data, dense, sparse, chunk_size=200, chunk_overlap=20, manifest_dir=tmp_path)
    assert not first["reused"] and first["chunks"] > len(data.corpus)  # d1 is long enough to split
    again = build_index(client, data, dense, sparse, chunk_size=200, chunk_overlap=20, manifest_dir=tmp_path)
    assert again["reused"] and again["chunks"] == first["chunks"]


def test_configs_score_through_production_retriever(beir_dir, tmp_path):
    data = load_beir(beir_dir)
    client = QdrantClient(location=":memory:")
    dense, sparse = BagOfWords(), HashSparse()
    index = build_index(client, data, dense, sparse, chunk_size=200, chunk_overlap=20, manifest_dir=tmp_path)
    stores = {m: make_store(client, index["collection"], dense, sparse, rm)
              for m, rm in {"dense": RetrievalMode.DENSE, "sparse": RetrievalMode.SPARSE,
                            "hybrid": RetrievalMode.HYBRID}.items()}

    dense_result = evaluate_config(stores, data, RetrievalConfig("dense", "dense", k=3))
    assert dense_result["queries"] == 3 and dense_result["hit@3"] == 1.0
    assert dense_result["recall@3"] <= 1.0
    # d1 has several chunks; unique docs must be fewer than or equal to chunks returned
    assert dense_result["avg_unique_docs"] <= dense_result["avg_chunks_returned"]

    strict = evaluate_config(stores, data, RetrievalConfig("dense-strict", "dense", k=3, score_threshold=0.999))
    assert strict["empty_result_rate"] > 0

    production = evaluate_config(stores, data, PRODUCTION)
    assert production["config"]["mode"] == "hybrid" and production["queries"] == 3

    sep = score_separation(stores, data, ["completely unrelated words"], k=3)
    assert sep["dense"]["auroc_top1"] is not None
    assert [row["threshold"] for row in sep["dense"]["threshold_sweep"]] == [0.3, 0.4, 0.5, 0.6, 0.7]


def test_auroc():
    assert auroc([0.9, 0.8], [0.1, 0.2]) == 1.0
    assert auroc([0.5], [0.5]) == 0.5
    assert auroc([], [0.1]) is None


def test_off_topic_queries_exclude_paper_questions(tmp_path):
    path = tmp_path / "r.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in [
        {"query": "paper q", "required": ["arxiv"], "tags": ["paper"]},
        {"query": "time q", "required": ["arxiv", "web"], "tags": ["time"]},
        {"query": "morse code history", "required": ["web"], "tags": ["keyword-trap"]},
    ]))
    assert load_off_topic(path) == ["morse code history"]


def test_legacy_config_reproduces_pre_fix_retrieval_settings():
    from research_copilot.evals.retrieval import _retrieve_kwargs, legacy
    before = _retrieve_kwargs(legacy("before", "hybrid"))
    assert before == {"k": 5, "score_threshold": 0.7, "fetch_k": 5, "collapse": False, "min_relevance": None,
                      "fusion": "rrf"}
    gated = _retrieve_kwargs(legacy("+gate", "hybrid", min_relevance="default"))
    assert "min_relevance" not in gated  # falls through to the production default
    assert _retrieve_kwargs(PRODUCTION) == {"k": 5, "score_threshold": None}


def test_off_topic_empty_rate_measures_the_gate(beir_dir, tmp_path):
    from research_copilot.evals.retrieval import legacy
    data = load_beir(beir_dir)
    client = QdrantClient(location=":memory:")
    dense, sparse = BagOfWords(), HashSparse()
    index = build_index(client, data, dense, sparse, chunk_size=200, chunk_overlap=20, manifest_dir=tmp_path)
    stores = {m: make_store(client, index["collection"], dense, sparse, rm)
              for m, rm in {"dense": RetrievalMode.DENSE, "hybrid": RetrievalMode.HYBRID}.items()}
    off_topic = ["zebra migration patterns", "weather in lisbon"]
    ungated = evaluate_config(stores, data, legacy("before", "hybrid", k=3), off_topic=off_topic)
    gated = evaluate_config(stores, data, legacy("+gate", "hybrid", k=3, min_relevance=0.4), off_topic=off_topic)
    assert ungated["off_topic_empty_rate"] == 0.0
    assert gated["off_topic_empty_rate"] == 1.0
    assert gated["hit@3"] == ungated["hit@3"]  # on-topic questions unaffected


def test_index_fingerprint_ignores_which_split_is_scored(beir_dir):
    (beir_dir / "qrels" / "train.tsv").write_text("query-id\tcorpus-id\tscore\nq2\td2\t1\n")
    test, train = load_beir(beir_dir, "test"), load_beir(beir_dir, "train")
    assert test.fingerprint == train.fingerprint  # same documents -> reuse the same index
    assert test.qrels_fingerprint != train.qrels_fingerprint
