"""Browser-bound local OAuth routes; state-changing endpoints require CSRF."""
import secrets
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

PANEL = '''<!doctype html><html><body style="font:14px system-ui;color:#ddd;background:#141414">
<button id="connect">Connect Notion</button> <button id="disconnect">Disconnect</button>
<span id="status">Loading connection…</span>
<script>
let csrf;
async function status() {
  const r = await fetch('/oauth/notion/status'); const s = await r.json(); csrf = s.csrf;
  document.getElementById('status').textContent = s.status + (s.workspace ? ': ' + s.workspace : '') + (s.error ? ' — ' + s.error : '');
}
document.getElementById('connect').onclick = async () => {
  const tab = window.open('about:blank', '_blank');
  try {
    await status();
    const r = await fetch('/oauth/notion/start', {method:'POST', headers:{'X-CSRF-Token':csrf}});
    const data = await r.json(); if (!r.ok) throw new Error(data.detail);
    if (tab) tab.location.href = data.authorization_url; else window.location.href = data.authorization_url;
  } catch(e) { if(tab) tab.close(); document.getElementById('status').textContent = e.message; }
};
document.getElementById('disconnect').onclick = async () => {
  await status();
  const r = await fetch('/oauth/notion/disconnect', {method:'POST',headers:{'X-CSRF-Token':csrf}});
  if(r.ok) window.parent.location.reload(); else document.getElementById('status').textContent = 'Could not remove connection. Check Keychain.';
};
status(); setInterval(status, 2000);
</script></body></html>'''


def oauth_router(service):
    router = APIRouter(prefix='/oauth/notion')

    def session(request):
        request.session.setdefault('id', secrets.token_urlsafe(32))
        request.session.setdefault('csrf', secrets.token_urlsafe(32))
        return request.session

    def verify(request):
        data = session(request)
        token = request.headers.get('x-csrf-token', '')
        if not token or not secrets.compare_digest(token, data['csrf']):
            raise HTTPException(403, 'Invalid CSRF token')
        return data

    @router.get('/panel', response_class=HTMLResponse)
    async def panel(request: Request):
        session(request)
        return HTMLResponse(PANEL, headers={'Cache-Control':'no-store', 'X-Frame-Options':'SAMEORIGIN'})

    @router.get('/status')
    async def status(request: Request):
        return JSONResponse({**service.status(), 'csrf': session(request)['csrf']}, headers={'Cache-Control':'no-store'})

    @router.post('/start')
    async def start(request: Request):
        data = verify(request)
        try:
            return {'authorization_url': await service.start(data['id'])}
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None
        except Exception:
            raise HTTPException(503, 'Could not start authorization. Check Keychain and your network.') from None

    @router.get('/callback')
    async def callback(request: Request, code: str = '', state: str = '', error: str = ''):
        try:
            await service.complete(session(request)['id'], code, state, error)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        except Exception:
            raise HTTPException(400, 'Authorization was denied, expired, or could not be completed.') from None
        return RedirectResponse('/ui', status_code=303)

    @router.post('/disconnect')
    async def disconnect(request: Request):
        verify(request)
        try:
            await service.disconnect()
        except Exception:
            raise HTTPException(503, 'Connection stopped, but Keychain removal failed. Retry disconnect.') from None
        return {'status':'disconnected', 'message':'Local credentials removed; revoke provider access in Notion settings if desired.'}

    return router
