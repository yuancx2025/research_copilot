"""Canonical local/legacy REST application entrypoint."""
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware


def create_app(config=None, connection=None, ui_factory=None, mount_ui=True):
    if config is None:
        from research_copilot.config import settings as config
    backend = getattr(config, 'NOTION_BACKEND', 'disabled')
    local = backend == 'mcp'
    base = getattr(config, 'OAUTH_BASE_URL', 'http://127.0.0.1:7860')
    parts = urlsplit(base)
    if local and (parts.scheme != 'http' or parts.hostname != '127.0.0.1' or parts.path not in ('', '/') or parts.query or parts.fragment or parts.username or parts.password):
        raise ValueError('Local MCP OAuth requires OAUTH_BASE_URL=http://127.0.0.1:<port>')
    from research_copilot.tools.mcp.oauth import ConnectionService
    from research_copilot.notion.notion_mcp_service import NotionMCPService
    from research_copilot.storage.export_store import ExportStore
    from research_copilot.notion.export_service import ExportService
    from .oauth_routes import oauth_router
    if local:
        connection = connection or ConnectionService(base_url=base, timeout=getattr(config, 'OAUTH_TIMEOUT', 300))
        notion = NotionMCPService(connection)
    else:
        connection, notion = None, None
    data_dir = Path(os.getenv('RESEARCH_COPILOT_DATA_DIR', str(Path.home() / '.local/share/research-copilot')))
    exporter = ExportService(ExportStore(data_dir / 'exports.sqlite3'), notion, config)

    @asynccontextmanager
    async def lifespan(app):
        if connection:
            await connection.initialize()
        yield
        if connection:
            await connection.close()

    app = FastAPI(lifespan=lifespan)
    app.state.connection = connection
    app.state.notion = notion
    app.state.exporter = exporter
    if local:
        app.add_middleware(SessionMiddleware, secret_key=secrets.token_urlsafe(48),
                           same_site='lax', session_cookie='research_copilot_session')
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1'])

        @app.middleware('http')
        async def local_origin(request: Request, call_next):
            origin = request.headers.get('origin')
            cross_site = request.headers.get('sec-fetch-site') == 'cross-site'
            if request.method not in ('GET', 'HEAD', 'OPTIONS') and (cross_site or (origin and origin != base)):
                return JSONResponse({'detail':'Cross-origin writes are not allowed'}, status_code=403)
            return await call_next(request)

        app.include_router(oauth_router(connection))

    @app.get('/')
    async def root():
        return RedirectResponse('/ui')

    if not mount_ui:
        return app
    if ui_factory is None:
        from research_copilot.ui.gradio_app import create_gradio_ui
        ui_factory = create_gradio_ui
    demo = ui_factory(notion_service=notion, export_service=exporter)
    import gradio as gr
    return gr.mount_gradio_app(app, demo, path='/ui')


def main():
    from dotenv import load_dotenv
    load_dotenv()
    from research_copilot.config import settings as config
    import uvicorn
    local = config.NOTION_BACKEND == 'mcp'
    port = (urlsplit(config.OAUTH_BASE_URL).port or 7860) if local else int(os.getenv('GRADIO_SERVER_PORT', '7860'))
    uvicorn.run(create_app(config), host='127.0.0.1' if local else os.getenv('GRADIO_SERVER_NAME', '0.0.0.0'),
                port=port, workers=1, access_log=False)


if __name__ == '__main__':
    main()
