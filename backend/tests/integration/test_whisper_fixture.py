"""
Real end-to-end STT integration test using faster-whisper (tiny) on the
committed 16kHz 16-bit mono WAV fixture ('What is SQL injection and how do you prevent it?').
"""
import wave
from pathlib import Path

import pytest

from app.services.transcription.whisper_provider import WhisperProvider

FIXTURE_WAV = Path(__file__).resolve().parent.parent / "fixtures" / "sample_audio.wav"


@pytest.mark.asyncio
async def test_whisper_transcribes_real_spoken_wav_fixture():
    assert FIXTURE_WAV.exists(), f"Missing fixture: {FIXTURE_WAV}"
    with wave.open(str(FIXTURE_WAV), "rb") as wf:
        assert wf.getframerate() == 16000
        assert wf.getsampwidth() == 2
        assert wf.getnchannels() == 1
        pcm = wf.readframes(wf.getnframes())

    provider = WhisperProvider(model_size="tiny")
    results = await provider.transcribe_pcm(pcm, source="tab", language="en", is_final=True)

    assert len(results) == 1
    text_lower = results[0].text.lower()
    assert "sql" in text_lower
    assert "injection" in text_lower
    assert results[0].source == "tab"
    assert results[0].is_final is True
    assert results[0].latency_ms > 0
