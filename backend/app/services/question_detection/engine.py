"""
QuestionDetectionEngine — Analyzes finalized interview transcript segments to
identify direct, indirect, technical, and follow-up questions while merging
multi-segment fragments and suppressing small talk and duplicates.
"""
import logging
import re
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Deque, List, Optional, Tuple

from app.services.question_detection.patterns import (
    DIRECT_QUESTION_STARTERS,
    FOLLOWUP_PATTERNS,
    FRAGMENT_ONLY_PATTERNS,
    INCOMPLETE_ENDINGS,
    INDIRECT_QUESTION_PATTERNS,
    SMALL_TALK_PATTERNS,
    TECHNICAL_KEYWORDS,
)

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", text.lower())).strip()


def _tokenize(text: str) -> set[str]:
    norm = _normalize(text)
    stop = {"the", "a", "an", "is", "are", "of", "to", "in", "and", "or", "me", "you", "your", "please", "can", "could"}
    tokens = {t for t in norm.split() if len(t) > 1 and t not in stop}
    return tokens if tokens else set(norm.split())


def _jaccard_similarity(a: str, b: str) -> float:
    ta = _tokenize(a)
    tb = _tokenize(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


@dataclass
class DetectedQuestionEvent:
    """Output produced when a genuine interview question is detected."""
    id: str
    session_id: str
    question_text: str
    question_type: str  # direct | indirect | technical | followup | manual
    segment_ids: List[str] = field(default_factory=list)
    parent_question_id: Optional[str] = None
    detected_at: datetime = field(default_factory=_utcnow)
    detection_latency_ms: float = 0.0

    def to_ws_dict(self) -> dict:
        return {
            "type": "question",
            "question_id": self.id,
            "session_id": self.session_id,
            "text": self.question_text,
            "question_type": self.question_type,
            "segment_ids": self.segment_ids,
            "parent_question_id": self.parent_question_id,
            "detected_at": self.detected_at.isoformat(),
            "detection_latency_ms": round(self.detection_latency_ms, 2),
        }


@dataclass
class _PendingFragment:
    source: str
    text: str
    segment_ids: List[str]
    created_mono: float


class QuestionDetectionEngine:
    """
    Stateful per-session question detector.

    Maintains:
    - Recent conversation history (for follow-up detection)
    - Pending incomplete fragments per source (for multi-segment merging)
    - Recently emitted questions (for exact + near-duplicate suppression)
    """

    def __init__(
        self,
        session_id: str,
        fragment_timeout_seconds: float = 8.0,
        dedup_window_seconds: float = 300.0,
        dedup_similarity_threshold: float = 0.80,
    ):
        self.session_id = session_id
        self.fragment_timeout_seconds = fragment_timeout_seconds
        self.dedup_window_seconds = dedup_window_seconds
        self.dedup_similarity_threshold = dedup_similarity_threshold

        # Conversation history: (source, text, timestamp_mono)
        self._history: Deque[Tuple[str, str, float]] = deque(maxlen=30)
        # Recent emitted questions: (question_id, norm_text, raw_text, timestamp_mono)
        self._recent_questions: Deque[Tuple[str, str, str, float]] = deque(maxlen=25)
        # Pending incomplete fragment per source
        self._pending: dict[str, _PendingFragment] = {}
        # Measured latencies (ms)
        self.latency_samples_ms: List[float] = []

    def _is_small_talk(self, text: str) -> bool:
        stripped = text.strip()
        if not stripped:
            return True
        for pat in SMALL_TALK_PATTERNS:
            if pat.search(stripped):
                return True
        return False

    def _is_incomplete_fragment(self, text: str) -> bool:
        stripped = text.strip()
        if not stripped:
            return True
        if stripped.endswith("?"):
            # Even with '?', check for standalone ultra-short fragment like "Could you?"
            words = _normalize(stripped).split()
            return len(words) < 3
        for pat in FRAGMENT_ONLY_PATTERNS:
            if pat.match(stripped):
                return True
        if stripped.endswith("...") or stripped.endswith("…"):
            return True
        # Short utterance ending on a dangling preposition/conjunction/verb
        words = _normalize(stripped).split()
        if len(words) <= 6 and INCOMPLETE_ENDINGS.search(stripped):
            return True
        return False

    def _has_technical_keyword(self, text: str) -> bool:
        lower = text.lower()
        for kw in TECHNICAL_KEYWORDS:
            if re.search(rf"\b{re.escape(kw)}\b", lower):
                return True
        return False

    def _is_followup(self, text: str) -> bool:
        if not self._recent_questions and len(self._history) < 2:
            return False
        for pat in FOLLOWUP_PATTERNS:
            if pat.search(text):
                return True
        return False

    def _classify_question(self, text: str) -> Optional[str]:
        """
        Return question_type ('followup', 'technical', 'direct', 'indirect')
        or None if text is not a question.
        """
        stripped = text.strip()
        words = _normalize(stripped).split()
        if len(words) < 3:
            return None

        if self._is_small_talk(stripped):
            return None

        is_followup = self._is_followup(stripped)
        has_qmark = stripped.endswith("?")
        is_direct = bool(DIRECT_QUESTION_STARTERS.match(stripped))
        is_indirect = any(p.search(stripped) for p in INDIRECT_QUESTION_PATTERNS)

        if not (has_qmark or is_direct or is_indirect or is_followup):
            return None

        if is_followup:
            return "followup"
        if self._has_technical_keyword(stripped):
            return "technical"
        if has_qmark or is_direct:
            return "direct"
        return "indirect"

    def _is_duplicate(self, text: str, now_mono: float) -> bool:
        norm = _normalize(text)
        # Prune expired entries
        while self._recent_questions and (now_mono - self._recent_questions[0][3]) > self.dedup_window_seconds:
            self._recent_questions.popleft()

        for _, prev_norm, prev_raw, _ in self._recent_questions:
            if prev_norm == norm:
                return True
            if _jaccard_similarity(text, prev_raw) >= self.dedup_similarity_threshold:
                return True
        return False

    def record_user_speech(self, text: str) -> None:
        """Record candidate's own speech in history so follow-up questions can be detected."""
        cleaned = text.strip()
        if cleaned:
            self._history.append(("mic", cleaned, time.monotonic()))

    def process_segment(
        self,
        text: str,
        source: str = "tab",
        segment_id: Optional[str] = None,
        now_mono: Optional[float] = None,
    ) -> Optional[DetectedQuestionEvent]:
        """
        Analyze a finalized transcript segment.

        Returns a DetectedQuestionEvent if a new, non-duplicate question is complete;
        otherwise returns None (buffering fragments or suppressing small talk/duplicates).
        """
        t0 = time.perf_counter()
        mono = now_mono if now_mono is not None else time.monotonic()
        cleaned = text.strip()
        if not cleaned:
            return None

        seg_id = segment_id or str(uuid.uuid4())

        # Check if there is a pending fragment from the same source within timeout
        pending = self._pending.get(source)
        segment_ids = [seg_id]
        combined_text = cleaned

        if pending is not None:
            if (mono - pending.created_mono) <= self.fragment_timeout_seconds:
                # Merge previous fragment with new segment
                prefix = pending.text.rstrip(".… ").strip()
                combined_text = f"{prefix} {cleaned}".strip()
                segment_ids = pending.segment_ids + [seg_id]
                del self._pending[source]
            else:
                del self._pending[source]

        # Record in conversation context
        self._history.append((source, combined_text, mono))

        # Suppress small talk immediately (never buffer small talk as a fragment)
        if self._is_small_talk(combined_text):
            return None

        # Buffer incomplete fragments waiting for the next segment
        if self._is_incomplete_fragment(combined_text):
            self._pending[source] = _PendingFragment(
                source=source,
                text=combined_text,
                segment_ids=segment_ids,
                created_mono=mono,
            )
            return None

        # Classify whether this complete utterance is a question
        q_type = self._classify_question(combined_text)
        if q_type is None:
            return None

        # Suppress duplicates
        if self._is_duplicate(combined_text, mono):
            logger.debug("Suppressed duplicate question: %s", combined_text)
            return None

        # Link parent question if follow-up
        parent_id: Optional[str] = None
        if q_type == "followup" and self._recent_questions:
            parent_id = self._recent_questions[-1][0]

        q_id = str(uuid.uuid4())
        latency_ms = (time.perf_counter() - t0) * 1000.0
        self.latency_samples_ms.append(latency_ms)

        self._recent_questions.append((q_id, _normalize(combined_text), combined_text, mono))

        return DetectedQuestionEvent(
            id=q_id,
            session_id=self.session_id,
            question_text=combined_text,
            question_type=q_type,
            segment_ids=segment_ids,
            parent_question_id=parent_id,
            detected_at=_utcnow(),
            detection_latency_ms=latency_ms,
        )

    def register_manual_question(
        self,
        question_text: str,
        question_id: Optional[str] = None,
        question_type: str = "manual",
    ) -> DetectedQuestionEvent:
        """Register a manually submitted or screen-detected question into context/history for follow-up tracking."""
        cleaned = question_text.strip()
        q_id = question_id or str(uuid.uuid4())
        mono = time.monotonic()
        self._history.append((question_type, cleaned, mono))
        self._recent_questions.append((q_id, _normalize(cleaned), cleaned, mono))
        return DetectedQuestionEvent(
            id=q_id,
            session_id=self.session_id,
            question_text=cleaned,
            question_type=question_type,
            segment_ids=[],
            parent_question_id=None,
            detected_at=_utcnow(),
            detection_latency_ms=0.0,
        )
