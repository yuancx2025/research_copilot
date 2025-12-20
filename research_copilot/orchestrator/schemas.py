from typing import List, Optional, Dict
from pydantic import BaseModel, Field

class QueryAnalysis(BaseModel):
    is_clear: bool = Field(
        description="Indicates if the user's question is clear and answerable."
    )
    questions: List[str] = Field(
        description="List of rewritten, self-contained questions."
    )
    clarification_needed: str = Field(
        description="Explanation if the question is unclear."
    )


class ResearchIntent(BaseModel):
    """
    Structured output for LLM-driven intent classification.
    
    Used by the orchestrator to determine which specialized agents
    should handle a given research query.
    """
    agents: List[str] = Field(
        description="List of agent types to invoke: 'arxiv', 'youtube', 'github', 'web', 'local'"
    )
    reasoning: str = Field(
        description="Explanation of why these agents were selected for this query"
    )
    confidence: float = Field(
        description="Confidence score between 0.0 and 1.0 indicating certainty of agent selection",
        ge=0.0,
        le=1.0
    )
    suggested_queries: Optional[Dict[str, str]] = Field(
        default=None,
        description="Agent-specific query refinements if the original query needs adaptation for specific agents"
    )