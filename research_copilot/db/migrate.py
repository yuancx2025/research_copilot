"""Explicit schema upgrades: Alembic for application tables, then LangGraph's own tables."""
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from research_copilot.db.engine import _checked_schema, psycopg_url, sqlalchemy_url

MIGRATIONS_DIR = Path(__file__).parent / 'migrations'


def alembic_config(url=None, schema=None) -> Config:
    config = Config()
    config.set_main_option('script_location', str(MIGRATIONS_DIR))
    if url:
        config.attributes['url'] = sqlalchemy_url(url)
    config.attributes['schema'] = _checked_schema(schema)
    return config


def head_revision() -> str:
    return ScriptDirectory.from_config(alembic_config()).get_current_head()


def setup_checkpointer(url, schema=None):
    import psycopg
    from psycopg.rows import dict_row
    from langgraph.checkpoint.postgres import PostgresSaver

    with psycopg.connect(psycopg_url(url), autocommit=True, prepare_threshold=0, row_factory=dict_row) as conn:
        if schema:
            conn.execute(f'SET search_path TO "{_checked_schema(schema)}"')
        PostgresSaver(conn).setup()


def upgrade(url, schema=None):
    command.upgrade(alembic_config(url, schema), 'head')
    setup_checkpointer(url, schema)
