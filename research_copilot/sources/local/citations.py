from typing import List, Dict, Any, Optional
from pathlib import PurePosixPath
from pydantic import Field
from research_copilot.runtime.schemas import BaseCitation, SourceType
import logging

logger = logging.getLogger(__name__)

SEARCH_HIT = "search_hit"
FETCHED = "fetched"


class LocalCitation(BaseCitation):
    """Citation model for local documents."""
    source_path: Optional[str] = None

    @classmethod
    def _build(cls, source: str, content: str, parent_id: str, source_type: SourceType,
               evidence: str) -> "LocalCitation":
        return cls(
            source_type=source_type,
            title=source.split("/")[-1] if "/" in source else source,
            url=f"local://{source}",
            snippet=(content or "")[:300],
            source_path=source,
            metadata={"parent_id": parent_id, "source_path": source, "evidence": evidence},
        )

    @classmethod
    def from_tool_result(cls, tool_result: Dict[str, Any], source_type: SourceType) -> Optional["LocalCitation"]:
        """Citation for a search hit (a child chunk with a top-level ``source``)."""
        source = tool_result.get("source", "")
        if not source:
            return None
        return cls._build(source, tool_result.get("content", ""), tool_result.get("parent_id", ""),
                          source_type, SEARCH_HIT)

    @classmethod
    def from_parent(cls, parent: Dict[str, Any], source_type: SourceType) -> Optional["LocalCitation"]:
        """Citation for a parent section the agent fetched and read (source lives in its metadata)."""
        metadata = parent.get("metadata") or {}
        source = metadata.get("source") or parent.get("source") or ""
        if not source or not parent.get("content"):
            return None
        return cls._build(source, parent["content"], parent.get("parent_id", ""), source_type, FETCHED)

    @property
    def evidence(self) -> str:
        return (self.metadata or {}).get("evidence", SEARCH_HIT)

    def get_deduplication_key(self) -> str:
        """One citation per document *and* evidence kind, so a fetch is not hidden by an earlier hit."""
        if self.source_path:
            return f"local:{self.source_path.lower()}:{self.evidence}"
        return super().get_deduplication_key()


def mentioned_in(answer: str, source: str) -> bool:
    """Whether the answer names this document by file name, or by stem when it is distinctive."""
    text = (answer or "").lower()
    name = PurePosixPath(source.replace("\\", "/")).name.lower()
    stem = name.rsplit(".", 1)[0]
    return bool(name and name in text) or (len(stem) >= 4 and stem in text)


def select_local_citations(answer: str, citations: List[LocalCitation]) -> List[LocalCitation]:
    """Keep documents the answer is grounded in: fetched parents, plus search hits the answer names.

    A search hit alone is not evidence that the answer used the document, the
    same rule the Notion agent applies (only fetched pages count).
    """
    selected, seen = [], set()
    for citation in citations:
        key = (citation.source_path or citation.url or "").lower()
        if citation.evidence == FETCHED and key not in seen:
            seen.add(key)
            selected.append(citation)
    for citation in citations:
        key = (citation.source_path or citation.url or "").lower()
        if citation.evidence != FETCHED and key not in seen and mentioned_in(answer, citation.source_path or ""):
            seen.add(key)
            selected.append(citation)
    return selected
