"""Serve the built React app with an index.html fallback for client routes."""
import os
from pathlib import Path
from fastapi import HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

DEFAULT_DIST = Path(__file__).resolve().parents[2] / 'frontend' / 'dist'

NOT_BUILT = '''<!doctype html><html><body style="font:14px system-ui;background:#0a0a0a;color:#f5f5f5;padding:2rem">
<h1>Research Copilot</h1>
<p>The frontend has not been built. Run <code>npm install &amp;&amp; npm run build</code> in <code>frontend/</code>,
or start the dev server with <code>npm run dev</code> and open <code>http://127.0.0.1:5173</code>.</p>
</body></html>'''


def frontend_dist(directory=None) -> Path:
    return Path(directory or os.getenv('RESEARCH_COPILOT_FRONTEND_DIR') or DEFAULT_DIST).resolve()


def mount_frontend(app, directory=None):
    root = frontend_dist(directory)
    index = root / 'index.html'
    if (root / 'assets').is_dir():
        app.mount('/assets', StaticFiles(directory=root / 'assets'), name='assets')

    @app.get('/{path:path}', include_in_schema=False)
    async def spa(path: str):
        if path.split('/', 1)[0] in ('api', 'assets') or path.startswith('oauth/notion'):
            raise HTTPException(404)
        candidate = (root / path).resolve()
        if path and candidate.is_file() and root in candidate.parents:
            return FileResponse(candidate)
        if index.is_file():
            return FileResponse(index, headers={'Cache-Control': 'no-cache'})
        return HTMLResponse(NOT_BUILT, status_code=503)
