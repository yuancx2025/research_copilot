"""
Notion module for study plan generation and Notion API integration.

This module provides:
- Pydantic models for type-safe study plan structures
- Notion API client for HTTP operations
- Notion renderer for converting study plans to blocks
- Study plan generator with LLM integration
- REST and MCP export paths for published study plans
"""

from research_copilot.notion.schemas import (
    Citation,
    Resource,
    LearningUnit,
    Phase,
    StudyPlan
)
from research_copilot.notion.notion_client import create_page, append_blocks
from research_copilot.notion.notion_renderer import render_study_plan
from research_copilot.notion.study_plan_generator import StudyPlanGenerator

__all__ = [
    "Citation",
    "Resource",
    "LearningUnit",
    "Phase",
    "StudyPlan",
    "create_page",
    "append_blocks",
    "render_study_plan",
    "StudyPlanGenerator",
]

