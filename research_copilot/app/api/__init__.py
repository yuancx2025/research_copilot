from fastapi import APIRouter
from . import config, conversations, documents, notion, runs, study_plan


def api_router():
    router = APIRouter(prefix='/api')
    for module in (config, documents, conversations, runs, study_plan, notion):
        router.include_router(module.router)
    return router
