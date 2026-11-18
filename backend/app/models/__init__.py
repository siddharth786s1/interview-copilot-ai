"""
SQLModel table definitions — all models imported here so init_db sees them.
"""
from app.models.session import Session, TranscriptSegment, DetectedQuestion, GeneratedAnswer
from app.models.resume import Resume
from app.models.knowledge_base import KBDocument
from app.models.settings import AppSettings
from app.models.mock import MockSession, MockExchange

__all__ = [
    "Session", "TranscriptSegment", "DetectedQuestion", "GeneratedAnswer",
    "Resume", "KBDocument", "AppSettings", "MockSession", "MockExchange",
]
