import math
from typing import Dict, Iterable, List, Mapping, Optional, Union

from langchain_core.documents import Document

Relevance = Union[Iterable[str], Mapping[str, float]]


class RAGEvaluator:
    """
    Retrieval metrics over ranked child chunks.

    Retrieval returns child chunks, but the unit that is relevant (and that the
    agent fetches as context) is the parent document. So:

    - hit rate, recall, MRR and nDCG work on the ranked list of *unique*
      parents, in the order their first chunk appeared. Two chunks of the same
      relevant parent count once; recall can never exceed 1.0.
    - precision counts *chunks*: the share of the k retrieved chunks whose
      parent is relevant, i.e. how much of the context budget is on target.

    ``k`` is always the number of retrieved chunks considered, because that is
    what the agent receives.
    """

    def __init__(self, id_key: Optional[str] = None):
        """``id_key`` picks the metadata field naming the relevant unit; by default parent_id, then source."""
        self.id_key = id_key

    # --- helpers -----------------------------------------------------------
    def doc_id(self, doc: Document) -> str:
        if self.id_key:
            return str(doc.metadata.get(self.id_key, ""))
        return doc.metadata.get("parent_id", "") or doc.metadata.get("source", "")

    def ranked_ids(self, retrieved_docs: List[Document], k: Optional[int] = None) -> List[str]:
        """Unique ids in first-appearance order within the top ``k`` chunks."""
        seen, ranked = set(), []
        for doc in retrieved_docs[:k] if k is not None else retrieved_docs:
            doc_id = self.doc_id(doc)
            if doc_id and doc_id not in seen:
                seen.add(doc_id)
                ranked.append(doc_id)
        return ranked

    @staticmethod
    def _gains(relevant: Relevance) -> Dict[str, float]:
        if isinstance(relevant, Mapping):
            return {str(k): float(v) for k, v in relevant.items() if float(v) > 0}
        return {str(r): 1.0 for r in relevant}

    # --- metrics -----------------------------------------------------------
    def hit_rate_at_k(self, retrieved_docs: List[Document], relevant_doc_ids: Relevance, k: int = 5) -> float:
        """1.0 if any relevant document appears in the top ``k`` chunks, else 0.0."""
        gains = self._gains(relevant_doc_ids)
        if not retrieved_docs or not gains:
            return 0.0
        return 1.0 if any(doc_id in gains for doc_id in self.ranked_ids(retrieved_docs, k)) else 0.0

    def mrr(self, retrieved_docs: List[Document], relevant_doc_ids: Relevance, k: Optional[int] = None) -> float:
        """1 / rank of the first relevant document (ranked by unique document), or 0.0."""
        gains = self._gains(relevant_doc_ids)
        if not retrieved_docs or not gains:
            return 0.0
        for rank, doc_id in enumerate(self.ranked_ids(retrieved_docs, k), start=1):
            if doc_id in gains:
                return 1.0 / rank
        return 0.0

    def precision_at_k(self, retrieved_docs: List[Document], relevant_doc_ids: Relevance, k: int = 5) -> float:
        """Share of the top ``k`` chunks whose document is relevant."""
        gains = self._gains(relevant_doc_ids)
        if not retrieved_docs or not gains or k <= 0:
            return 0.0
        relevant_chunks = sum(1 for doc in retrieved_docs[:k] if self.doc_id(doc) in gains)
        return relevant_chunks / k

    def recall_at_k(self, retrieved_docs: List[Document], relevant_doc_ids: Relevance, k: int = 5) -> float:
        """Share of relevant documents that appear in the top ``k`` chunks (each counted once)."""
        gains = self._gains(relevant_doc_ids)
        if not retrieved_docs or not gains:
            return 0.0
        found = set(self.ranked_ids(retrieved_docs, k)) & set(gains)
        return len(found) / len(gains)

    def ndcg_at_k(self, retrieved_docs: List[Document], relevant_doc_ids: Relevance, k: int = 10) -> float:
        """nDCG over unique documents from the top ``k`` chunks; graded if relevance is a mapping."""
        gains = self._gains(relevant_doc_ids)
        if not retrieved_docs or not gains:
            return 0.0
        ranked = self.ranked_ids(retrieved_docs, k)
        dcg = sum(gains.get(doc_id, 0.0) / math.log2(rank + 1) for rank, doc_id in enumerate(ranked, start=1))
        ideal = sorted(gains.values(), reverse=True)[:k]
        idcg = sum(g / math.log2(rank + 1) for rank, g in enumerate(ideal, start=1))
        return dcg / idcg if idcg else 0.0

    def evaluate_retrieval(self, query: str, retrieved_docs: List[Document],
                           relevant_doc_ids: Relevance, k: int = 5) -> Dict[str, float]:
        """All retrieval metrics at cutoff ``k``."""
        return {
            "hit_rate@k": self.hit_rate_at_k(retrieved_docs, relevant_doc_ids, k),
            "mrr": self.mrr(retrieved_docs, relevant_doc_ids, k),
            "precision@k": self.precision_at_k(retrieved_docs, relevant_doc_ids, k),
            "recall@k": self.recall_at_k(retrieved_docs, relevant_doc_ids, k),
            "ndcg@k": self.ndcg_at_k(retrieved_docs, relevant_doc_ids, k),
        }

    def compare_retrieval(self, baseline_docs: List[Document], improved_docs: List[Document],
                          relevant_doc_ids: Relevance, k: int = 5) -> Dict[str, Dict[str, float]]:
        """Metrics for two rankings of the same query."""
        return {
            "baseline": self.evaluate_retrieval("", baseline_docs, relevant_doc_ids, k),
            "improved": self.evaluate_retrieval("", improved_docs, relevant_doc_ids, k),
        }
