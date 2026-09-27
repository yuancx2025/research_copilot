"""Request checks shared by OAuth and API routes.

Local OAuth mode binds to 127.0.0.1, only accepts writes from OAUTH_BASE_URL, and
requires a session-bound CSRF token. Other modes still reject cross-site writes.
"""
import secrets
from urllib.parse import urlsplit
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS')


def validate_loopback_url(url, name):
    parts = urlsplit(url)
    if (parts.scheme != 'http' or parts.hostname != '127.0.0.1' or parts.path not in ('', '/')
            or parts.query or parts.fragment or parts.username or parts.password):
        raise ValueError(f'{name} must be http://127.0.0.1:<port>')


def session(request: Request):
    request.session.setdefault('id', secrets.token_urlsafe(32))
    request.session.setdefault('csrf', secrets.token_urlsafe(32))
    return request.session


def verify_csrf(request: Request):
    data = session(request)
    token = request.headers.get('x-csrf-token', '')
    if not token or not secrets.compare_digest(token, data['csrf']):
        raise HTTPException(403, 'Invalid CSRF token')
    return data


def csrf_token(request: Request):
    return session(request)['csrf'] if request.app.state.local else None


async def require_csrf(request: Request):
    if request.app.state.local:
        verify_csrf(request)


def install_security(app, local, base):
    if local:
        from starlette.middleware.sessions import SessionMiddleware
        app.add_middleware(SessionMiddleware, secret_key=secrets.token_urlsafe(48),
                           same_site='lax', session_cookie='research_copilot_session')
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1'])

    @app.middleware('http')
    async def same_origin_writes(request: Request, call_next):
        if request.method not in SAFE_METHODS:
            origin = request.headers.get('origin')
            cross_site = request.headers.get('sec-fetch-site') == 'cross-site'
            if local:
                foreign = bool(origin) and origin != base
            else:
                foreign = bool(origin) and urlsplit(origin).netloc != request.headers.get('host', '')
            if cross_site or foreign:
                return JSONResponse({'detail': 'Cross-origin writes are not allowed'}, status_code=403)
        return await call_next(request)
