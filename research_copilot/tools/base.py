from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from langchain_core.tools import BaseTool
from enum import Enum
from pydantic import BaseModel, Field

class SourceType(str, Enum):
    """Types of sources the research copilot can access."""
    LOCAL = "local"
    ARXIV = "arxiv"
    YOUTUBE = "youtube"
    GITHUB = "github"
    WEB = "web"

class Citation(BaseModel):
    """Standardized citation format across all sources."""
    source_type: SourceType
    title: str
    url: str
    authors: List[str] = Field(default_factory=list)
    date: Optional[str] = None
    snippet: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def to_markdown(self) -> str:
        """Format citation as markdown."""
        author_str = ", ".join(self.authors[:3])
        if len(self.authors) > 3:
            author_str += " et al."
        
        if self.source_type == SourceType.ARXIV:
            return f"[{self.title}]({self.url}) - {author_str} ({self.date})"
        elif self.source_type == SourceType.YOUTUBE:
            return f"📺 [{self.title}]({self.url})"
        elif self.source_type == SourceType.GITHUB:
            return f"💻 [{self.title}]({self.url})"
        else:
            return f"[{self.title}]({self.url})"

class ToolResult(BaseModel):
    """Standardized result format from all tools."""
    success: bool
    data: Any
    citations: List[Citation] = Field(default_factory=list)
    error: Optional[str] = None

class BaseToolkit(ABC):
    """Abstract base class for all tool factories."""
    
    source_type: SourceType
    
    @abstractmethod
    def create_tools(self) -> List[BaseTool]:
        """Create and return list of tools for this source."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this toolkit is properly configured and available."""
        pass
    
    def get_source_type(self) -> SourceType:
        """Return the source type for this toolkit."""
        return self.source_type
    
    def _create_citation(self, **kwargs) -> Citation:
        """Helper to create citations with source type pre-filled."""
        return Citation(source_type=self.source_type, **kwargs)