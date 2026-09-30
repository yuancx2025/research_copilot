import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query

from research_copilot.app.deps import get_research
from research_copilot.app.schemas import PageOut

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get('/notion/pages', response_model=List[PageOut])
async def search_pages(q: str = Query('', max_length=200), service=Depends(get_research)):
    if not service.notion:
        raise HTTPException(404, 'Page search needs a Notion OAuth connection.')
    try:
        return await service.search_destinations(q)
    except Exception:
        logger.exception('Notion page search failed')
        raise HTTPException(502, 'Could not search destinations. Check your Notion connection.') from None
