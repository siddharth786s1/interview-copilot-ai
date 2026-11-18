"""
Pydantic schemas for Session API.
"""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    type: str = Field(default="general")
    settings: Optional[Dict[str, Any]] = None


class SessionUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    status: Optional[str] = Field(default=None)


class SessionResponse(BaseModel):
    id: str
    title: str
    type: str
    status: str
    created_at: datetime
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None

    model_config = {"from_attributes": True}


class ManualQuestionCreate(BaseModel):
    question_text: str = Field(min_length=2, max_length=2000)
    question_type: str = Field(default="manual")
    style: Optional[str] = Field(default=None)
    auto_generate: bool = Field(default=True)


class AnswerRequest(BaseModel):
    style: Optional[str] = Field(default=None)  # short | detailed | practical | stepbystep
    technical_depth: Optional[str] = Field(default=None)  # low | medium | high
    expand: bool = Field(default=False)


class AnswerResponse(BaseModel):
    id: str
    question_id: str
    style: str
    answer_text: str
    model_used: str
    generated_at: datetime
    generation_time_ms: int
    ttft_ms: Optional[int] = None
    keywords: list[str] = []
    needs_customization: bool = False

    model_config = {"from_attributes": True}


class ScreenAnalysisResponse(BaseModel):
    actionable: bool
    topic: str
    screen_summary: str
    question: Optional[Dict[str, Any]] = None
    answer: Optional[AnswerResponse] = None
    analysis_time_ms: int



