"""
Pydantic schemas for agent citations and results.

Provides type-safe citation models that can be extended by specific agents.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from research_copilot.tools.base import SourceType
import logging

logger = logging.getLogger(__name__)


class BaseCitation(BaseModel):
    """
    Base citation model with common fields across all sources.
    
    Agents can extend this for source-specific fields.
    """
    source_type: SourceType
    title: str
    url: str
    snippet: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        """Pydantic config."""
        use_enum_values = True  # Store enum as value (string)
        json_encoders = {
            SourceType: lambda v: v.value if isinstance(v, SourceType) else v
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backward compatibility."""
        # Works with both Pydantic v1 and v2
        try:
            return self.dict()
        except AttributeError:
            # Pydantic v2 uses model_dump()
            return self.model_dump()
    
    def get_deduplication_key(self) -> str:
        """
        Get a stable key for deduplication.
        
        Returns a unique identifier for this citation that can be used
        to deduplicate citations from the same source.
        """
        # Default: use URL as deduplication key
        return self.url.lower().strip()


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

