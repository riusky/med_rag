# med_rag_server/web/api/document/views.py
import asyncio
from datetime import datetime
from enum import Enum
import json
from logging import getLogger
import logging
import traceback
from fastapi import APIRouter, BackgroundTasks, Form, HTTPException, Depends, Request, status, Path, UploadFile, File
from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel, Field
from med_rag_server.settings import settings
from med_rag_server.db.dao.document_dao import DocumentDAO
from med_rag_server.tasks import process_document_task
from med_rag_server.web.api.document.schema import (
    AsyncTaskResponse,
    DocumentDTO,
    DocumentInputDTO,
    DocumentUpdateDTO,
    ErrorResponse
)
import os
import uuid
from pathlib import Path as PathLib

from taskiq import AsyncBroker, TaskiqResult
from med_rag_server.tkq import broker
# from med_rag_server.tasks import process_document_task

router = APIRouter()
logger = logging.getLogger(__name__)

class MedicalQuery(BaseModel):
    question: str = Field(..., description="用户医疗设备的问题")
    kb_id: int = Field(..., description="要查询的知识库ID")
    language: str = "zh"
    require_references: bool = True
    safety_warnings: bool = True

class MedicalResponse(BaseModel):
    answer: str
    references: List[Dict]  # 仅保留必要字段
    timestamp: datetime
    search_metadata: Dict

MEDICAL_PROMPT_TEMPLATE = """
[角色设定]
您是认证的医疗设备专家，需严格依据医疗文档回答。

[知识片段]
{context}

[用户问题]
{question}

[回答规范]
1. 操作步骤用❶❷❸标记
2. 安全警示添加⚠️标识
3. 包含至少2个分点说明
4. 使用语言: {language} 回答
"""

from fastapi.responses import StreamingResponse
from langchain.callbacks import AsyncIteratorCallbackHandler


from langchain.callbacks import AsyncIteratorCallbackHandler
from fastapi.responses import StreamingResponse
import json

@router.post("/medical-search-stream")
async def medical_rag_search_stream(request: Request, query: MedicalQuery):
    """修正版流式医疗RAG接口"""
    try:
        qa_chain = request.app.state.qa_chains.get(query.kb_id)
        if not qa_chain:
            raise HTTPException(
                status_code=503,
                detail=f"知识库 {query.kb_id} 的问答系统未初始化"
            )

        callback = AsyncIteratorCallbackHandler()
        
        async def event_stream():
            try:
                # 异步任务包装（修正事件触发机制）
                async def wrap_done(future):
                    try:
                        await future
                    except Exception as e:
                        callback.done.set()
                    finally:
                        callback.done.set()

                task = asyncio.create_task(
                    qa_chain.acall(
                        {"query": query.question},
                        callbacks=[callback]
                    )
                )

                # 启动异步监控
                asyncio.create_task(wrap_done(task))

                # 流式传输（兼容Event机制）
                async for token in callback.aiter():
                    yield f"event: data\ndata: {json.dumps({'delta': token}, ensure_ascii=False)}\n\n"

                # 添加参考文献处理逻辑
                if task.done() and not task.exception():
                    result = task.result()
                    sources = [doc.metadata.get('source') for doc in result.get('source_documents', [])]
                    yield (
                        f"event: references\n"
                        f"data: {json.dumps({'sources': sources}, ensure_ascii=False)}\n\n"
                    )


            except HTTPException as he:
                yield f"event: error\ndata: {json.dumps({'error': he.detail}, ensure_ascii=False)}\n\n"
            except Exception as e:
                error_msg = f"数据流异常: {str(e)}"
                logger.error(f"{error_msg}\n{traceback.format_exc()}")
                yield f"event: error\ndata: {json.dumps({'error': error_msg}, ensure_ascii=False)}\n\n"
            finally:
                callback.done.set()

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "X-Stream-ID": f"kb{query.kb_id}-medical-rag",
                "X-KnowledgeBase-ID": str(query.kb_id)
            }
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.critical(f"接口严重错误: {str(e)}", exc_info=True)
        raise HTTPException(500, "系统处理失败") from e

class TaskStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    NOT_FOUND = "not_found"

@router.get("/task/{task_id}", response_model=dict)
async def get_task_status(
    task_id: str,
):
    """
    获取任务状态（增强版）
    :param task_id: 任务ID
    :return: 包含详细状态信息的响应
    """
    try:
        # 检查结果后端配置
        result_backend = broker.result_backend
        if not result_backend:
            raise HTTPException(
                status_code=501,
                detail="Result backend not configured"
            )

        # 获取任务结果
        task_result: TaskiqResult = await result_backend.get_result(task_id)
        
        # 处理任务不存在的情况
        if task_result is None:
            return {
                "task_id": task_id,
                "status": "not_found",
                "detail": "Task not found or expired"
            }

        # 构建响应数据
        response = {
            "task_id": task_id,
            "status": "success" if not task_result.is_err else "error",
            "execution_time": None,
            "result": None,
            "error": None
        }

        # 处理任务结果
        if task_result.is_err:
            response["error"] = str(task_result.error)
        else:
            response["result"] = task_result.return_value

        # 添加执行时间
        if task_result.execution_time:
            response["execution_time"] = f"{task_result.execution_time:.2f}s"

        return response

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

class FileStorageService:
    def __init__(self):
        self.storage_root = PathLib(settings.UPLOAD_ROOT)
    
    async def file_exists(self, relative_path: str) -> bool:
        """检查文件是否存在"""
        full_path = self.storage_root / relative_path
        return full_path.exists() and full_path.is_file()
    
    async def delete_file(self, relative_path: str):
        """删除指定文件"""
        full_path = self.storage_root / relative_path
        try:
            if await self.file_exists(relative_path):
                full_path.unlink()  # 仅删除文件
        except Exception as e:
            raise RuntimeError(f"文件删除失败: {str(e)}")

def ensure_upload_dir(kb_id: int) -> str:
    """确保上传目录存在"""
    upload_dir = PathLib(settings.UPLOAD_ROOT) / str(kb_id)
    try:
        upload_dir.mkdir(parents=True, exist_ok=True)
        return str(upload_dir)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Create upload directory failed: {str(e)}"
        )

def generate_unique_filename(original_name: str) -> str:
    """生成唯一文件名"""
    ext = original_name.split('.')[-1] if '.' in original_name else ''
    unique_id = uuid.uuid4().hex
    return f"{unique_id[:8]}_{unique_id[8:16]}.{ext}" if ext else unique_id

@router.post("/", response_model=DocumentDTO, status_code=status.HTTP_201_CREATED)
async def create_document(
    kb_id: int = Form(...),
    file_name: str = Form(...),
    chunk_method: str = Form("fixed"),
    file: UploadFile = File(...),
    chunk_params: Optional[str] = Form(None),  # JSON字符串
    dao: DocumentDAO = Depends(),
):
    """创建新文档（带文件上传）"""
    try:
        # 参数验证
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename cannot be empty")
        
        # 生成存储路径
        upload_dir = ensure_upload_dir(kb_id)
        unique_filename = generate_unique_filename(file.filename)
        save_path = PathLib(upload_dir) / unique_filename
        
        # 保存文件
        try:
            contents = await file.read()
            with open(save_path, 'wb') as f:
                f.write(contents)
        except IOError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"File save failed: {str(e)}"
            )
        finally:
            await file.close()

        # 解析chunk_params
        chunk_params_dict = {}
        if chunk_params:
            try:
                chunk_params_dict = json.loads(chunk_params)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid chunk_params format")

        return await dao.create_document(
            kb_id=kb_id,
            file_name=file_name,
            file_path=str(save_path.relative_to(settings.UPLOAD_ROOT)),  # 存储相对路径
            chunk_method=chunk_method,
            chunk_params=chunk_params_dict or {"chunk_size": 1500, "overlap": 150}
        )
    
    except HTTPException as he:
        # 如果已经保存文件但后续失败，清理文件
        if 'save_path' in locals() and save_path.exists():
            try:
                save_path.unlink()
            except OSError:
                pass
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/{doc_id}", response_model=DocumentDTO)
async def get_document(
    doc_id: int = Path(..., gt=0),
    dao: DocumentDAO = Depends(),
):
    """获取单个文档详情"""
    doc = await dao.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc

@router.get("/knowledge_base/{kb_id}", response_model=List[DocumentDTO])
async def get_documents_by_kb(
    kb_id: int = Path(..., gt=0),
    limit: int = 10,
    offset: int = 0,
    dao: DocumentDAO = Depends(),
):
    """根据知识库ID获取文档列表"""
    return await dao.get_documents_by_kb_id(kb_id, limit, offset)

@router.put("/{doc_id}", response_model=DocumentDTO)
async def update_document(
    doc_id: int = Path(..., gt=0),
    data: DocumentUpdateDTO = Depends(),
    dao: DocumentDAO = Depends(),
):
    """更新文档信息"""
    doc = await dao.update_document(doc_id, **data.model_dump(exclude_unset=True))
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc

# @router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
# async def delete_document(
#     doc_id: int = Path(..., gt=0),
#     dao: DocumentDAO = Depends(),
# ):
#     """删除文档"""
#     success = await dao.delete_document(doc_id)
#     if not success:
#         raise HTTPException(status_code=404, detail="Document not found")
#     return None

@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doc_id: int = Path(..., gt=0),
    dao: DocumentDAO = Depends(),
    file_storage: FileStorageService = Depends(),
):
    """删除文档及关联文件（保留目录）"""
    try:
        # 获取文档元数据
        document = await dao.get_document_by_id(doc_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # 检查文件是否存在
        if await file_storage.file_exists(document.file_path):
            # 文件存在时执行删除
            await file_storage.delete_file(document.file_path)

        # 无论文件是否存在都删除数据库记录
        success = await dao.delete_document(doc_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database deletion failed"
            )
            
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document deletion failed: {str(e)}"
        )
    
    return None
  
  
  
# @router.post("/{doc_id}/process", status_code=202)
# async def trigger_document_processing(
#     doc_id: int,
#     background: bool = False
# ):
#     """
#     触发文档处理
#     :param doc_id: 文档ID
#     :param background: 是否后台异步处理
#     """
#     # 验证文档存在
#     from med_rag_server.db.dao.document_dao import DocumentDAO
#     doc = await DocumentDAO().get_document(doc_id)
#     if not doc:
#         raise HTTPException(status_code=404, detail="Document not found")

#     if background:
#         # 发送到任务队列异步执行
#         task = await process_document_task.kiq(doc_id)
#         return {
#             "message": "Processing started in background",
#             "task_id": task.task_id
#         }
#     else:
#         # 同步处理（仅用于调试）
#         result = await process_document_task(doc_id)
#         return result