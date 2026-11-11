"""A minimal real chat model, so LangChain callbacks and caching behave as in production."""
from typing import Any, List, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda


class FakeChat(BaseChatModel):
    """Answers with ``reply`` and reports fixed token usage."""

    reply: str = "ok"
    input_tokens: int = 10
    output_tokens: int = 3
    fail: bool = False
    calls: int = 0

    @property
    def _llm_type(self) -> str:
        return "fake-chat"

    def _generate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None,
                  run_manager=None, **kwargs: Any) -> ChatResult:
        self.calls += 1
        if self.fail:
            raise RuntimeError("provider unavailable")
        message = AIMessage(content=self.reply, usage_metadata={
            "input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
            "total_tokens": self.input_tokens + self.output_tokens})
        return ChatResult(generations=[ChatGeneration(message=message)])

    def with_structured_output(self, schema, **kwargs):
        return self | RunnableLambda(lambda message: schema.model_validate_json(message.content))


# --- Embedding fakes for retrieval tests -----------------------------------
import math as _math
import re as _re
from collections import Counter as _Counter

from langchain_core.embeddings import Embeddings as _Embeddings
from langchain_qdrant.sparse_embeddings import SparseEmbeddings as _SparseEmbeddings, SparseVector as _SparseVector

DIM = 256


def _tokens(text):
    return _re.findall(r"[a-z0-9]+", text.lower())


def _bucket(token):
    import zlib
    return zlib.crc32(token.encode()) % DIM  # deterministic across processes, unlike hash()


class BagOfWords(_Embeddings):
    """Dense fake: normalised hashed bag of words, so texts sharing words are similar and
    texts sharing none score ~0 (a constant bias term would make all unrelated texts identical)."""
    model_name = "fake-dense"

    def _vec(self, text):
        vec = [0.0] * DIM
        for token in _tokens(text):
            vec[_bucket(token)] += 1.0
        norm = _math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)


class HashSparse(_SparseEmbeddings):
    model_name = "fake-sparse"

    def _vec(self, text):
        by_id = _Counter(_bucket(token) for token in _tokens(text))
        ids = sorted(by_id)
        return _SparseVector(indices=ids, values=[float(by_id[i]) for i in ids])

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)


def hybrid_store(documents, mode=None):
    """An in-memory Qdrant store laid out like VectorDbManager's collections, filled with ``documents``."""
    from langchain_qdrant import QdrantVectorStore, RetrievalMode
    from qdrant_client import QdrantClient, models as qm

    dense, sparse = BagOfWords(), HashSparse()
    client = QdrantClient(location=":memory:")
    from research_copilot.storage.qdrant_client import create_or_upgrade_collection
    create_or_upgrade_collection(client, "test", dense_size=len(dense.embed_query("x")), sparse_vector_name="sparse")
    store = QdrantVectorStore(client=client, collection_name="test", embedding=dense, sparse_embedding=sparse,
                              retrieval_mode=mode or RetrievalMode.HYBRID, sparse_vector_name="sparse")
    store.add_documents(list(documents))
    return store
