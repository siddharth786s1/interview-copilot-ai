"""
Application settings model (single row, id=1), including Gemini structured
answer training preferences (target role, structured mode, custom instructions,
and few-shot coaching examples).
"""
from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, Text


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AppSettings(SQLModel, table=True):
    __tablename__ = "app_settings"

    id: int = Field(default=1, primary_key=True)
    stt_provider: str = Field(default="whisper")
    llm_provider: str = Field(default="gemini")
    llm_model: str = Field(default="gemini-3.5-flash-lite")
    whisper_model_size: str = Field(default="base")
    language: str = Field(default="en")
    default_answer_style: str = Field(default="short")
    default_technical_depth: str = Field(default="medium")
    theme: str = Field(default="dark")
    retention_days: Optional[int] = Field(default=None)
    # Gemini Answer Structure & Coaching Profile
    structured_output: bool = Field(default=True)
    conversation_mode: bool = Field(default=True)  # Reply to full conversation turns, not only formal questions
    target_role: str = Field(default="")
    custom_instructions: str = Field(default="", sa_column=Column(Text))
    few_shot_examples: Optional[str] = Field(default=None, sa_column=Column(Text))  # JSON list[{question, ideal_answer}]
    updated_at: datetime = Field(default_factory=_utcnow)
