"""
Integration tests for Phase 8:
- Interview History: list, detail, search past questions, Markdown/JSON export,
  transcript-only purge, full delete, and retention-based deletion.
- Mock Interview Mode: ask -> answer -> evaluate -> suggest loop (both LLM and
  offline local rubric), performance tracking, spoken answer transcription, and
  strict data isolation from live interview sessions.
"""
import json
from datetime import datetime, timedelta, timezone
from typing import AsyncIterator

import pytest

from app.api.websockets.manager import ws_manager
from app.models.session import (
    DetectedQuestion,
    GeneratedAnswer,
    Session,
    TranscriptSegment,
)
from app.services.answer_generation.base import LLMProvider
from app.services.answer_generation.gemini_provider import GeminiProvider
from app.services.transcription.base import SpeechToTextProvider, TranscriptChunkResult
from tests.conftest import TestAsyncSessionLocal


class FakeMockLLM(LLMProvider):
    @property
    def name(self) -> str:
        return "fake-mock-llm"

    @property
    def model_name(self) -> str:
        return "mock-v1"

    async def stream_generate(
        self, system_prompt: str, user_prompt: str, max_tokens: int = 800, temperature: float = 0.3
    ) -> AsyncIterator[str]:
        if "Return the JSON evaluation" in user_prompt:
            yield json.dumps(
                {
                    "score": 84,
                    "feedback": "Clear explanation of parameterized queries.",
                    "missing_concepts": ["least privilege DB account", "WAF defense-in-depth"],
                    "improved_answer": "Use parameterized queries, ORM bindings, and least-privilege DB accounts.",
                }
            )
        else:
            yield "How do you prevent SQL injection in a Python FastAPI service?"


class FakeMockSTT(SpeechToTextProvider):
    @property
    def name(self) -> str:
        return "fake-mock-stt"

    async def transcribe_pcm(self, audio_pcm: bytes, source: str, language: str = "en", is_final: bool = True):
        return [
            TranscriptChunkResult(
                text="Use parameterized queries to prevent SQL injection.",
                source=source,
                is_final=True,
                language=language,
                latency_ms=10,
            )
        ]


@pytest.mark.asyncio
async def test_history_list_detail_search_export_and_transcript_delete(client):
    # Seed a live session with transcript, question, and generated answer
    s_resp = await client.post("/api/sessions/", json={"title": "Security Round 1", "type": "technical"})
    s_id = s_resp.json()["id"]

    async with TestAsyncSessionLocal() as db:
        t1 = TranscriptSegment(
            session_id=s_id, source="tab", speaker_label="Interviewer", text="What is SQL injection?", is_final=True, sequence=1
        )
        t2 = TranscriptSegment(
            session_id=s_id, source="mic", speaker_label="Me", text="It is untrusted SQL concatenation.", is_final=True, sequence=2
        )
        q1 = DetectedQuestion(
            session_id=s_id, question_text="What is SQL injection?", question_type="technical", answered=True
        )
        db.add_all([t1, t2, q1])
        await db.commit()
        await db.refresh(q1)

        a1 = GeneratedAnswer(
            question_id=q1.id,
            style="short",
            answer_text="SQL injection exploits unsafe query concatenation; prevent it with parameterized queries.",
            model_used="gemini:gemini-2.0-flash",
            generation_time_ms=420,
        )
        db.add(a1)
        await db.commit()

    # 1. List history with counts
    list_resp = await client.get("/api/history/")
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) == 1
    assert items[0]["id"] == s_id
    assert items[0]["transcript_count"] == 2
    assert items[0]["question_count"] == 1
    assert items[0]["answer_count"] == 1

    # 2. Detail view
    det_resp = await client.get(f"/api/history/{s_id}")
    assert det_resp.status_code == 200
    detail = det_resp.json()
    assert len(detail["transcript"]) == 2
    assert len(detail["qa_pairs"]) == 1
    assert "parameterized queries" in detail["qa_pairs"][0]["answers"][0]["answer_text"]

    # 3. Search past questions
    search_resp = await client.get("/api/history/search?q=SQL+injection")
    assert search_resp.status_code == 200
    hits = search_resp.json()
    assert len(hits) == 1
    assert hits[0]["session_id"] == s_id
    assert hits[0]["question_text"] == "What is SQL injection?"

    # 4. Export Markdown & JSON
    md_resp = await client.get(f"/api/history/{s_id}/export?format=markdown")
    assert md_resp.status_code == 200
    assert "# Interview Notes — Security Round 1" in md_resp.text
    assert "What is SQL injection?" in md_resp.text
    assert "parameterized queries" in md_resp.text

    json_resp = await client.get(f"/api/history/{s_id}/export?format=json")
    assert json_resp.status_code == 200
    exported = json_resp.json()
    assert exported["session"]["id"] == s_id
    assert len(exported["qa_pairs"]) == 1

    # 5. Purge transcript only (retains Q&A)
    pt_resp = await client.delete(f"/api/history/{s_id}/transcript")
    assert pt_resp.status_code == 204
    det_after = (await client.get(f"/api/history/{s_id}")).json()
    assert det_after["transcript"] == []
    assert len(det_after["qa_pairs"]) == 1

    # 6. Full delete
    del_resp = await client.delete(f"/api/history/{s_id}")
    assert del_resp.status_code == 204
    assert (await client.get(f"/api/history/{s_id}")).status_code == 404


@pytest.mark.asyncio
async def test_retention_policy_actually_deletes_expired_sessions(client):
    # Create one expired session (45 days old) and one recent session (today)
    async with TestAsyncSessionLocal() as db:
        old_session = Session(
            title="Old Expired Session",
            type="hr",
            status="ended",
            created_at=datetime.now(timezone.utc) - timedelta(days=45),
        )
        fresh_session = Session(
            title="Fresh Recent Session",
            type="technical",
            status="ended",
            created_at=datetime.now(timezone.utc),
        )
        db.add_all([old_session, fresh_session])
        await db.commit()
        await db.refresh(old_session)
        await db.refresh(fresh_session)

        old_q = DetectedQuestion(session_id=old_session.id, question_text="Old Q?")
        db.add(old_q)
        await db.commit()
        old_id = old_session.id
        fresh_id = fresh_session.id

    # Configure retention_days = 30 via Settings API
    upd = await client.patch("/api/settings/", json={"retention_days": 30})
    assert upd.status_code == 200
    assert upd.json()["retention_days"] == 30

    # Trigger retention purge
    purge = await client.post("/api/history/purge-retention")
    assert purge.status_code == 200
    body = purge.json()
    assert body["retention_days"] == 30
    assert body["deleted_sessions"] == 1

    # Expired session is gone; fresh session remains
    assert (await client.get(f"/api/history/{old_id}")).status_code == 404
    assert (await client.get(f"/api/history/{fresh_id}")).status_code == 200


@pytest.mark.asyncio
async def test_mock_interview_end_to_end_and_strict_live_isolation(client, monkeypatch):
    # Force offline mode (empty API key) for the first half so tests stay hermetic even when .env has a real key
    monkeypatch.setattr(ws_manager, "llm_provider_factory", lambda _p=None, _m=None: GeminiProvider(api_key=""))
    create_resp = await client.post("/api/mock/sessions", json={"topic": "SAP Security"})
    assert create_resp.status_code == 201
    detail = create_resp.json()
    mock_id = detail["session"]["id"]
    ex1 = detail["exchanges"][0]
    assert "SAP" in ex1["question_text"]

    # Submit answer -> offline rubric evaluates with score, missing concepts, improved answer
    ans1 = await client.post(
        f"/api/mock/sessions/{mock_id}/exchanges/{ex1['id']}/answer",
        json={"user_answer": "SAP authorization uses PFCG roles and authorization objects checked via SU53."},
    )
    assert ans1.status_code == 200
    ev1 = ans1.json()["evaluation"]
    assert ev1["evaluation_mode"] == "local_rubric"
    assert 0 <= ev1["score"] <= 100
    assert isinstance(ev1["missing_concepts"], list)
    assert len(ev1["improved_answer"]) > 20

    # Next question with injected LLM provider
    monkeypatch.setattr(ws_manager, "llm_provider_factory", lambda _p=None, _m=None: FakeMockLLM())
    next_q = await client.post(f"/api/mock/sessions/{mock_id}/next-question")
    assert next_q.status_code == 201
    ex2 = next_q.json()
    assert ex2["question_text"] != ex1["question_text"]

    ans2 = await client.post(
        f"/api/mock/sessions/{mock_id}/exchanges/{ex2['id']}/answer",
        json={"user_answer": "Always use parameterized queries."},
    )
    assert ans2.status_code == 200
    ev2 = ans2.json()["evaluation"]
    assert ev2["evaluation_mode"] == "llm"
    assert ev2["score"] == 84
    assert "least privilege DB account" in ev2["missing_concepts"]

    # End mock session & verify performance tracking
    end_resp = await client.post(f"/api/mock/sessions/{mock_id}/end")
    assert end_resp.status_code == 200
    assert end_resp.json()["ended_at"] is not None

    perf = (await client.get("/api/mock/performance")).json()
    assert perf["total_sessions"] == 1
    assert perf["total_evaluated"] == 2
    assert perf["overall_average_score"] is not None
    assert len(perf["score_trend"]) == 1

    # Spoken answer transcription endpoint
    monkeypatch.setattr(ws_manager, "stt_provider_factory", lambda: FakeMockSTT())
    tr_resp = await client.post("/api/mock/transcribe", content=b"\x01\x02" * 4000)
    assert tr_resp.status_code == 200
    assert "parameterized queries" in tr_resp.json()["text"]

    # STRICT ISOLATION CHECK: Mock sessions must NEVER appear in live sessions or live history!
    live_sessions = (await client.get("/api/sessions/")).json()
    live_history = (await client.get("/api/history/")).json()
    assert live_sessions == []
    assert live_history == []

    # Delete mock session cleanly
    assert (await client.delete(f"/api/mock/sessions/{mock_id}")).status_code == 204
    assert (await client.get(f"/api/mock/sessions/{mock_id}")).status_code == 404
