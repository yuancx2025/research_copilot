from typing import List, Dict, Any, Optional
from pydantic import Field
from research_copilot.runtime.schemas import BaseCitation, SourceType
import logging

logger = logging.getLogger(__name__)

class ArxivCitation(BaseCitation):
    """Citation model for ArXiv papers."""
    authors: List[str] = Field(default_factory=list)
    date: Optional[str] = None
    
    @classmethod
    def from_tool_result(cls, tool_result: Dict[str, Any], source_type: SourceType) -> Optional["ArxivCitation"]:
        """Create citation from ArXiv tool result."""
        arxiv_id = tool_result.get("arxiv_id", "")
        if not arxiv_id:
            return None
        
        # Normalize authors field - handle both list and string formats
        authors_raw = tool_result.get("authors", [])
        if isinstance(authors_raw, str):
            # Split comma-separated string into list
            authors = [a.strip() for a in authors_raw.split(",") if a.strip()]
        elif isinstance(authors_raw, list):
            authors = authors_raw
        else:
            authors = []
        
        try:
            return cls(
                source_type=source_type,
                title=tool_result.get("title", "Unknown Paper"),
                url=tool_result.get("pdf_url", f"https://arxiv.org/abs/{arxiv_id}"),
                snippet=tool_result.get("abstract", "")[:300],
                authors=authors,
                date=tool_result.get("published", ""),
                metadata={
                    "arxiv_id": arxiv_id,
                    "categories": tool_result.get("categories", []),
                    "primary_category": tool_result.get("primary_category", "")
                }
            )
        except Exception as e:
            # Log validation error but don't crash - return None to skip this citation
            logger.warning(f"Failed to create ArxivCitation for {arxiv_id}: {e}")
            return None
    
    def get_deduplication_key(self) -> str:
        """Use arxiv_id as deduplication key."""
        arxiv_id = self.metadata.get("arxiv_id", "")
        if arxiv_id:
            return f"arxiv:{arxiv_id.lower()}"
        return super().get_deduplication_key()
