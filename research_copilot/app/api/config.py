from fastapi import APIRouter, Depends, Request, Response
from research_copilot.app.deps import get_research
from research_copilot.app.schemas import ConfigOut
from research_copilot.app.security import csrf_token

router = APIRouter()


@router.get('/health')
async def health():
    return {'status': 'ok'}


@router.get('/config', response_model=ConfigOut)
async def app_config(request: Request, response: Response, service=Depends(get_research)):
    response.headers['Cache-Control'] = 'no-store'
    config = request.app.state.config
    return ConfigOut(
        notion_backend=service.notion_backend,
        default_destination=getattr(config, 'NOTION_PARENT_PAGE_ID', '') or '',
        sources=service.available_sources(),
        csrf=csrf_token(request),
    )
