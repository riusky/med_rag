from contextlib import asynccontextmanager
from datetime import datetime
import logging
import os
from typing import AsyncGenerator

from fastapi import FastAPI
from langchain_ollama import OllamaEmbeddings, OllamaLLM
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from med_rag_server.db.meta import meta
from med_rag_server.db.models import load_all_models
from med_rag_server.settings import settings
from med_rag_server.tkq import broker
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from tenacity import stop_after_attempt, wait_exponential
from langchain.callbacks import AsyncIteratorCallbackHandler
logger = logging.getLogger(__name__)




async def _get_llm() -> OllamaLLM:
    async def _init_llm():
        return OllamaLLM(
            model='deepseek-r1:8b',
            base_url='http://host.docker.internal:11434',
            callbacks=[AsyncIteratorCallbackHandler()],
            streaming=True
        )
    
    return await _init_llm()

# async def _load_vectorstore(app: FastAPI) -> None:
#     """加载向量数据库到应用状态"""
#     vector_store_path = settings.VECTORSTORAGE_ROOT  # 确保settings包含该配置项
#     if not vector_store_path:
#         raise ValueError("VECTOR_STORE_PATH 未配置")

#     if os.path.exists(vector_store_path):
#         try:
#             logger.info(f"正在加载向量存储: {vector_store_path}")
#             app.state.vectorstore = FAISS.load_local(
#                 folder_path=vector_store_path,
#                 embeddings=get_embeddings(),
#                 allow_dangerous_deserialization=True
#             )
#             logger.info("向量存储加载成功")
#         except Exception as e:
#             logger.error(f"向量存储加载失败: {str(e)}")
#             raise RuntimeError(f"无法加载向量存储: {str(e)}") from e
#     else:
#         logger.warning(f"向量存储路径不存在: {vector_store_path}")
#         app.state.vectorstore = None  # 或初始化空存储

def _setup_db(app: FastAPI) -> None:  # pragma: no cover
    """
    Creates connection to the database.

    This function creates SQLAlchemy engine instance,
    session_factory for creating sessions
    and stores them in the application's state property.

    :param app: fastAPI application.
    """
    engine = create_async_engine(str(settings.db_url), echo=settings.db_echo)
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )
    app.state.db_engine = engine
    app.state.db_session_factory = session_factory


async def _create_tables() -> None:  # pragma: no cover
    """Populates tables in the database."""
    load_all_models()
    engine = create_async_engine(str(settings.db_url))
    async with engine.begin() as connection:
        await connection.run_sync(meta.create_all)
    await engine.dispose()


async def _init_llm_async(app: FastAPI):
    app.state.llm = await _get_llm()  # ✅ 添加await
    logger.info(f"LLM模型 {settings.MODELSNAME} 初始化完成")

@asynccontextmanager
async def lifespan_setup(
    app: FastAPI,
) -> AsyncGenerator[None, None]:  # pragma: no cover
    """
    Actions to run on application startup.

    This function uses fastAPI app to store data
    in the state, such as db_engine.

    :param app: the fastAPI application.
    :return: function that actually performs actions.
    """

    app.middleware_stack = None
    if not broker.is_worker_process:
        await broker.startup()
    # await _load_vectorstore(app)
    await _init_llm_async(app)
    
    # 初始化 QA Chains 字典
    app.state.qa_chains = {}
            
    _setup_db(app)
    await _create_tables()
    app.middleware_stack = app.build_middleware_stack()

    yield
    if not broker.is_worker_process:
        await broker.shutdown()
    await app.state.db_engine.dispose()
