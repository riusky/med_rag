from sqlalchemy.orm import DeclarativeBase

from med_rag_server.db.meta import meta


class Base(DeclarativeBase):
    """Base for all models."""

    metadata = meta
