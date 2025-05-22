# med_rag_server/db/dao/document_dao.py
from typing import List, Optional, Dict
from fastapi import Depends, HTTPException
from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from med_rag_server.db.dependencies import get_db_session
from med_rag_server.db.models.document_model import DocumentModel
from med_rag_server.db.dao.knowledge_base_dao import KnowledgeBaseDAO


from med_rag_server.db.dependencies import get_db_session
from med_rag_server.db.models.document_model import DocumentModel
from med_rag_server.db.dao.knowledge_base_dao import KnowledgeBaseDAO

class DocumentDAO:
    """文档数据访问对象"""
    def __init__(self, session: AsyncSession = Depends(get_db_session)) -> None:
        self.session = session

    async def create_document(
        self,
        kb_id: int,
        file_name: str,
        file_path: str,
        chunk_method: str = "fixed",
        chunk_params: Optional[Dict] = None,
    ) -> DocumentModel:
        """创建文档"""
        async with self.session.begin():
            # 检查知识库是否存在
            kb = await KnowledgeBaseDAO(self.session).get_kb_by_id(kb_id)
            if not kb:
                raise HTTPException(status_code=404, detail="Knowledge base not found")

            # 检查文件路径是否唯一
            existing = await self.session.execute(
                select(DocumentModel).where(DocumentModel.file_path == file_path)
            )
            if existing.scalars().first():
                raise HTTPException(status_code=400, detail="File path already exists")

            doc = DocumentModel(
                kb_id=kb_id,
                file_name=file_name,
                file_path=file_path,
                chunk_method=chunk_method,
                chunk_params=chunk_params or {"chunk_size": 1500, "overlap": 150},
            )
            self.session.add(doc)
            await self.session.flush()
            return doc

    async def get_document_by_id(self, doc_id: int) -> Optional[DocumentModel]:
        """根据ID获取文档"""
        result = await self.session.execute(
            select(DocumentModel).where(DocumentModel.id == doc_id)
        )
        return result.scalars().first()

    async def get_documents_by_kb_id(
        self, 
        kb_id: int,
        limit: int = 10,
        offset: int = 0,
        active_only: bool = True
    ) -> List[DocumentModel]:
        """根据知识库ID获取文档（分页）"""
        query = select(DocumentModel).where(DocumentModel.kb_id == kb_id)
        if active_only:
            query = query.where(DocumentModel.is_active == True)
        
        result = await self.session.execute(
            query.order_by(DocumentModel.upload_time.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def update_document(
        self,
        doc_id: int,
        file_name: Optional[str] = None,
        chunk_method: Optional[str] = None,
        chunk_params: Optional[Dict] = None,
        parsing_status: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Optional[DocumentModel]:
        """更新文档信息"""
        doc = await self.get_document_by_id(doc_id)
        if not doc:
            return None

        update_data = {}
        if file_name is not None:
            update_data["file_name"] = file_name
        if chunk_method is not None:
            update_data["chunk_method"] = chunk_method
        if chunk_params is not None:
            update_data["chunk_params"] = chunk_params
        if parsing_status is not None:
            update_data["parsing_status"] = parsing_status
        if is_active is not None:
            update_data["is_active"] = is_active

        try:
            await self.session.execute(
                update(DocumentModel)
                .where(DocumentModel.id == doc_id)
                .values(**update_data)
            )
            await self.session.commit()
            await self.session.refresh(doc)
        except Exception:
            await self.session.rollback()
            raise

        return doc

    async def delete_document(self, doc_id: int) -> bool:
        """删除文档（移除外层事务管理）"""
        try:
            doc = await self.get_document_by_id(doc_id)
            if not doc:
                return False

            # 删除文档记录
            await self.session.delete(doc)
            
            # 显式刷新并提交（由调用方控制事务）
            await self.session.flush()  # 生成SQL但不提交
            return True

        except Exception as e:
            await self.session.rollback()
            raise RuntimeError(f"删除操作失败: {str(e)}") from e