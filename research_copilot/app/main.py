"""Canonical application entrypoint: JSON/SSE API, local OAuth routes, and the React app."""
import logging
import os
from contextlib import asynccontextmanager
from urllib.parse import urlsplit
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from .security import install_security, validate_loopback_url

logger = logging.getLogger(__name__)


def create_app(config=None, connection=None, research_factory=None, frontend_dir=None, database=None):
    """Build the app. PostgreSQL (``DATABASE_URL`` or ``database``) is required in every mode."""
    if config is None:
        from research_copilot.config import settings as config
    backend = getattr(config, 'NOTION_BACKEND', 'disabled')
    local = backend == 'mcp'
    base = getattr(config, 'OAUTH_BASE_URL', 'http://127.0.0.1:7860')
    frontend_url = (getattr(config, 'FRONTEND_URL', '') or '').rstrip('/')
    if local:
        try:
            validate_loopback_url(base, 'OAUTH_BASE_URL')
        except ValueError:
            raise ValueError('Local MCP OAuth requires OAUTH_BASE_URL=http://127.0.0.1:<port>') from None
        if frontend_url:
            validate_loopback_url(frontend_url, 'FRONTEND_URL')
    from research_copilot.db.engine import Database
    from research_copilot.db.repositories import ResearchRepository
    from research_copilot.runtime.auth.connection import ConnectionService
    from research_copilot.sources.notion.oauth import NotionAuthProvider
    from research_copilot.sources.notion.mcp_service import NotionMCPService
    from research_copilot.storage.credential_store import PostgresCredentialStore
    from research_copilot.storage.export_store import PostgresExportLedger, STALE_UNKNOWN
    from research_copilot.sources.notion.exporter import ExportService
    from .oauth_routes import oauth_router
    from .api import api_router
    from .static import mount_frontend
    db = database or Database.from_env()
    if local:
        connection = connection or ConnectionService(
            NotionAuthProvider(), PostgresCredentialStore(db), base_url=base,
            timeout=getattr(config, 'OAUTH_TIMEOUT', 300))
        notion = NotionMCPService(connection)
    else:
        connection, notion = None, None
    exporter = ExportService(PostgresExportLedger(db), notion, config)
    repo = ResearchRepository(db)
    if research_factory is None:
        from research_copilot.core.research_service import build_research_service
        research_factory = build_research_service

    @asynccontextmanager
    async def lifespan(app):
        try:
            await db.verify()
            checkpointer = await db.open_checkpointer()
            interrupted = await repo.interrupt_unfinished()
            expired = await repo.expire_pending_exports(STALE_UNKNOWN.message)
            if interrupted or expired:
                logger.info('Startup marked %d run(s) interrupted and %d export(s) unknown',
                            len(interrupted), expired)
            if connection:
                await connection.initialize()
            app.state.research = research_factory(config=config, notion=notion, exporter=exporter,
                                                  repo=repo, checkpointer=checkpointer)
            yield
        finally:
            if app.state.research is not None:
                await app.state.research.shutdown()
            if connection:
                await connection.close()
            await db.close()

    app = FastAPI(title='Research Copilot', lifespan=lifespan)
    app.state.config = config
    app.state.db = db
    app.state.local = local
    app.state.connection = connection
    app.state.notion = notion
    app.state.exporter = exporter
    app.state.research = None
    install_security(app, local, base)

    if local:
        app.include_router(oauth_router(connection, frontend_url))
    app.include_router(api_router())
    from .contracts import install_contracts
    install_contracts(app)

    @app.get('/ui', include_in_schema=False)
    async def legacy_ui():
        return RedirectResponse('/')

    mount_frontend(app, frontend_dir)
    return app


def main():
    from dotenv import load_dotenv
    load_dotenv()
    from research_copilot.config import settings as config
    import uvicorn
    local = config.NOTION_BACKEND == 'mcp'
    if local:
        host, port = '127.0.0.1', urlsplit(config.OAUTH_BASE_URL).port or 7860
    else:
        host = os.getenv('SERVER_HOST') or os.getenv('GRADIO_SERVER_NAME', '0.0.0.0')
        port = int(os.getenv('PORT') or os.getenv('SERVER_PORT') or os.getenv('GRADIO_SERVER_PORT', '7860'))
    uvicorn.run(create_app(config), host=host, port=port, workers=1, access_log=False)


if __name__ == '__main__':
    main()
