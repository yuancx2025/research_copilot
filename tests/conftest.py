"""
Pytest configuration and fixtures
"""
import asyncio
import os
import uuid
import pytest
import pytest_asyncio
import sys
from pathlib import Path

# Add project root and package root so both
# `research_copilot.foo` and legacy `rag.foo` / `config` imports work.
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "research_copilot"))

POSTGRES_FIXTURES = {"pg_schema", "db", "adb"}
TRUNCATED_TABLES = (
    "run_events", "exports", "study_plan_drafts", "messages", "research_runs", "conversations",
    "mcp_connections", "checkpoint_writes", "checkpoint_blobs", "checkpoints",
)


def pytest_collection_modifyitems(config, items):
    for item in items:
        if POSTGRES_FIXTURES & set(getattr(item, "fixturenames", ())):
            item.add_marker(pytest.mark.postgres)


def _test_database_url():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        from dotenv import dotenv_values
        url = dotenv_values(project_root / ".env").get("TEST_DATABASE_URL")
    return url


@pytest.fixture(scope="session")
def pg_schema():
    """A throwaway schema on the dedicated Neon test branch, migrated once per session."""
    url = _test_database_url()
    if not url:
        pytest.fail("TEST_DATABASE_URL is not set. Point it at the Neon test branch's direct endpoint "
                    "(see README), or deselect these tests with -m 'not postgres'.", pytrace=False)
    import psycopg
    from research_copilot.db.migrate import upgrade
    schema = "test_" + uuid.uuid4().hex[:12]
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(f'CREATE SCHEMA "{schema}"')
    try:
        upgrade(url, schema)
        yield url, schema
    finally:
        with psycopg.connect(url, autocommit=True) as conn:
            conn.execute(f'DROP SCHEMA "{schema}" CASCADE')


@pytest.fixture
def db(pg_schema):
    import psycopg
    from research_copilot.db.engine import Database
    url, schema = pg_schema
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(f'SET search_path TO "{schema}"')
        conn.execute("TRUNCATE " + ", ".join(TRUNCATED_TABLES) + " RESTART IDENTITY CASCADE")
    database = Database(url, schema, pool_size=2, checkpoint_pool_size=2)
    yield database
    try:
        asyncio.run(database.close())
    except Exception:
        pass


@pytest_asyncio.fixture
async def adb(db):
    """The same database, closed on the test's own event loop."""
    yield db
    await db.close()


@pytest.fixture
def mock_config():
    """Create a mock config object"""
    from unittest.mock import Mock
    config = Mock()
    
    # Set default config values
    config.ENABLE_ARXIV_AGENT = True
    config.ENABLE_YOUTUBE_AGENT = True
    config.ENABLE_GITHUB_AGENT = True
    config.ENABLE_WEB_AGENT = True
    config.MAX_ARXIV_RESULTS = 10
    config.MAX_WEB_RESULTS = 10
    config.YOUTUBE_API_KEY = None
    config.GITHUB_TOKEN = None
    config.TAVILY_API_KEY = None
    config.USE_GITHUB_MCP = False
    config.USE_WEB_SEARCH_MCP = False
    
    return config


@pytest.fixture
def mock_collection():
    """Create a mock vector store collection"""
    from unittest.mock import MagicMock
    
    mock_doc = MagicMock()
    mock_doc.page_content = "Test document content"
    mock_doc.metadata = {
        "parent_id": "parent_1",
        "source": "test.pdf"
    }
    
    collection = MagicMock()
    collection.similarity_search.return_value = [mock_doc]
    
    return collection

