"""
TranscriptManager — Manages streaming audio buffers, silence-based utterance
segmentation, partial vs finalized results, timestamps, and duplicate suppression.
"""
import asyncio
import logging
import re
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Awaitable, Callable, Deque, Dict, List, Optional, Tuple

import numpy as np

from app.services.transcription.base import SpeechToTextProvider

logger = logging.getLogger(__name__)

BYTES_PER_SECOND = 32000  # 16,000 Hz * 2 bytes/sample (16-bit mono)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", text.lower())).strip()


def _compute_pcm_rms(pcm_bytes: bytes) -> float:
    """Compute normalized RMS amplitude (0.0 to 1.0) of 16-bit signed PCM bytes."""
    usable = len(pcm_bytes) - (len(pcm_bytes) % 2)
    if usable < 2:
        return 0.0
    samples = np.frombuffer(pcm_bytes[:usable], dtype=np.int16).astype(np.float32) / 32768.0
    return float(np.sqrt(np.mean(samples * samples)))


@dataclass
class ManagedTranscriptEvent:
    """Structured transcript event ready for WebSocket broadcast and DB persistence."""
    session_id: str
    source: str  # "mic" | "tab"
    speaker_label: str  # best-effort label
    text: str
    is_final: bool
    timestamp: datetime
    sequence: int
    language: str = "en"
    confidence: float = 1.0
    latency_ms: int = 0

    def to_ws_dict(self) -> dict:
        return {
            "type": "transcript",
            "session_id": self.session_id,
            "source": self.source,
            "speaker_label": self.speaker_label,
            "text": self.text,
            "is_final": self.is_final,
            "timestamp": self.timestamp.isoformat(),
            "sequence": self.sequence,
            "language": self.language,
            "confidence": self.confidence,
            "latency_ms": self.latency_ms,
        }


@dataclass
class _SourceBuffer:
    pcm: bytearray = field(default_factory=bytearray)
    has_speech: bool = False
    trailing_silence_bytes: int = 0
    bytes_since_last_partial: int = 0
    last_partial_norm: str = ""
    speech_start_perf: float = 0.0


class TranscriptManager:
    """
    Processes incremental PCM audio chunks for a single interview session,
    producing deduplicated partial and finalized transcript events.
    """

    def __init__(
        self,
        session_id: str,
        stt_provider: SpeechToTextProvider,
        language: str = "en",
        silence_rms_threshold: float = 0.008,
        partial_interval_seconds: float = 1.2,
        silence_finalize_seconds: float = 0.6,
        max_utterance_seconds: float = 5.0,
        dedup_window_seconds: float = 15.0,
        on_event: Optional[Callable[[ManagedTranscriptEvent], Awaitable[None]]] = None,
    ):
        self.session_id = session_id
        self.stt_provider = stt_provider
        self.language = language
        self.silence_rms_threshold = silence_rms_threshold
        self.partial_interval_bytes = int(partial_interval_seconds * BYTES_PER_SECOND)
        self.silence_finalize_bytes = int(silence_finalize_seconds * BYTES_PER_SECOND)
        self.max_utterance_bytes = int(max_utterance_seconds * BYTES_PER_SECOND)
        self.dedup_window_seconds = dedup_window_seconds
        self.on_event = on_event

        self._buffers: Dict[str, _SourceBuffer] = {
            "mic": _SourceBuffer(),
            "tab": _SourceBuffer(),
        }
        self._locks: Dict[str, asyncio.Lock] = {
            "mic": asyncio.Lock(),
            "tab": asyncio.Lock(),
        }
        # Recent finalized utterances per source for duplicate suppression: (norm_text, monotonic_ts)
        self._recent_finals: Dict[str, Deque[Tuple[str, float]]] = {
            "mic": deque(maxlen=20),
            "tab": deque(maxlen=20),
        }
        self._sequence = 0
        self._paused = False
        self.latency_samples_ms: List[int] = []

    @property
    def paused(self) -> bool:
        return self._paused

    def set_paused(self, paused: bool) -> None:
        self._paused = paused

    def set_language(self, language: str) -> None:
        if language:
            self.language = language

    def _speaker_label(self, source: str) -> str:
        # Best-effort speaker label based on capture source
        if source == "tab":
            return "Interviewer"
        if source == "mic":
            return "Me"
        return "Speaker"

    def _is_duplicate_final(self, source: str, norm_text: str, now_mono: float) -> bool:
        recent = self._recent_finals[source]
        # Prune expired entries
        while recent and (now_mono - recent[0][1]) > self.dedup_window_seconds:
            recent.popleft()
        for prev_norm, _ in recent:
            if prev_norm == norm_text:
                return True
        return False

    def _record_final(self, source: str, norm_text: str, now_mono: float) -> None:
        self._recent_finals[source].append((norm_text, now_mono))

    async def process_audio_chunk(
        self, source: str, pcm_bytes: bytes
    ) -> List[ManagedTranscriptEvent]:
        """
        Ingest a raw 16kHz 16-bit mono PCM chunk for a given source ("mic" or "tab").
        Returns any transcript events emitted during this call.
        """
        if self._paused or not pcm_bytes:
            return []

        if source not in self._buffers:
            self._buffers[source] = _SourceBuffer()
            self._locks[source] = asyncio.Lock()
            self._recent_finals[source] = deque(maxlen=20)

        async with self._locks[source]:
            buf = self._buffers[source]
            rms = _compute_pcm_rms(pcm_bytes)
            is_speech = rms >= self.silence_rms_threshold

            if is_speech:
                if not buf.has_speech:
                    buf.has_speech = True
                    buf.speech_start_perf = time.perf_counter()
                buf.trailing_silence_bytes = 0
                buf.pcm.extend(pcm_bytes)
                buf.bytes_since_last_partial += len(pcm_bytes)
            else:
                if not buf.has_speech:
                    # Pure silence before any speech — keep a tiny pre-roll (200ms) and ignore the rest
                    buf.pcm.extend(pcm_bytes)
                    pre_roll = int(0.2 * BYTES_PER_SECOND)
                    if len(buf.pcm) > pre_roll:
                        del buf.pcm[: len(buf.pcm) - pre_roll]
                    return []
                else:
                    # Silence following speech
                    buf.pcm.extend(pcm_bytes)
                    buf.trailing_silence_bytes += len(pcm_bytes)
                    buf.bytes_since_last_partial += len(pcm_bytes)

            # Decide whether to finalize or emit a partial update
            should_finalize = (
                buf.has_speech
                and (
                    buf.trailing_silence_bytes >= self.silence_finalize_bytes
                    or len(buf.pcm) >= self.max_utterance_bytes
                )
            )

            if should_finalize:
                return await self._transcribe_buffer(source, buf, is_final=True)

            should_partial = (
                buf.has_speech
                and buf.bytes_since_last_partial >= self.partial_interval_bytes
            )
            if should_partial:
                buf.bytes_since_last_partial = 0
                return await self._transcribe_buffer(source, buf, is_final=False)

            return []

    async def flush(self, source: Optional[str] = None) -> List[ManagedTranscriptEvent]:
        """Finalize and flush any buffered speech for one or all sources."""
        sources = [source] if source else list(self._buffers.keys())
        emitted: List[ManagedTranscriptEvent] = []
        for src in sources:
            if src not in self._buffers:
                continue
            async with self._locks[src]:
                buf = self._buffers[src]
                if buf.has_speech and len(buf.pcm) >= 3200:
                    events = await self._transcribe_buffer(src, buf, is_final=True)
                    emitted.extend(events)
                else:
                    buf.pcm.clear()
                    buf.has_speech = False
                    buf.trailing_silence_bytes = 0
                    buf.bytes_since_last_partial = 0
                    buf.last_partial_norm = ""
        return emitted

    async def _transcribe_buffer(
        self, source: str, buf: _SourceBuffer, is_final: bool
    ) -> List[ManagedTranscriptEvent]:
        audio_snapshot = bytes(buf.pcm)

        if is_final:
            buf.pcm.clear()
            buf.has_speech = False
            buf.trailing_silence_bytes = 0
            buf.bytes_since_last_partial = 0
            buf.last_partial_norm = ""

        t0 = time.perf_counter()
        results = await self.stt_provider.transcribe_pcm(
            audio_snapshot,
            source=source,
            language=self.language,
            is_final=is_final,
        )
        total_ms = int((time.perf_counter() - t0) * 1000)

        emitted: List[ManagedTranscriptEvent] = []
        now_mono = time.monotonic()

        for res in results:
            cleaned = res.text.strip()
            if not cleaned:
                continue
            norm = _normalize_text(cleaned)
            if not norm:
                continue

            if not is_final:
                if norm == buf.last_partial_norm:
                    continue
                buf.last_partial_norm = norm
            else:
                if self._is_duplicate_final(source, norm, now_mono):
                    logger.debug("Suppressed duplicate final transcript (%s): %s", source, cleaned)
                    continue
                self._record_final(source, norm, now_mono)

            self._sequence += 1
            latency = res.latency_ms if res.latency_ms > 0 else total_ms
            if is_final:
                self.latency_samples_ms.append(latency)

            event = ManagedTranscriptEvent(
                session_id=self.session_id,
                source=source,
                speaker_label=self._speaker_label(source),
                text=cleaned,
                is_final=is_final,
                timestamp=res.timestamp or _utcnow(),
                sequence=self._sequence,
                language=res.language or self.language,
                confidence=res.confidence,
                latency_ms=latency,
            )
            emitted.append(event)

            if self.on_event is not None:
                await self.on_event(event)

        return emitted
