import asyncio
from datetime import datetime
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List

from med_rag_server.settings import settings
from med_rag_server.db.dao.knowledge_base_dao import KnowledgeBaseDAO
from med_rag_server.db.models.document_model import DocumentModel
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from taskiq import TaskiqDepends

from med_rag_server.db.dao.document_dao import DocumentDAO
from med_rag_server.db.dependencies import get_takiq_db_session
from .tkq import broker


@broker.task
async def process_document_task(kb_id: int) -> dict:
    """重构后的健壮型文档处理任务（支持嵌入生成）"""
    async with get_takiq_db_session() as session:
        kb_dao = KnowledgeBaseDAO(session)
        doc_dao = DocumentDAO(session)
        
        try:
            # 阶段0: 验证知识库存在性
            if not await kb_dao.get_kb_by_id(kb_id):
                logger.error(f"知识库不存在 kb_id={kb_id}")
                raise ValueError(f"Knowledge base {kb_id} not found")

            # 获取知识库下所有有效文档
            documents = await doc_dao.get_documents_by_kb_id(
                kb_id=kb_id,
                active_only=True
            )

            # 阶段1: 批量更新文档状态
            update_tasks = [
                _update_document_status(doc_dao, doc.id, "processing")
                for doc in documents
            ]
            await asyncio.gather(*update_tasks)

            # 阶段2: 并行处理文档
            config = {
                "models": {
                    "name": "bge-m3:latest",
                    "base_url": "http://host.docker.internal:11434"
                },
                "vector_store": {
                    "base_path": Path(settings.VECTORSTORAGE_ROOT),
                    "naming_template": "vec_{model_hash}_{doc_hash}"
                }
            }
            upload_dir = Path(settings.UPLOAD_ROOT) / str(kb_id)
            
            # 创建处理任务列表
            processing_tasks = [
                _process_document_with_retry(
                    doc=doc,
                    file_path=upload_dir / doc.file_path,
                    config=config,
                    doc_dao=doc_dao
                )
                for doc in documents
            ]

            # 并行执行并收集结果
            results = await asyncio.gather(
                *processing_tasks,
                return_exceptions=True
            )

            # 统计处理结果
            success_count = sum(1 for res in results if res is True)
            failed_count = len(results) - success_count

            logger.success(f"知识库处理完成 kb_id={kb_id}，成功：{success_count} 失败：{failed_count}")
            return {
                "kb_id": kb_id,
                "total": len(documents),
                "success": success_count,
                "failed": failed_count,
                "processed_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"任务处理异常: {str(e)}")
            raise

async def _process_document_with_retry(
    doc: DocumentModel,
    file_path: Path,
    config: Dict,
    doc_dao: DocumentDAO,
    max_retries: int = 3
) -> bool:
    """带重试机制的文档处理"""
    for attempt in range(1, max_retries+1):
        try:
            # 验证文件存在性
            if not file_path.exists():
                raise FileNotFoundError(f"文件不存在: {file_path}")
                
            # 执行异步处理
            manager = await async_process_document(file_path, config)
            
            if not manager or not manager.is_ready:
                raise RuntimeError("向量存储失败")

            # 更新成功状态
            await _update_document_status(
                doc_dao=doc_dao,
                doc_id=doc.id,
                status="completed",
                vector_store_path=str(manager.base_path),
                processing_attempts=attempt
            )
            return True
            
        except Exception as e:
            error_msg = f"文档处理失败（尝试 {attempt}/{max_retries}）: {str(e)}"
            logger.warning(error_msg)
            
            # 更新错误状态
            await _update_document_status(
                doc_dao=doc_dao,
                doc_id=doc.id,
                status="failed" if attempt == max_retries else "retrying",
                error_log=error_msg,
                processing_attempts=attempt
            )
            
            if attempt == max_retries:
                return False
            await asyncio.sleep(2 ** attempt)  # 指数退避

    return False

async def _update_document_status(
    dao: DocumentDAO,
    doc_id: int,
    status: str,
    **kwargs: Any
) -> None:
    """带重试机制的文档状态更新"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            await dao.update_document(
                doc_id=doc_id,
                parsing_status=status,
                **kwargs
            )
            logger.debug(f"状态更新成功 doc_id={doc_id} => {status}")
            
            # 具体的文档处理逻辑
            
            
            
            
            
            return
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"最终更新失败 doc_id={doc_id}: {str(e)}")
                raise
            logger.warning(f"状态更新重试（{attempt+1}/{max_retries}）: {str(e)}")
            await asyncio.sleep(2 ** attempt)
            

    
    
async def async_process_document(file_path: Path, config: Dict):
    """异步包装同步处理函数"""
    try:
        pass
    except Exception as e:
        logger.error(f"文档处理失败: {file_path} | {str(e)}")
        raise