from fastapi import HTTPException, Request


def get_research(request: Request):
    service = getattr(request.app.state, 'research', None)
    if service is None:
        raise HTTPException(503, 'Research service is not ready.')
    return service
