"""
Integration tests for WebSocket audio streaming, live transcription broadcast,
database persistence, language config, error handling, and socket reconnection.
"""
import asyncio
import json
import math
import struct
from typing import List

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel

from app.api.websockets.manager import ws_manager
from app.core.exceptions import ProviderError
from app.database.connection import get_session
from app.main import app as fastapi_app
from app.services.transcription.base import SpeechToTextProvider, TranscriptChunkResult
import app.models  # noqa: F401


def _sine_pcm(duration_sec: float, freq: float = 440.0) -> bytes:
    num_samples = int(16000 * duration_sec)
    samples = [
        int(0.5 * 32767 * math.sin(2 * math.pi * freq * i / 16000))
        for i in range(num_samples)
    ]
    return struct.pack(f"<{num_samples}h", *samples)


def _silence_pcm(duration_sec: float) -> bytes:
    return b"\x00\x00" * int(16000 * duration_sec)


class ScriptedSTTProvider(SpeechToTextProvider):
    def __init__(self, responses: List[str], raise_error: bool = False):
        self._responses = list(responses)
        self._raise_error = raise_error
        self.seen_languages: List[str] = []

    @property
    def name(self) -> str:
        return "scripted-stt"

    async def transcribe_pcm(
        self,
        audio_pcm: bytes,
        source: str,
        language: str = "en",
        is_final: bool = True,
    ) -> List[TranscriptChunkResult]:
        self.seen_languages.append(language)
        if self._raise_error:
            raise ProviderError("scripted-stt", "Simulated STT outage")
        if not self._responses:
            return []
        text = self._responses.pop(0) if len(self._responses) > 1 else self._responses[0]
        return [
            TranscriptChunkResult(
                text=text,
                source=source,
                is_final=is_final,
                language=language,
                confidence=0.96,
                latency_ms=15,
            )
        ]


@pytest.fixture
def sync_ws_env(tmp_path):
    """Set up an isolated temp-file async SQLite DB (NullPool) and TestClient for WebSocket tests."""
    db_file = tmp_path / "ws_test.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_file.as_posix()}",
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _init():
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        await engine.dispose()

    asyncio.run(_init())

    async def override_get_session():
        async with session_factory() as db:
            yield db

    orig_factory = ws_manager.stt_provider_factory
    orig_llm_factory = ws_manager.llm_provider_factory
    orig_db_factory = ws_manager.db_session_factory
    orig_auto_gen = ws_manager.auto_generate_answers
    ws_manager.db_session_factory = session_factory
    ws_manager.auto_generate_answers = False
    fastapi_app.dependency_overrides[get_session] = override_get_session

    with TestClient(fastapi_app) as client:
        yield client

    # Teardown
    ws_manager.stt_provider_factory = orig_factory
    ws_manager.llm_provider_factory = orig_llm_factory
    ws_manager.db_session_factory = orig_db_factory
    ws_manager.auto_generate_answers = orig_auto_gen
    ws_manager._transcript_managers.clear()
    ws_manager._question_engines.clear()
    ws_manager._session_sockets.clear()
    ws_manager._audio_sources.clear()
    fastapi_app.dependency_overrides.clear()


def test_ws_audio_to_transcript_and_db_persistence(sync_ws_env: TestClient):
    stt = ScriptedSTTProvider(["Explain the SAP authorization concept."])
    ws_manager.stt_provider_factory = lambda: stt

    # Create a session first
    resp = sync_ws_env.post("/api/sessions/", json={"title": "WS Transcription Test", "type": "technical"})
    assert resp.status_code == 201
    session_id = resp.json()["id"]

    with sync_ws_env.websocket_connect(f"/ws/session/{session_id}") as session_ws:
        # Initial status frame
        init_msg = json.loads(session_ws.receive_text())
        assert init_msg["type"] == "status"
        assert init_msg["session_status"] == "active"

        # Ping/pong heartbeat check
        session_ws.send_text(json.dumps({"type": "ping"}))
        pong_msg = json.loads(session_ws.receive_text())
        assert pong_msg["type"] == "pong"

        with sync_ws_env.websocket_connect(f"/ws/audio/{session_id}") as audio_ws:
            # Send tab audio (0x02 header) + speech + silence to finalize
            audio_ws.send_bytes(b"\x02" + _sine_pcm(0.8))
            audio_ws.send_bytes(b"\x02" + _silence_pcm(0.7))

            # Collect messages until we get the transcript event
            transcript_event = None
            for _ in range(5):
                msg = json.loads(session_ws.receive_text())
                if msg["type"] == "transcript":
                    transcript_event = msg
                    break

            assert transcript_event is not None
            assert transcript_event["text"] == "Explain the SAP authorization concept."
            assert transcript_event["source"] == "tab"
            assert transcript_event["speaker_label"] == "Interviewer"
            assert transcript_event["is_final"] is True
            assert "timestamp" in transcript_event
            assert transcript_event["sequence"] >= 1
            assert transcript_event["latency_ms"] >= 0

    # Verify persisted to DB via REST endpoint
    t_resp = sync_ws_env.get(f"/api/sessions/{session_id}/transcript")
    assert t_resp.status_code == 200
    rows = t_resp.json()
    assert len(rows) == 1
    assert rows[0]["text"] == "Explain the SAP authorization concept."
    assert rows[0]["source"] == "tab"
    assert rows[0]["is_final"] is True


def test_ws_reconnect_after_socket_kill(sync_ws_env: TestClient):
    """Kill both session and audio sockets, reconnect, and verify streaming resumes cleanly."""
    stt = ScriptedSTTProvider(
        ["First question before disconnect.", "Second question after reconnect."]
    )
    ws_manager.stt_provider_factory = lambda: stt

    resp = sync_ws_env.post("/api/sessions/", json={"title": "WS Reconnect Test", "type": "general"})
    session_id = resp.json()["id"]

    # Connection 1
    with sync_ws_env.websocket_connect(f"/ws/session/{session_id}") as s_ws1:
        _ = json.loads(s_ws1.receive_text())  # status
        with sync_ws_env.websocket_connect(f"/ws/audio/{session_id}") as a_ws1:
            a_ws1.send_bytes(b"\x01" + _sine_pcm(0.6))
            a_ws1.send_bytes(b"\x01" + _silence_pcm(0.7))
            got1 = None
            for _ in range(5):
                m = json.loads(s_ws1.receive_text())
                if m["type"] == "transcript":
                    got1 = m
                    break
            assert got1 is not None
            assert got1["text"] == "First question before disconnect."
    # Both sockets are now closed ("killed")

    # Connection 2 (reconnect to same session)
    with sync_ws_env.websocket_connect(f"/ws/session/{session_id}") as s_ws2:
        status2 = json.loads(s_ws2.receive_text())
        assert status2["type"] == "status"

        with sync_ws_env.websocket_connect(f"/ws/audio/{session_id}") as a_ws2:
            # Also verify language reconfiguration persists on reconnected audio socket
            a_ws2.send_text(json.dumps({"type": "config", "language": "de"}))
            lang_status = json.loads(s_ws2.receive_text())
            assert lang_status["type"] == "status"
            assert lang_status["language"] == "de"

            a_ws2.send_bytes(b"\x02" + _sine_pcm(0.6))
            a_ws2.send_bytes(b"\x02" + _silence_pcm(0.7))
            got2 = None
            for _ in range(5):
                m = json.loads(s_ws2.receive_text())
                if m["type"] == "transcript":
                    got2 = m
                    break
            assert got2 is not None
            assert got2["text"] == "Second question after reconnect."
            assert got2["language"] == "de"

    assert "de" in stt.seen_languages
    # Both segments persisted in DB
    rows = sync_ws_env.get(f"/api/sessions/{session_id}/transcript").json()
    assert len(rows) == 2


def test_ws_stt_provider_error_broadcasts_error_event(sync_ws_env: TestClient):
    stt = ScriptedSTTProvider([], raise_error=True)
    ws_manager.stt_provider_factory = lambda: stt

    resp = sync_ws_env.post("/api/sessions/", json={"title": "WS Error Test", "type": "general"})
    session_id = resp.json()["id"]

    with sync_ws_env.websocket_connect(f"/ws/session/{session_id}") as session_ws:
        _ = json.loads(session_ws.receive_text())  # initial status
        with sync_ws_env.websocket_connect(f"/ws/audio/{session_id}") as audio_ws:
            audio_ws.send_bytes(b"\x01" + _sine_pcm(0.6))
            audio_ws.send_bytes(b"\x01" + _silence_pcm(0.7))

            err_event = None
            for _ in range(5):
                m = json.loads(session_ws.receive_text())
                if m["type"] == "error":
                    err_event = m
                    break
            assert err_event is not None
            assert err_event["code"] == "STT_PROVIDER_ERROR"
            assert "Simulated STT outage" in err_event["message"]


def test_ws_audio_triggers_automatic_question_detection_and_db_save(sync_ws_env: TestClient):
    stt = ScriptedSTTProvider(["What is the difference between OTBI and BI Publisher?"])
    ws_manager.stt_provider_factory = lambda: stt

    resp = sync_ws_env.post("/api/sessions/", json={"title": "Auto Q Detect Test", "type": "technical"})
    session_id = resp.json()["id"]

    with sync_ws_env.websocket_connect(f"/ws/session/{session_id}") as session_ws:
        _ = json.loads(session_ws.receive_text())  # initial status

        with sync_ws_env.websocket_connect(f"/ws/audio/{session_id}") as audio_ws:
            audio_ws.send_bytes(b"\x02" + _sine_pcm(0.7))
            audio_ws.send_bytes(b"\x02" + _silence_pcm(0.7))

            got_transcript = None
            got_question = None
            for _ in range(6):
                msg = json.loads(session_ws.receive_text())
                if msg["type"] == "transcript":
                    got_transcript = msg
                elif msg["type"] == "question":
                    got_question = msg
                    break

            assert got_transcript is not None
            assert got_question is not None
            assert got_question["text"] == "What is the difference between OTBI and BI Publisher?"
            assert got_question["question_type"] == "technical"

    q_rows = sync_ws_env.get(f"/api/sessions/{session_id}/questions").json()
    assert len(q_rows) == 1
    assert q_rows[0]["question_text"] == "What is the difference between OTBI and BI Publisher?"
    assert q_rows[0]["question_type"] == "technical"


def test_manual_question_rest_endpoint_persists_and_broadcasts(sync_ws_env: TestClient):
    resp = sync_ws_env.post("/api/sessions/", json={"title": "Manual Q Test", "type": "hr"})
    session_id = resp.json()["id"]

    with sync_ws_env.websocket_connect(f"/ws/session/{session_id}") as session_ws:
        _ = json.loads(session_ws.receive_text())  # initial status

        post_resp = sync_ws_env.post(
            f"/api/sessions/{session_id}/questions",
            json={"question_text": "Tell me about yourself.", "question_type": "manual"},
        )
        assert post_resp.status_code == 201
        created = post_resp.json()
        assert created["question_text"] == "Tell me about yourself."
        assert created["question_type"] == "manual"

        ws_msg = json.loads(session_ws.receive_text())
        assert ws_msg["type"] == "question"
        assert ws_msg["question_id"] == created["id"]
        assert ws_msg["text"] == "Tell me about yourself."
        assert ws_msg["question_type"] == "manual"

    q_rows = sync_ws_env.get(f"/api/sessions/{session_id}/questions").json()
    assert len(q_rows) == 1
    assert q_rows[0]["id"] == created["id"]

