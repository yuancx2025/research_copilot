"""Shared source identifiers and the production citation base model."""
from typing import List, Dict, Any, Optional
from enum import Enum
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)


class SourceType(str, Enum):
    """Types of sources the research copilot can access."""
    LOCAL = "local"
    ARXIV = "arxiv"
    YOUTUBE = "youtube"
    GITHUB = "github"
    WEB = "web"
    NOTION = "notion"


class BaseCitation(BaseModel):
    """Common citation fields. Source packages extend this for extra metadata."""
    source_type: SourceType
    title: str
    url: str
    snippet: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True
        json_encoders = {
            SourceType: lambda v: v.value if isinstance(v, SourceType) else v
        }

    def to_dict(self) -> Dict[str, Any]:
        try:
            return self.dict()
        except AttributeError:
            return self.model_dump()

    def get_deduplication_key(self) -> str:
        return self.url.lower().strip()
