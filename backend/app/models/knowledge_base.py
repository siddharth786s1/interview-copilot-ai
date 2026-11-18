"""
Knowledge base document model.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, Text


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class KBDocument(SQLModel, table=True):
    __tablename__ = "kb_documents"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    filename: str = Field(max_length=255)
    file_path: str = Field(max_length=512)
    category: str = Field(default="Custom", max_length=100)
    uploaded_at: datetime = Field(default_factory=_utcnow)
    extracted_text: Optional[str] = Field(default=None, sa_column=Column(Text))
    chunks: Optional[str] = Field(default=None, sa_column=Column(Text))
    is_active: bool = Field(default=True)
