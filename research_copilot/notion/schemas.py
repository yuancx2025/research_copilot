"""
Pydantic models for study plan structures.

Provides type-safe models for citations, resources, learning units, phases, and study plans.
"""

from typing import List, Dict, Any, Optional, Literal
from uuid import uuid4
from pydantic import BaseModel, Field


class Citation(BaseModel):
    """Citation model for references to sources."""
    source_type: str
    title: str
    url: str
    snippet: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Resource(BaseModel):
    """Resource model for learning materials."""
    title: str
    url: str
    type: Optional[str] = None  # For source type


class LearningUnit(BaseModel):
    """Atomic learning unit model."""
    name: str  # Title
    why_it_matters: str
    core_ideas: List[str]
    key_resources: List[Resource]
    deep_dive_resources: List[Resource]
    checkpoints: List[str]


class Phase(BaseModel):
    """Learning phase model."""
    phase_number: int
    name: str  # Title
    time_estimate: str
    phase_checkpoint: str
    topics: List[LearningUnit]


class StudyPlan(BaseModel):
    """Complete study plan model."""
    title: str
    overview: str
    outcome_objectives: List[str]
    phases: List[Phase]
    citations: List[Citation]  # Typed Citation models, not dicts
    next_steps: List[str]


class StudyPlanDraft(BaseModel):
    draft_id: str = Field(default_factory=lambda: str(uuid4()))
    plan: StudyPlan
    markdown: str
    connection_generation: str


class ExportResult(BaseModel):
    status: Literal['success', 'failure', 'unknown', 'pending']
    page_id: str | None = None
    url: str | None = None
    message: str = ''
