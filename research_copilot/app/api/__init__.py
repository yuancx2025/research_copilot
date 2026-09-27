from fastapi import APIRouter
from . import config, documents, notion, research, study_plan


def api_router():
    router = APIRouter(prefix='/api')
    for module in (config, documents, research, study_plan, notion):
        router.include_router(module.router)
    return router
