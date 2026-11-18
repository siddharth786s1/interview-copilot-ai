"""
Resume database model.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, Text


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Resume(SQLModel, table=True):
    __tablename__ = "resumes"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    filename: str = Field(max_length=255)
    file_path: str = Field(max_length=512)
    uploaded_at: datetime = Field(default_factory=_utcnow)
    extracted_text: Optional[str] = Field(default=None, sa_column=Column(Text))
    skills: Optional[str] = Field(default=None, sa_column=Column(Text))
    experience: Optional[str] = Field(default=None, sa_column=Column(Text))
    education: Optional[str] = Field(default=None, sa_column=Column(Text))
    certifications: Optional[str] = Field(default=None, sa_column=Column(Text))
    projects: Optional[str] = Field(default=None, sa_column=Column(Text))
    is_active: bool = Field(default=True)
