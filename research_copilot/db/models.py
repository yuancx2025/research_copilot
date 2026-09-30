"""Application tables. LangGraph owns its checkpoint tables separately."""
import uuid
from datetime import datetime

from sqlalchemy import (Boolean, DateTime, Double, ForeignKey, Index, Integer, LargeBinary, String,
                        Text, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

ACTIVE_RUN_STATUSES = ('queued', 'running')
RUN_STATUSES = ('queued', 'running', 'awaiting_clarification', 'completed', 'failed', 'interrupted',
                'superseded')
RESULT_VERSION = 1
PLAN_VERSION = 1


def new_id() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


def _created():
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def _updated():
    return mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
                         nullable=False)


class Conversation(Base):
    __tablename__ = 'conversations'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(Text, nullable=False, default='New conversation')
    thread_id: Mapped[str] = mapped_column(String(36), nullable=False, default=new_id)
    context_generation: Mapped[str | None] = mapped_column(Text)
    stable_checkpoint_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class ResearchRun(Base):
    __tablename__ = 'research_runs'
    __table_args__ = (
        UniqueConstraint('conversation_id', 'request_id', name='uq_research_runs_request'),
        Index('ix_research_runs_conversation', 'conversation_id', 'created_at'),
        Index('uq_research_runs_one_active', text('(true)'), unique=True,
              postgresql_where=text("status IN ('queued', 'running')")),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    retry_of_run_id: Mapped[str | None] = mapped_column(ForeignKey('research_runs.id', ondelete='SET NULL'))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='queued')
    query: Mapped[str] = mapped_column(Text, nullable=False)
    thread_id: Mapped[str] = mapped_column(String(36), nullable=False)
    connection_generation: Mapped[str | None] = mapped_column(Text)
    base_checkpoint_id: Mapped[str | None] = mapped_column(Text)
    result_checkpoint_id: Mapped[str | None] = mapped_column(Text)
    needs_clarification: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    result: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Message(Base):
    __tablename__ = 'messages'
    __table_args__ = (
        UniqueConstraint('conversation_id', 'position', name='uq_messages_position'),
        Index('uq_messages_request', 'conversation_id', 'request_id', unique=True,
              postgresql_where=text('request_id IS NOT NULL')),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False)
    run_id: Mapped[str | None] = mapped_column(ForeignKey('research_runs.id', ondelete='SET NULL'))
    request_id: Mapped[str | None] = mapped_column(String(64))
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    clarification: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = _created()


class RunEvent(Base):
    __tablename__ = 'run_events'
    __table_args__ = (UniqueConstraint('run_id', 'seq', name='uq_run_events_seq'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey('research_runs.id', ondelete='CASCADE'), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = _created()


class StudyPlanDraftRow(Base):
    __tablename__ = 'study_plan_drafts'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey('research_runs.id', ondelete='CASCADE'), nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    plan: Mapped[dict] = mapped_column(JSONB, nullable=False)
    markdown: Mapped[str] = mapped_column(Text, nullable=False)
    connection_id: Mapped[str | None] = mapped_column(Text)
    connection_generation: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created()


class ExportRow(Base):
    __tablename__ = 'exports'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    draft_id: Mapped[str | None] = mapped_column(ForeignKey('study_plan_drafts.id', ondelete='SET NULL'))
    destination: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    page_id: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str] = mapped_column(Text, nullable=False, default='')
    legacy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class McpConnection(Base):
    __tablename__ = 'mcp_connections'
    __table_args__ = (
        Index('uq_mcp_connections_active_provider', 'provider', unique=True,
              postgresql_where=text("status <> 'disconnected'")),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    server_url: Mapped[str] = mapped_column(Text, nullable=False)
    issuer: Mapped[str] = mapped_column(Text, nullable=False)
    token_endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    resource: Mapped[str] = mapped_column(Text, nullable=False)
    workspace_id: Mapped[str] = mapped_column(Text, nullable=False, default='')
    workspace_name: Mapped[str] = mapped_column(Text, nullable=False, default='')
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    generation: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[float | None] = mapped_column(Double)
    record_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    key_version: Mapped[str | None] = mapped_column(String(32))
    nonce: Mapped[bytes | None] = mapped_column(LargeBinary)
    ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()
