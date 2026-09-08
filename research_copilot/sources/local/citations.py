from typing import List, Dict, Any, Optional
from pydantic import Field
from research_copilot.runtime.schemas import BaseCitation, SourceType
import logging

logger = logging.getLogger(__name__)

class LocalCitation(BaseCitation):
    """Citation model for local documents."""
    source_path: Optional[str] = None
    
    @classmethod
    def from_tool_result(cls, tool_result: Dict[str, Any], source_type: SourceType) -> Optional["LocalCitation"]:
        """Create citation from local document tool result."""
        source = tool_result.get("source", "")
        if not source:
            return None
        
        return cls(
            source_type=source_type,
            title=source.split("/")[-1] if "/" in source else source,
            url=f"local://{source}",
            snippet=tool_result.get("content", "")[:300],
            source_path=source,
            metadata={
                "parent_id": tool_result.get("parent_id", ""),
                "source_path": source
            }
        )
    
    def get_deduplication_key(self) -> str:
        """Use source_path as deduplication key."""
        if self.source_path:
            return f"local:{self.source_path.lower()}"
        return super().get_deduplication_key()
