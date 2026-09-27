"""Request and response bodies for the JSON API.

Streaming endpoints emit ``progress``, ``result`` and ``error`` SSE events whose
``result`` payloads match ``ResearchResultOut`` and ``UploadResultOut``.
"""
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class ConfigOut(BaseModel):
    notion_backend: Literal['disabled', 'rest', 'mcp']
    default_destination: str = ''
    sources: List[str] = []
    csrf: Optional[str] = None


class DocumentsOut(BaseModel):
    documents: List[str]


class UploadResultOut(BaseModel):
    added: int
    skipped: int
    documents: List[str]


class ResearchRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class CitationOut(BaseModel):
    source_type: str
    title: str
    url: str
    snippet: str = ''
    authors: List[str] = []
    date: Optional[str] = None
    channel: Optional[str] = None
    repo: Optional[str] = None


class ResearchResultOut(BaseModel):
    query: str
    answer: str
    citations: List[CitationOut]
    sources: Dict[str, int]
    needs_clarification: bool
    can_preview_plan: bool
    generation: Optional[str] = None


class LastResearchOut(BaseModel):
    running: bool
    result: Optional[ResearchResultOut] = None


class DraftOut(BaseModel):
    draft_id: str
    title: str
    markdown: str


class PageOut(BaseModel):
    title: str
    ref: str


class ExportRequest(BaseModel):
    draft_id: str
    destination: str = Field(min_length=1, max_length=500)


class ExportOut(BaseModel):
    status: Literal['success', 'failure', 'unknown', 'pending']
    page_id: Optional[str] = None
    url: Optional[str] = None
    message: str = ''
    retryable: bool
