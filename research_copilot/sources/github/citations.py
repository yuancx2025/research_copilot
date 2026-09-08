from typing import List, Dict, Any, Optional
from pydantic import Field
from research_copilot.runtime.schemas import BaseCitation, SourceType
import logging

logger = logging.getLogger(__name__)

class GitHubCitation(BaseCitation):
    """Citation model for GitHub repositories."""
    repo: Optional[str] = None
    
    @classmethod
    def from_tool_result(cls, tool_result: Dict[str, Any], source_type: SourceType) -> Optional["GitHubCitation"]:
        """Create citation from GitHub tool result."""
        # Handle different GitHub result types
        repo = tool_result.get("full_name") or tool_result.get("repo", "")
        url = tool_result.get("url", "")
        
        # Special handling for README, file, and structure results
        if "repo" in tool_result and "content" in tool_result:
            # README result
            title = f"README: {repo}"
            snippet = tool_result.get("content", "")[:300]
            metadata = {
                "repo": repo,
                "path": tool_result.get("path", "README.md")
            }
        elif "repo" in tool_result and "path" in tool_result and "contents" not in tool_result:
            # File result
            title = f"{repo}/{tool_result.get('path', '')}"
            snippet = tool_result.get("content", "")[:500]
            metadata = {
                "repo": repo,
                "path": tool_result.get("path", ""),
                "size": tool_result.get("size", 0)
            }
        elif "repo" in tool_result and "contents" in tool_result:
            # Structure result
            title = f"Structure: {repo}"
            snippet = f"Repository structure with {len(tool_result.get('contents', []))} items"
            url = url or f"https://github.com/{repo}"
            metadata = {
                "repo": repo,
                "path": tool_result.get("path", ""),
                "item_count": len(tool_result.get("contents", []))
            }
        else:
            # Regular repository result
            if not repo and not url:
                return None
            title = tool_result.get("full_name", repo)
            snippet = tool_result.get("description", "")[:300]
            url = url or f"https://github.com/{repo}"
            metadata = {
                "full_name": tool_result.get("full_name", ""),
                "stars": tool_result.get("stars", 0),
                "language": tool_result.get("language", ""),
                "topics": tool_result.get("topics", [])
            }
        
        if not url:
            return None
        
        return cls(
            source_type=source_type,
            title=title,
            url=url,
            snippet=snippet,
            repo=repo,
            metadata=metadata
        )
    
    def get_deduplication_key(self) -> str:
        """Use repo as deduplication key, fallback to URL."""
        if self.repo:
            return f"github:{self.repo.lower()}"
        return super().get_deduplication_key()
