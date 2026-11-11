"""H2: the 0.7 score threshold was a no-op on hybrid scores; relevance is now gated on dense cosine."""
from langchain_core.documents import Document
from langchain_qdrant import RetrievalMode

from research_copilot.rag.retriever import Retriever
from tests.evals.fakes import hybrid_store

DOCS = [
    Document(page_content="reciprocal rank fusion merges rank lists", metadata={"parent_id": "p1", "source": "a.pdf"}),
    Document(page_content="bm25 is a lexical ranking function", metadata={"parent_id": "p2", "source": "b.pdf"}),
    Document(page_content="gradient clip limits the gradient norm", metadata={"parent_id": "p3", "source": "c.pdf"}),
]


def test_raw_threshold_has_no_effect_on_hybrid_scores():
    """Documents the original bug: a 0.7 threshold on fused scores keeps everything."""
    store = hybrid_store(DOCS)
    with_threshold = store.similarity_search("zebra migration patterns", k=3, score_threshold=0.7)
    without = store.similarity_search("zebra migration patterns", k=3)
    assert len(with_threshold) == len(without) == 3


def test_gate_blocks_off_topic_queries_in_hybrid_mode():
    retriever = Retriever(hybrid_store(DOCS), parent_store=None, min_relevance=0.4)
    assert retriever.top_dense_score("zebra migration patterns") < 0.4
    assert retriever.retrieve("zebra migration patterns", k=3) == []
    assert retriever.search("zebra migration patterns", k=3, use_reranking=False) == []


def test_gate_keeps_on_topic_queries():
    retriever = Retriever(hybrid_store(DOCS), parent_store=None, min_relevance=0.4)
    results = retriever.retrieve("rank fusion", k=3)
    assert results and results[0].metadata["parent_id"] == "p1"


def test_gate_can_be_disabled_and_overridden():
    store = hybrid_store(DOCS)
    assert len(Retriever(store, parent_store=None, min_relevance=None).retrieve("zebra", k=3)) == 3
    gated = Retriever(store, parent_store=None, min_relevance=0.4)
    assert len(gated.retrieve("zebra", k=3, min_relevance=None)) == 3


def test_gate_uses_scores_directly_in_dense_mode():
    store = hybrid_store(DOCS, mode=RetrievalMode.DENSE)
    retriever = Retriever(store, parent_store=None, min_relevance=0.4)
    assert retriever._dense_store() is store
    assert retriever.retrieve("zebra migration", k=3) == []


def test_gate_defaults_to_setting(monkeypatch):
    from research_copilot.config import settings
    monkeypatch.setattr(settings, "RETRIEVAL_MIN_DENSE_SCORE", 0.55, raising=False)
    assert Retriever(hybrid_store(DOCS), parent_store=None).min_relevance == 0.55


def test_local_tool_no_longer_passes_a_raw_threshold():
    from unittest.mock import Mock
    from research_copilot.sources.local.tools import LocalToolkit
    toolkit = LocalToolkit(config=None, collection=object())
    toolkit.retriever = Mock(search=Mock(return_value=[]))
    toolkit._search_child_chunks("q", k=4)
    _, kwargs = toolkit.retriever.search.call_args
    assert "score_threshold" not in kwargs
