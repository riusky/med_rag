from importlib import metadata
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import UJSONResponse

from med_rag_server.log import configure_logging
from med_rag_server.web.api.router import api_router
from med_rag_server.web.lifespan import lifespan_setup
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

def get_app() -> FastAPI:
    """
    Get FastAPI application.

    This is the main constructor of an application.

    :return: application.
    """
    configure_logging()
    app = FastAPI(
        title="med_rag_server",
        version=metadata.version("med_rag_server"),
        lifespan=lifespan_setup,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        default_response_class=UJSONResponse,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 允许所有来源
        allow_credentials=True,
        allow_methods=["*"],  # 允许所有方法
        allow_headers=["*"],  # 允许所有头
    )
    
    
    
    # 获取项目根目录的绝对路径
    BASE_DIR = Path(__file__).resolve().parent.parent
    static_dir = BASE_DIR / "static"
    # 挂载静态文件目录
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    # Main router for the API.
    app.include_router(router=api_router, prefix="/api")

    return app
