"""Request and response bodies for the JSON API.

Run event streams emit ``progress``, ``result`` and ``error`` SSE events, each
with a per-run ``seq``; ``result`` events carry the committed ``RunOut``.
Upload streams emit ``progress`` and a ``result`` matching ``UploadResultOut``.
"""
from datetime import datetime
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field

RequestId = Field(min_length=8, max_length=64, pattern=r'^[A-Za-z0-9_-]+$')
RunStatus = Literal['queued', 'running', 'awaiting_clarification', 'completed', 'failed', 'interrupted',
                    'superseded']


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


class ConversationCreate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)


class RunCreate(BaseModel):
    message: str = Field('', max_length=4000)
    request_id: str = RequestId
    retry_of_run_id: Optional[str] = Field(None, max_length=36)


class ReplyCreate(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    request_id: str = RequestId


class PreviewRequest(BaseModel):
    run_id: str = Field(min_length=1, max_length=36)


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
    run_id: str
    query: str
    answer: str
    citations: List[CitationOut]
    sources: Dict[str, int]
    needs_clarification: bool
    can_preview_plan: bool
    generation: Optional[str] = None


class RunOut(BaseModel):
    id: str
    conversation_id: str
    request_id: str
    status: RunStatus
    query: str
    retry_of_run_id: Optional[str] = None
    error: Optional[str] = None
    last_seq: int = 0
    created_at: datetime
    finished_at: Optional[datetime] = None
    result: Optional[ResearchResultOut] = None


class MessageOut(BaseModel):
    id: str
    role: Literal['user', 'assistant', 'error']
    content: str
    clarification: bool
    run_id: Optional[str] = None
    request_id: Optional[str] = None
    created_at: datetime


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class DraftOut(BaseModel):
    draft_id: str
    run_id: str
    title: str
    markdown: str
    exportable: bool


class ConversationDetailOut(ConversationOut):
    messages: List[MessageOut]
    runs: List[RunOut]
    drafts: List[DraftOut]


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
