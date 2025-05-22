from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional

class KnowledgeBaseDTO(BaseModel):
    """知识库响应结构"""
    id: int
    name: str
    description: Optional[str] = None
    vectorStoragePath: Optional[str] = Field(  # 改为可选字段
        None,
        alias="vector_storage_path"
    )
    processingStatus: str = Field(alias="processing_status")
    createdAt: datetime = Field(alias="created_at")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )

class KnowledgeBaseUpdateDTO(BaseModel):
    """知识库更新请求结构"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)

class KnowledgeBaseInputDTO(BaseModel):
    """知识库创建请求结构"""
    name: str = Field(..., min_length=1, max_length=200, example="临床指南库")
    description: Optional[str] = Field(
        None,
        max_length=500,
        example="包含最新临床实践指南的知识库"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "心血管疾病库",
                "description": "心血管疾病相关文献合集"
            }
        }
    )

class ProcessingStatusUpdateDTO(BaseModel):
    """处理状态更新请求结构"""
    processingStatus: str = Field(..., alias="processing_status")
    
class VectorPathUpdateDTO(BaseModel):
    vectorStoragePath: str = Field(..., alias="vector_storage_path")
    
class PrefectDeploymentResponse(BaseModel):
    id: str
    name: str
    status: str