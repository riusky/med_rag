# med_rag_server/web/api/document/schema.py
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, validator
from typing import Optional, Dict

class DocumentDTO(BaseModel):
    """文档返回数据结构"""
    id: int
    kb_id: int
    file_name: str
    file_path: str
    chunk_method: str
    chunk_params: Dict
    upload_time: str
    parsing_status: str
    is_active: bool

    @validator('upload_time', pre=True)
    def format_upload_time(cls, value):
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return value

    class Config:
        from_attributes = True
        populate_by_name = True

class DocumentInputDTO(BaseModel):
    """创建文档请求结构"""
    kb_id: int
    file_name: str
    file_path: str
    chunk_method: Optional[str] = "fixed"
    chunk_params: Optional[Dict] = Field(
        default_factory=lambda: {"chunk_size": 1500, "overlap": 150}
    )

class DocumentUpdateDTO(BaseModel):
    """更新文档请求结构"""
    file_name: Optional[str] = None
    chunk_method: Optional[str] = None
    chunk_params: Optional[Dict] = None
    parsing_status: Optional[str] = None
    is_active: Optional[bool] = None

    @validator('parsing_status')
    def validate_status(cls, v):
        valid_statuses = {"pending", "processing", "completed", "failed"}
        if v and v not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of {valid_statuses}")
        return v
      
      
class AsyncTaskResponse(BaseModel):
    task_id: str
    status_url: str
    monitor_url: Optional[str]

class ErrorResponse(BaseModel):
    code: str
    message: str
    detail: Optional[dict]