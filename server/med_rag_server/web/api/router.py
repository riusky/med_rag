from fastapi.routing import APIRouter

from med_rag_server.web.api import dummy, echo, monitoring, knowledge_base, document

api_router = APIRouter()
api_router.include_router(monitoring.router)
api_router.include_router(echo.router, prefix="/echo", tags=["echo"])
api_router.include_router(dummy.router, prefix="/dummy", tags=["dummy"])
api_router.include_router(knowledge_base.router, prefix="/knowledge-bases", tags=["Knowledge Bases"])
api_router.include_router(document.router, prefix="/document", tags=["Knowledge Document"])
