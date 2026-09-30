"""PostgreSQL connections for application records and LangGraph checkpoints.

Use Neon's direct (non-pooler) endpoint: the checkpointer's setup and prepared
statements do not work through PgBouncer transaction pooling. Both pools check
connections because Neon suspends idle computes and drops their sessions.
"""
import os
import re
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

SCHEMA_NAME = re.compile(r'^[a-z_][a-z0-9_]{0,62}$')


class DatabaseConfigError(RuntimeError):
    pass


def database_url(env=None) -> str:
    url = (env if env is not None else os.environ).get('DATABASE_URL', '').strip()
    if not url:
        raise DatabaseConfigError(
            'DATABASE_URL is not set. Point it at your Neon direct endpoint, then run '
            '`research-copilot-admin db upgrade`.')
    if urlsplit(url).scheme not in ('postgresql', 'postgres', 'postgresql+psycopg'):
        raise DatabaseConfigError('DATABASE_URL must be a postgresql:// connection string.')
    return url


def psycopg_url(url: str) -> str:
    return re.sub(r'^(postgres|postgresql\+psycopg)://', 'postgresql://', url)


def sqlalchemy_url(url: str) -> str:
    return 'postgresql+psycopg://' + psycopg_url(url).split('://', 1)[1]


def _checked_schema(schema):
    if schema is not None and not SCHEMA_NAME.match(schema):
        raise DatabaseConfigError('Database schema names must be lowercase identifiers.')
    return schema


class Database:
    """Owns the SQLAlchemy engine and, while open, the checkpointer pool.

    The engine connects lazily, so one instance can be opened and closed from
    successive event loops (for example a test client and a test coroutine).
    """

    def __init__(self, url: str, schema: str | None = None, pool_size: int = 5, checkpoint_pool_size: int = 3):
        self.url = psycopg_url(url)
        self.schema = _checked_schema(schema)
        self.checkpoint_pool_size = checkpoint_pool_size
        self.engine = create_async_engine(
            sqlalchemy_url(self.url), pool_size=pool_size, max_overflow=2,
            pool_pre_ping=True, pool_recycle=240)
        if self.schema:
            @event.listens_for(self.engine.sync_engine, 'connect')
            def _search_path(dbapi_connection, _record):
                cursor = dbapi_connection.cursor()
                cursor.execute(f'SET search_path TO "{self.schema}"')
                cursor.close()
                dbapi_connection.commit()
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.checkpoint_pool = None
        self.checkpointer = None

    @classmethod
    def from_env(cls, env=None):
        return cls(database_url(env))

    @asynccontextmanager
    async def session(self):
        async with self.sessions() as session:
            yield session

    @asynccontextmanager
    async def transaction(self):
        async with self.sessions() as session:
            async with session.begin():
                yield session

    async def open_checkpointer(self):
        """Open the psycopg pool LangGraph uses and return an AsyncPostgresSaver."""
        if self.checkpointer is not None:
            return self.checkpointer
        from psycopg.rows import dict_row
        from psycopg_pool import AsyncConnectionPool
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        schema = self.schema

        async def configure(connection):
            if schema:
                await connection.execute(f'SET search_path TO "{schema}"')

        self.checkpoint_pool = AsyncConnectionPool(
            self.url, min_size=1, max_size=self.checkpoint_pool_size, open=False,
            kwargs={'autocommit': True, 'row_factory': dict_row, 'prepare_threshold': 0},
            configure=configure, check=AsyncConnectionPool.check_connection)
        await self.checkpoint_pool.open(wait=True, timeout=30)
        self.checkpointer = AsyncPostgresSaver(self.checkpoint_pool)
        return self.checkpointer

    async def verify(self):
        """Fail fast when migrations have not been applied to this database."""
        from research_copilot.db.migrate import head_revision
        from langgraph.checkpoint.postgres.base import BasePostgresSaver

        instruction = 'Run `research-copilot-admin db upgrade`.'
        async with self.engine.connect() as connection:
            try:
                current = (await connection.execute(text('SELECT version_num FROM alembic_version'))).scalar()
                checkpoint = (await connection.execute(text('SELECT max(v) FROM checkpoint_migrations'))).scalar()
            except Exception as exc:
                raise DatabaseConfigError(f'The database schema is missing. {instruction}') from exc
        if current != head_revision():
            raise DatabaseConfigError(f'The database schema is out of date. {instruction}')
        if checkpoint != len(BasePostgresSaver.MIGRATIONS) - 1:
            raise DatabaseConfigError(f'Research checkpoint tables are out of date. {instruction}')

    async def close(self):
        if self.checkpoint_pool is not None:
            await self.checkpoint_pool.close()
        self.checkpoint_pool = None
        self.checkpointer = None
        await self.engine.dispose()
