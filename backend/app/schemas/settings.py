"""
Pydantic schemas for Settings API, including Gemini structured answer
and few-shot coaching profile configuration.
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class FewShotExample(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    ideal_answer: str = Field(min_length=2, max_length=2000)


class SettingsResponse(BaseModel):
    id: int
    stt_provider: str
    llm_provider: str
    llm_model: str
    whisper_model_size: str
    language: str
    default_answer_style: str
    default_technical_depth: str
    theme: str
    retention_days: Optional[int] = None
    structured_output: bool = True
    conversation_mode: bool = True
    target_role: str = ""
    custom_instructions: str = ""
    few_shot_examples: List[FewShotExample] = []
    updated_at: datetime


class SettingsUpdate(BaseModel):
    stt_provider: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    whisper_model_size: Optional[str] = None
    language: Optional[str] = None
    default_answer_style: Optional[str] = None
    default_technical_depth: Optional[str] = None
    theme: Optional[str] = None
    retention_days: Optional[int] = None
    structured_output: Optional[bool] = None
    conversation_mode: Optional[bool] = None
    target_role: Optional[str] = Field(default=None, max_length=200)
    custom_instructions: Optional[str] = Field(default=None, max_length=3000)
    few_shot_examples: Optional[List[FewShotExample]] = Field(default=None, max_length=10)
