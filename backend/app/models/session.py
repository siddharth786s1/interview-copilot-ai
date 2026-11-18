"""
Session-related database models.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, Text


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Session(SQLModel, table=True):
    __tablename__ = "sessions"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    title: str = Field(max_length=200)
    type: str = Field(default="general")  # technical|hr|behavioral|general|mock|custom
    status: str = Field(default="created")  # created|active|paused|ended
    created_at: datetime = Field(default_factory=_utcnow)
    ended_at: Optional[datetime] = Field(default=None)
    duration_seconds: Optional[int] = Field(default=None)
    settings_snapshot: Optional[str] = Field(default=None, sa_column=Column(Text))


class TranscriptSegment(SQLModel, table=True):
    __tablename__ = "transcript_segments"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    session_id: str = Field(foreign_key="sessions.id", index=True)
    source: str = Field(default="mic")  # tab|mic|manual
    speaker_label: Optional[str] = Field(default=None, max_length=50)
    text: str = Field(sa_column=Column(Text))
    is_final: bool = Field(default=False)
    timestamp: datetime = Field(default_factory=_utcnow)
    sequence: int = Field(default=0)


class DetectedQuestion(SQLModel, table=True):
    __tablename__ = "detected_questions"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    session_id: str = Field(foreign_key="sessions.id", index=True)
    segment_ids: Optional[str] = Field(default=None, sa_column=Column(Text))  # JSON list
    question_text: str = Field(sa_column=Column(Text))
    question_type: str = Field(default="direct")  # direct|indirect|technical|followup|manual
    detected_at: datetime = Field(default_factory=_utcnow)
    answered: bool = Field(default=False)


class GeneratedAnswer(SQLModel, table=True):
    __tablename__ = "generated_answers"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    question_id: str = Field(foreign_key="detected_questions.id", index=True)
    style: str = Field(default="short")  # short|detailed|practical|stepbystep
    answer_text: str = Field(sa_column=Column(Text))
    model_used: str = Field(default="")
    generated_at: datetime = Field(default_factory=_utcnow)
    generation_time_ms: int = Field(default=0)
