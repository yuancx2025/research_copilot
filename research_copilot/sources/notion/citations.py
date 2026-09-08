from typing import List, Dict, Any, Optional
from pydantic import Field
from research_copilot.runtime.schemas import BaseCitation, SourceType
import logging

logger = logging.getLogger(__name__)

class NotionCitation(BaseCitation):
    """Evidence from a fetched page, not a search snippet."""
    pass
