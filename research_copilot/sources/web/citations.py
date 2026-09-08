from typing import List, Dict, Any, Optional
from pydantic import Field
from research_copilot.runtime.schemas import BaseCitation, SourceType
import logging

logger = logging.getLogger(__name__)

class WebCitation(BaseCitation):
    """Citation model for web pages."""
    @classmethod
    def from_tool_result(cls, tool_result: Dict[str, Any], source_type: SourceType) -> Optional["WebCitation"]:
        """Create citation from web tool result."""
        url = tool_result.get("url", "")
        if not url:
            return None
        
        # Handle structured content
        if "structured_content" in tool_result:
            structured = tool_result["structured_content"]
            return cls(
                source_type=source_type,
                title=structured.get("title", "Unknown Page"),
                url=url,
                snippet=" ".join(structured.get("paragraphs", [])[:3])[:300],
                metadata={
                    "headings": structured.get("headings", []),
                    "code_blocks": len(structured.get("code_blocks", []))
                }
            )
        
        # Handle code extraction result
        if "code_blocks" in tool_result:
            return cls(
                source_type=source_type,
                title=f"Code Examples: {url.split('/')[-1]}",
                url=url,
                snippet=f"Extracted {len(tool_result.get('code_blocks', []))} code blocks",
                metadata={
                    "code_blocks": tool_result.get("code_blocks", []),
                    "url": url
                }
            )
        
        # Regular webpage content
        title = tool_result.get("title", url.split("/")[-1])
        snippet = tool_result.get("content", "")[:300] or tool_result.get("snippet", "")[:300]
        
        # Extract domain from URL
        domain = ""
        if "/" in url:
            try:
                domain = url.split("/")[2]
            except IndexError:
                pass
        
        return cls(
            source_type=source_type,
            title=title,
            url=url,
            snippet=snippet,
            metadata={
                "word_count": tool_result.get("word_count", 0),
                "domain": domain,
                "score": tool_result.get("score", 0)
            }
        )
