from contextlib import asynccontextmanager
from typing import AsyncGenerator, Type, TypeVar

from med_rag_server.settings import settings
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from taskiq import TaskiqDepends
from sqlalchemy.ext.asyncio import create_async_engine

async def get_db_session(
    request: Request = TaskiqDepends(),
) -> AsyncGenerator[AsyncSession, None]:
    """
    Create and get database session.

    :param request: current request.
    :yield: database session.
    """
    session: AsyncSession = request.app.state.db_session_factory()

    try:
        yield session
    finally:
        await session.commit()
        await session.close()
        
@asynccontextmanager
async def get_takiq_db_session() -> AsyncGenerator[AsyncSession, None]:
    """异步上下文管理器获取数据库会话"""
    engine = create_async_engine(str(settings.db_url), echo=settings.db_echo)
    session = AsyncSession(bind=engine)  # 替换为你的实际 engine 实例
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()