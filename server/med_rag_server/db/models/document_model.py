# med_rag_server/db/models/document_model.py
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime, Boolean, ForeignKey, JSON

from med_rag_server.db.base import Base

class DocumentModel(Base):
    """文档数据模型"""
    __tablename__ = "document"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kb_id: Mapped[int] = mapped_column(ForeignKey("knowledge_base.id"), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), unique=True)
    chunk_method: Mapped[str] = mapped_column(String(50), default="fixed")
    chunk_params: Mapped[dict] = mapped_column(
        JSON, 
        default=lambda: {"chunk_size": 1500, "overlap": 150}
    )
    upload_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    parsing_status: Mapped[str] = mapped_column(String(20), default="pending")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)