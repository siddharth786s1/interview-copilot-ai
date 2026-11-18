"""
Mock interview session and exchange models.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, Text


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MockSession(SQLModel, table=True):
    __tablename__ = "mock_sessions"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    topic: str = Field(max_length=200)
    created_at: datetime = Field(default_factory=_utcnow)
    ended_at: Optional[datetime] = Field(default=None)


class MockExchange(SQLModel, table=True):
    __tablename__ = "mock_exchanges"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    mock_session_id: str = Field(foreign_key="mock_sessions.id", index=True)
    question_text: str = Field(sa_column=Column(Text))
    user_answer: Optional[str] = Field(default=None, sa_column=Column(Text))
    evaluation: Optional[str] = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(default_factory=_utcnow)
