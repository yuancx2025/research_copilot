"""Browser-bound local OAuth routes; state-changing endpoints require CSRF."""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from .security import session, verify_csrf


def oauth_router(service, frontend_url=''):
    router = APIRouter(prefix='/oauth/notion')

    @router.get('/status')
    async def status(request: Request):
        return JSONResponse({**service.status(), 'csrf': session(request)['csrf']}, headers={'Cache-Control':'no-store'})

    @router.post('/start')
    async def start(request: Request):
        data = verify_csrf(request)
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
        return RedirectResponse(f'{frontend_url}/oauth/done', status_code=303)

    @router.post('/disconnect')
    async def disconnect(request: Request):
        verify_csrf(request)
        try:
            await service.disconnect()
        except Exception:
            raise HTTPException(503, 'Connection stopped, but Keychain removal failed. Retry disconnect.') from None
        return {'status':'disconnected', 'message':'Local credentials removed; revoke provider access in Notion settings if desired.'}

    return router
