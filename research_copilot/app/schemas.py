"""Request and response bodies for the JSON API.

Run event streams emit ``progress``, ``result`` and ``error`` SSE events, each
with a per-run ``seq``; ``result`` events carry the committed ``RunOut``.
Upload streams emit ``progress`` and a ``result`` matching ``UploadResultOut``.
"""
from datetime import datetime
from typing import Annotated, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, RootModel

RequestId = Field(min_length=8, max_length=64, pattern=r'^[A-Za-z0-9_-]+$')
RunStatus = Literal['queued', 'running', 'awaiting_clarification', 'completed', 'failed', 'interrupted',
                    'superseded']


class ResponseModel(BaseModel):
    # FastAPI emits these defaults, so the output contract must describe them.
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class ConfigOut(ResponseModel):
    notion_backend: Literal['disabled', 'rest', 'mcp']
    default_destination: str = ''
    sources: List[str] = []
    csrf: Optional[str] = None


class DocumentsOut(ResponseModel):
    documents: List[str]


class UploadResultOut(ResponseModel):
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


class CitationOut(ResponseModel):
    source_type: str
    title: str
    url: str
    snippet: str = ''
    authors: List[str] = []
    date: Optional[str] = None
    channel: Optional[str] = None
    repo: Optional[str] = None


class ResearchResultOut(ResponseModel):
    run_id: str
    query: str
    answer: str
    citations: List[CitationOut]
    sources: Dict[str, int]
    needs_clarification: bool
    can_preview_plan: bool
    generation: Optional[str] = None


class RunOut(ResponseModel):
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


class MessageOut(ResponseModel):
    id: str
    role: Literal['user', 'assistant', 'error']
    content: str
    clarification: bool
    run_id: Optional[str] = None
    request_id: Optional[str] = None
    created_at: datetime


class ConversationOut(ResponseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class DraftOut(ResponseModel):
    draft_id: str
    run_id: str
    title: str
    markdown: str
    exportable: bool


class ConversationDetailOut(ConversationOut):
    messages: List[MessageOut]
    runs: List[RunOut]
    drafts: List[DraftOut]


class PageOut(ResponseModel):
    title: str
    ref: str


class ExportRequest(BaseModel):
    draft_id: str
    destination: str = Field(min_length=1, max_length=500)


class ExportOut(ResponseModel):
    status: Literal['success', 'failure', 'unknown', 'pending']
    page_id: Optional[str] = None
    url: Optional[str] = None
    message: str = ''
    retryable: bool


class NotionStatusOut(ResponseModel):
    status: Literal['connected', 'connecting', 'disconnected', 'reconnect_required', 'failed']
    workspace: str
    generation: Optional[str]
    error: Optional[str]
    csrf: str


class NotionStartOut(ResponseModel):
    authorization_url: str


class NotionDisconnectOut(ResponseModel):
    status: Literal['disconnected']
    message: str


class ResearchProgressEvent(BaseModel):
    type: Literal['progress']
    seq: int = Field(gt=0)
    run_id: str
    node: str
    agents: Optional[List[str]] = None
    source: Optional[str] = None
    clear: Optional[bool] = None


class ResearchResultEvent(BaseModel):
    type: Literal['result']
    seq: int = Field(gt=0)
    run_id: str
    run: RunOut


class ResearchErrorEvent(BaseModel):
    type: Literal['error']
    seq: int = Field(gt=0)
    run_id: str
    message: str
    status: RunStatus


class ResearchEventOut(RootModel[Annotated[
    Union[ResearchProgressEvent, ResearchResultEvent, ResearchErrorEvent], Field(discriminator='type')
]]):
    pass


class UploadProgressEvent(BaseModel):
    type: Literal['progress']
    fraction: float
    message: str


class UploadResultEvent(UploadResultOut):
    type: Literal['result']


class UploadErrorEvent(BaseModel):
    type: Literal['error']
    message: str


class UploadEventOut(RootModel[Annotated[
    Union[UploadProgressEvent, UploadResultEvent, UploadErrorEvent], Field(discriminator='type')
]]):
    pass
