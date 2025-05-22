# med_rag_server/db/models/knowledge_base_model.py
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime, Text, text
from med_rag_server.db.base import Base


class KnowledgeBaseModel(Base):
    """精简版知识库模型（保留向量存储路径）"""
    __tablename__ = "knowledge_base"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, comment="知识库唯一标识名称")
    description: Mapped[Optional[str]] = mapped_column(String(500), comment="知识库描述")
    
    # 保留核心字段
    vector_storage_path: Mapped[Optional[str]] = mapped_column(  # 修改为Optional
        String(500),
        nullable=True,
        comment="向量数据存储路径（处理完成后更新）"  # 更新注释说明
    )
    
    processing_status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        comment="处理状态（pending/processing/completed/failed）"
    )
    

    # 时间记录
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))