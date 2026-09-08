from typing import List, Dict, Any, Optional
from pydantic import Field
from research_copilot.runtime.schemas import BaseCitation, SourceType
import logging

logger = logging.getLogger(__name__)

class YouTubeCitation(BaseCitation):
    """Citation model for YouTube videos."""
    video_id: Optional[str] = None
    channel: Optional[str] = None
    
    @classmethod
    def from_tool_result(cls, tool_result: Dict[str, Any], source_type: SourceType) -> Optional["YouTubeCitation"]:
        """Create citation from YouTube tool result."""
        video_id = tool_result.get("video_id", "")
        if not video_id:
            return None
        
        return cls(
            source_type=source_type,
            title=tool_result.get("title", "Unknown Video"),
            url=tool_result.get("url", f"https://www.youtube.com/watch?v={video_id}"),
            snippet=tool_result.get("description", "")[:300],
            video_id=video_id,
            channel=tool_result.get("channel"),
            metadata={
                "video_id": video_id,
                "duration": tool_result.get("duration"),
                "view_count": tool_result.get("view_count")
            }
        )
    
    def get_deduplication_key(self) -> str:
        """Use video_id as deduplication key."""
        if self.video_id:
            return f"youtube:{self.video_id.lower()}"
        return super().get_deduplication_key()
