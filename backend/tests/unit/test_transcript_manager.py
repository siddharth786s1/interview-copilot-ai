"""
Unit tests for TranscriptManager: buffering, VAD/silence gating,
partial vs final emission, duplicate suppression, pause/resume, language config.
"""
import math
import struct
from typing import List

import pytest

from app.services.transcription.base import SpeechToTextProvider, TranscriptChunkResult
from app.services.transcription.transcript_manager import (
    BYTES_PER_SECOND,
    ManagedTranscriptEvent,
    TranscriptManager,
)


def make_sine_pcm(duration_sec: float, freq: float = 440.0, amplitude: float = 0.5) -> bytes:
    """Generate synthetic 16kHz 16-bit mono PCM sine wave (triggers speech VAD)."""
    num_samples = int(16000 * duration_sec)
    samples = [
        int(max(-32767, min(32767, amplitude * 32767 * math.sin(2 * math.pi * freq * i / 16000))))
        for i in range(num_samples)
    ]
    return struct.pack(f"<{num_samples}h", *samples)


def make_silence_pcm(duration_sec: float) -> bytes:
    """Generate synthetic 16kHz 16-bit mono silent PCM."""
    return b"\x00\x00" * int(16000 * duration_sec)


class FakeSTTProvider(SpeechToTextProvider):
    """Deterministic STT test double."""

    def __init__(self, responses: List[str]):
        self._responses = list(responses)
        self.calls: List[dict] = []

    @property
    def name(self) -> str:
        return "fake-stt"

    async def transcribe_pcm(
        self,
        audio_pcm: bytes,
        source: str,
        language: str = "en",
        is_final: bool = True,
    ) -> List[TranscriptChunkResult]:
        self.calls.append(
            {
                "bytes": len(audio_pcm),
                "source": source,
                "language": language,
                "is_final": is_final,
            }
        )
        if not self._responses:
            return []
        text = self._responses.pop(0) if len(self._responses) > 1 else self._responses[0]
        return [
            TranscriptChunkResult(
                text=text,
                source=source,
                is_final=is_final,
                language=language,
                confidence=0.98,
                latency_ms=12,
            )
        ]


@pytest.mark.asyncio
async def test_silence_never_invokes_stt():
    stt = FakeSTTProvider(["Should not appear"])
    tm = TranscriptManager(session_id="s1", stt_provider=stt)

    for _ in range(10):
        events = await tm.process_audio_chunk("tab", make_silence_pcm(0.5))
        assert events == []

    assert len(stt.calls) == 0


@pytest.mark.asyncio
async def test_speech_then_silence_emits_final_event():
    stt = FakeSTTProvider(["What is SQL injection?"])
    received: List[ManagedTranscriptEvent] = []

    async def on_event(ev: ManagedTranscriptEvent):
        received.append(ev)

    tm = TranscriptManager(
        session_id="s1",
        stt_provider=stt,
        partial_interval_seconds=2.0,
        silence_finalize_seconds=0.5,
        on_event=on_event,
    )

    # 0.8s of speech
    ev1 = await tm.process_audio_chunk("tab", make_sine_pcm(0.8))
    assert ev1 == []

    # 0.6s of silence -> triggers finalization
    ev2 = await tm.process_audio_chunk("tab", make_silence_pcm(0.6))
    assert len(ev2) == 1
    assert ev2[0].is_final is True
    assert ev2[0].text == "What is SQL injection?"
    assert ev2[0].speaker_label == "Interviewer"
    assert ev2[0].source == "tab"
    assert ev2[0].sequence == 1
    assert ev2[0].timestamp is not None
    assert len(received) == 1


@pytest.mark.asyncio
async def test_partial_then_final_emitted_distinctly():
    stt = FakeSTTProvider(
        ["Explain the difference", "Explain the difference between auth and authz."]
    )
    tm = TranscriptManager(
        session_id="s1",
        stt_provider=stt,
        partial_interval_seconds=0.5,
        silence_finalize_seconds=0.4,
        max_utterance_seconds=3.0,
    )

    # 0.6s speech -> exceeds partial interval (0.5s) -> emits partial
    ev_partial = await tm.process_audio_chunk("tab", make_sine_pcm(0.6))
    assert len(ev_partial) == 1
    assert ev_partial[0].is_final is False
    assert ev_partial[0].text == "Explain the difference"

    # 0.5s silence -> triggers finalization
    ev_final = await tm.process_audio_chunk("tab", make_silence_pcm(0.5))
    assert len(ev_final) == 1
    assert ev_final[0].is_final is True
    assert ev_final[0].text == "Explain the difference between auth and authz."
    assert ev_final[0].sequence == 2


@pytest.mark.asyncio
async def test_duplicate_final_suppression():
    stt = FakeSTTProvider(["What is SQL injection?", "What is SQL injection?!"])
    tm = TranscriptManager(
        session_id="s1",
        stt_provider=stt,
        silence_finalize_seconds=0.3,
        dedup_window_seconds=15.0,
    )

    # First utterance
    await tm.process_audio_chunk("tab", make_sine_pcm(0.5))
    ev1 = await tm.process_audio_chunk("tab", make_silence_pcm(0.4))
    assert len(ev1) == 1

    # Duplicate utterance within dedup window (even with punctuation difference)
    await tm.process_audio_chunk("tab", make_sine_pcm(0.5))
    ev2 = await tm.process_audio_chunk("tab", make_silence_pcm(0.4))
    assert ev2 == []


@pytest.mark.asyncio
async def test_separate_sources_independent_buffers_and_labels():
    stt = FakeSTTProvider(["Tell me about yourself.", "I am a backend engineer."])
    tm = TranscriptManager(
        session_id="s1",
        stt_provider=stt,
        silence_finalize_seconds=0.3,
    )

    await tm.process_audio_chunk("tab", make_sine_pcm(0.4))
    await tm.process_audio_chunk("mic", make_sine_pcm(0.4))

    tab_ev = await tm.process_audio_chunk("tab", make_silence_pcm(0.4))
    mic_ev = await tm.process_audio_chunk("mic", make_silence_pcm(0.4))

    assert len(tab_ev) == 1
    assert tab_ev[0].source == "tab"
    assert tab_ev[0].speaker_label == "Interviewer"

    assert len(mic_ev) == 1
    assert mic_ev[0].source == "mic"
    assert mic_ev[0].speaker_label == "Me"


@pytest.mark.asyncio
async def test_pause_and_language_config():
    stt = FakeSTTProvider(["Hola mundo"])
    tm = TranscriptManager(session_id="s1", stt_provider=stt, language="en")

    tm.set_paused(True)
    ev = await tm.process_audio_chunk("mic", make_sine_pcm(1.0))
    assert ev == []
    assert len(stt.calls) == 0

    tm.set_language("es")
    tm.set_paused(False)
    await tm.process_audio_chunk("mic", make_sine_pcm(0.5))
    flushed = await tm.flush("mic")
    assert len(flushed) == 1
    assert flushed[0].language == "es"
    assert stt.calls[0]["language"] == "es"
