"""Pydantic models for study plan structures."""
from typing import List, Dict, Any, Optional
from uuid import uuid4
from pydantic import BaseModel, Field


class Citation(BaseModel):
    source_type: str
    title: str
    url: str
    snippet: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Resource(BaseModel):
    title: str
    url: str
    type: Optional[str] = None


class LearningUnit(BaseModel):
    name: str
    why_it_matters: str
    core_ideas: List[str]
    key_resources: List[Resource]
    deep_dive_resources: List[Resource]
    checkpoints: List[str]


class Phase(BaseModel):
    phase_number: int
    name: str
    time_estimate: str
    phase_checkpoint: str
    topics: List[LearningUnit]


class StudyPlan(BaseModel):
    title: str
    overview: str
    outcome_objectives: List[str]
    phases: List[Phase]
    citations: List[Citation]
    next_steps: List[str]


class StudyPlanDraft(BaseModel):
    draft_id: str = Field(default_factory=lambda: str(uuid4()))
    plan: StudyPlan
    markdown: str
    connection_generation: str
