# med_rag_server/db/dao/knowledge_base_dao.py
from datetime import datetime
from typing import List, Optional
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from med_rag_server.db.dependencies import get_db_session
from med_rag_server.db.models.knowledge_base_model import KnowledgeBaseModel

class KnowledgeBaseDAO:
    """知识库数据访问对象"""
    def __init__(self, session: AsyncSession = Depends(get_db_session)) -> None:
        self.session = session

    async def create_kb(
        self, 
        name: str,
        description: Optional[str] = None
    ) -> KnowledgeBaseModel:
        """创建知识库（自动生成向量路径）"""
        async with self.session.begin():
            # 生成唯一向量路径（示例逻辑）

            
            kb = KnowledgeBaseModel(
                name=name,
                description=description,
                processing_status="pending"
            )
            self.session.add(kb)
            await self.session.flush()
            return kb

    async def update_processing_info(
        self,
        kb_id: int,
        processing_status: str,
    ) -> Optional[KnowledgeBaseModel]:
        """更新处理状态"""
        kb = await self.get_kb_by_id(kb_id)
        if not kb:
            return None

        # 更新状态
        kb.processing_status = processing_status

        try:
            self.session.add(kb)
            await self.session.commit()
            await self.session.refresh(kb)
        except Exception:
            await self.session.rollback()
            raise
        
        return kb

    async def update_vector_path(
        self,
        kb_id: int,
        vector_path: str
    ) -> Optional[KnowledgeBaseModel]:
        """更新向量存储路径"""
        kb = await self.get_kb_by_id(kb_id)
        if not kb:
            return None

        kb.vector_storage_path = vector_path
        try:
            self.session.add(kb)
            await self.session.commit()
            await self.session.refresh(kb)
        except Exception:
            await self.session.rollback()
            raise
        
        return kb

    async def get_all_kbs(self, limit: int = 10, offset: int = 0) -> List[KnowledgeBaseModel]:
        """获取所有知识库（分页）"""
        result = await self.session.execute(
            select(KnowledgeBaseModel)
            .order_by(KnowledgeBaseModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_kb_by_id(self, kb_id: int) -> Optional[KnowledgeBaseModel]:
        """根据ID获取知识库"""
        result = await self.session.execute(
            select(KnowledgeBaseModel)
            .where(KnowledgeBaseModel.id == kb_id)
        )
        # 使用 scalars().first() 会自动关闭结果集
        return result.scalars().first()

    async def update_kb(
        self,
        kb_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> Optional[KnowledgeBaseModel]:
        """更新知识库信息"""
        kb = await self.get_kb_by_id(kb_id)
        if not kb:
            return None

        if name is not None:
            kb.name = name
        if description is not None:
            kb.description = description

        try:
            # 使用显式提交代替事务块
            self.session.add(kb)
            await self.session.commit()
            await self.session.refresh(kb)
        except Exception:
            await self.session.rollback()
            raise
        
        return kb

    async def delete_kb(self, kb_id: int) -> bool:
        """删除知识库"""
        kb = await self.get_kb_by_id(kb_id)
        if not kb:
            return False

        async with self.session.begin_nested():
            await self.session.delete(kb)
            await self.session.commit()
        return True