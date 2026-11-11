"""M4: fetch more candidates per hybrid leg; M5: return distinct parents instead of sibling chunks."""
from unittest.mock import MagicMock

from langchain_core.documents import Document

from research_copilot.rag.retriever import Retriever, collapse_by_parent
from tests.evals.fakes import hybrid_store


def _chunk(parent, text="x"):
    return Document(page_content=text, metadata={"parent_id": parent, "source": f"{parent}.pdf"})


def test_collapse_keeps_best_chunk_per_parent_in_rank_order():
    docs = [_chunk("a", "a1"), _chunk("a", "a2"), _chunk("b", "b1"), _chunk("a", "a3"), _chunk("c", "c1")]
    assert [d.page_content for d in collapse_by_parent(docs, 2)] == ["a1", "b1"]
    assert [d.page_content for d in collapse_by_parent(docs, 5)] == ["a1", "b1", "c1"]


def test_docs_without_parent_ids_are_not_merged():
    docs = [Document(page_content="one"), Document(page_content="two")]
    assert len(collapse_by_parent(docs, 5)) == 2


def test_default_fetch_depth_is_k_times_multiplier():
    collection = MagicMock()
    collection.similarity_search.return_value = []
    Retriever(collection, None, fetch_multiplier=4, min_relevance=None).retrieve("q", k=5)
    assert collection.similarity_search.call_args[1]["k"] == 20
    Retriever(collection, None, fetch_multiplier=None, min_relevance=None).retrieve("q", k=5)
    assert collection.similarity_search.call_args[1]["k"] == 5


def test_explicit_fetch_k_wins():
    collection = MagicMock()
    collection.similarity_search.return_value = []
    Retriever(collection, None, fetch_multiplier=4, min_relevance=None).retrieve("q", k=5, fetch_k=7)
    assert collection.similarity_search.call_args[1]["k"] == 7


def test_real_store_returns_k_distinct_parents():
    """A long parent split into many chunks must not crowd out other parents."""
    long_parent = [_chunk("p_long", "rank fusion merges rank lists " * 3) for _ in range(6)]
    others = [_chunk("p_bm25", "bm25 rank function"), _chunk("p_graph", "graph rank neighbour"),
              _chunk("p_clip", "gradient clip")]
    store = hybrid_store(long_parent + others)

    legacy = Retriever(store, None, min_relevance=None, fetch_multiplier=None, collapse_parents=False)
    legacy_parents = [d.metadata["parent_id"] for d in legacy.retrieve("rank fusion", k=3)]
    assert legacy_parents == ["p_long"] * 3  # the old behaviour: three copies of one parent

    fixed = Retriever(store, None, min_relevance=None, fetch_multiplier=4, collapse_parents=True)
    parents = [d.metadata["parent_id"] for d in fixed.retrieve("rank fusion", k=3)]
    assert parents[0] == "p_long" and len(set(parents)) == 3


def test_rerank_path_collapses_after_scoring_every_candidate():
    candidates = [_chunk("a", "a1"), _chunk("a", "a2"), _chunk("b", "b1"), _chunk("c", "c1")]
    collection = MagicMock()
    collection.similarity_search.return_value = candidates
    reranker = MagicMock()
    reranker.is_available.return_value = True
    # Reranker prefers a2 over a1, then c, then b
    reranker.rerank.return_value = [(candidates[1], 0.9), (candidates[0], 0.8), (candidates[3], 0.7),
                                    (candidates[2], 0.1)]
    retriever = Retriever(collection, None, reranker=reranker, enable_reranking=True,
                          min_relevance=None, collapse_parents=True)
    out = retriever.retrieve_with_rerank("q", k=2, initial_k=4)
    assert [d.page_content for d, _ in out] == ["a2", "c1"]
    assert reranker.rerank.call_args[1]["top_k"] == 4  # every candidate scored before collapsing


def test_fusion_reaches_real_hybrid_stores_only():
    import pytest
    from qdrant_client import models as qm
    store = hybrid_store([_chunk("a", "rank fusion"), _chunk("b", "bm25 rank")])
    seen = []
    original = store.similarity_search

    def spy(query, k=4, **kwargs):
        seen.append(kwargs.get("hybrid_fusion"))
        return original(query, k=k, **kwargs)

    store.similarity_search = spy
    Retriever(store, None, min_relevance=None, fusion="dbsf").retrieve("rank", k=2)
    Retriever(store, None, min_relevance=None, fusion="rrf").retrieve("rank", k=2)
    assert [f.fusion for f in seen] == [qm.Fusion.DBSF, qm.Fusion.RRF]

    collection = MagicMock()
    collection.similarity_search.return_value = []
    Retriever(collection, None, min_relevance=None, fusion="dbsf").retrieve("q", k=2, fetch_k=3)
    collection.similarity_search.assert_called_once_with("q", k=3, score_threshold=None)

    with pytest.raises(ValueError):
        Retriever(store, None, min_relevance=None, fusion="nonsense").retrieve("rank", k=2)
