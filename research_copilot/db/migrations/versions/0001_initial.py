"""Conversations, research runs, drafts, export ledger, and encrypted MCP connections.

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def _timestamps(updated=True):
    columns = [sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)]
    if updated:
        columns.append(sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    return columns


def upgrade():
    op.create_table(
        'conversations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('title', sa.Text, nullable=False),
        sa.Column('thread_id', sa.String(36), nullable=False),
        sa.Column('context_generation', sa.Text),
        sa.Column('stable_checkpoint_id', sa.Text),
        *_timestamps(),
    )
    op.create_table(
        'research_runs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('conversation_id', sa.String(36), sa.ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('request_id', sa.String(64), nullable=False),
        sa.Column('retry_of_run_id', sa.String(36), sa.ForeignKey('research_runs.id', ondelete='SET NULL')),
        sa.Column('status', sa.String(32), nullable=False),
        sa.Column('query', sa.Text, nullable=False),
        sa.Column('thread_id', sa.String(36), nullable=False),
        sa.Column('connection_generation', sa.Text),
        sa.Column('base_checkpoint_id', sa.Text),
        sa.Column('result_checkpoint_id', sa.Text),
        sa.Column('needs_clarification', sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column('result', JSONB),
        sa.Column('error', sa.Text),
        *_timestamps(),
        sa.Column('finished_at', sa.DateTime(timezone=True)),
        sa.UniqueConstraint('conversation_id', 'request_id', name='uq_research_runs_request'),
        sa.CheckConstraint(
            "status IN ('queued','running','awaiting_clarification','completed','failed','interrupted','superseded')",
            name='ck_research_runs_status'),
    )
    op.create_index('ix_research_runs_conversation', 'research_runs', ['conversation_id', 'created_at'])
    op.execute("CREATE UNIQUE INDEX uq_research_runs_one_active ON research_runs ((true)) "
               "WHERE status IN ('queued', 'running')")

    op.create_table(
        'messages',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('conversation_id', sa.String(36), sa.ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('run_id', sa.String(36), sa.ForeignKey('research_runs.id', ondelete='SET NULL')),
        sa.Column('request_id', sa.String(64)),
        sa.Column('position', sa.Integer, nullable=False),
        sa.Column('role', sa.String(16), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('clarification', sa.Boolean, nullable=False, server_default=sa.false()),
        *_timestamps(updated=False),
        sa.UniqueConstraint('conversation_id', 'position', name='uq_messages_position'),
        sa.CheckConstraint("role IN ('user','assistant','error')", name='ck_messages_role'),
    )
    op.create_index('uq_messages_request', 'messages', ['conversation_id', 'request_id'], unique=True,
                    postgresql_where=sa.text('request_id IS NOT NULL'))

    op.create_table(
        'run_events',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('run_id', sa.String(36), sa.ForeignKey('research_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('seq', sa.Integer, nullable=False),
        sa.Column('payload', JSONB, nullable=False),
        *_timestamps(updated=False),
        sa.UniqueConstraint('run_id', 'seq', name='uq_run_events_seq'),
    )

    op.create_table(
        'study_plan_drafts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('run_id', sa.String(36), sa.ForeignKey('research_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('conversation_id', sa.String(36), sa.ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.Text, nullable=False),
        sa.Column('plan', JSONB, nullable=False),
        sa.Column('markdown', sa.Text, nullable=False),
        sa.Column('connection_id', sa.Text),
        sa.Column('connection_generation', sa.Text, nullable=False),
        *_timestamps(updated=False),
    )
    op.create_index('ix_study_plan_drafts_run_id', 'study_plan_drafts', ['run_id'])

    op.create_table(
        'exports',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('idempotency_key', sa.String(64), nullable=False, unique=True),
        sa.Column('draft_id', sa.String(36), sa.ForeignKey('study_plan_drafts.id', ondelete='SET NULL')),
        sa.Column('destination', sa.Text),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('page_id', sa.Text),
        sa.Column('url', sa.Text),
        sa.Column('message', sa.Text, nullable=False, server_default=''),
        sa.Column('legacy', sa.Boolean, nullable=False, server_default=sa.false()),
        *_timestamps(),
        sa.CheckConstraint("status IN ('success','failure','unknown','pending')", name='ck_exports_status'),
    )

    op.create_table(
        'mcp_connections',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('provider', sa.String(32), nullable=False),
        sa.Column('server_url', sa.Text, nullable=False),
        sa.Column('issuer', sa.Text, nullable=False),
        sa.Column('token_endpoint', sa.Text, nullable=False),
        sa.Column('resource', sa.Text, nullable=False),
        sa.Column('workspace_id', sa.Text, nullable=False, server_default=''),
        sa.Column('workspace_name', sa.Text, nullable=False, server_default=''),
        sa.Column('status', sa.String(32), nullable=False),
        sa.Column('generation', sa.String(64), nullable=False),
        sa.Column('expires_at', sa.Double),
        sa.Column('record_version', sa.Integer, nullable=False, server_default='1'),
        sa.Column('key_version', sa.String(32)),
        sa.Column('nonce', sa.LargeBinary),
        sa.Column('ciphertext', sa.LargeBinary),
        *_timestamps(),
        sa.CheckConstraint("status IN ('connected','reconnect_required','disconnected')", name='ck_mcp_connections_status'),
        sa.CheckConstraint("status <> 'connected' OR (ciphertext IS NOT NULL AND nonce IS NOT NULL)",
                           name='ck_mcp_connections_payload'),
    )
    op.create_index('uq_mcp_connections_active_provider', 'mcp_connections', ['provider'], unique=True,
                    postgresql_where=sa.text("status <> 'disconnected'"))


def downgrade():
    for table in ('mcp_connections', 'exports', 'study_plan_drafts', 'run_events', 'messages', 'research_runs',
                  'conversations'):
        op.drop_table(table)
