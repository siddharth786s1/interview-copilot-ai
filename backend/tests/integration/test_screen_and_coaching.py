"""
Unit + Integration tests for:
1. Permitted Visual Screen Reader / Auto-Watch (validation, parsing, REST endpoint, screen-context injection)
2. Gemini Structured Output & Personal Coaching Profile (Settings persistence + ContextManager prompt injection)
"""
from typing import AsyncIterator, List, Optional, Tuple
import pytest

from app.api.websockets.manager import ws_manager
from app.core.exceptions import ValidationError
from app.services.answer_generation.base import LLMProvider
from app.services.vision.screen_analyzer import (
    MAX_SCREEN_IMAGE_BYTES,
    parse_screen_response,
    validate_screen_image,
)
from tests.conftest import TestAsyncSessionLocal


FAKE_JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"
FAKE_PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
FAKE_WEBP_BYTES = b"RIFF\x1a\x00\x00\x00WEBPVP8 \x0e\x00\x00\x00"


class RecordingMultimodalProvider(LLMProvider):
    """Test double that records prompts + image bytes and returns scripted outputs."""

    def __init__(self, responses: List[str]):
        self._responses = list(responses)
        self.calls: List[Tuple[str, str, Optional[bytes], str]] = []

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return "gemini-3.5-flash-lite-test"

    async def stream_generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 800,
        temperature: float = 0.3,
        image_bytes: Optional[bytes] = None,
        image_mime_type: str = "image/jpeg",
    ) -> AsyncIterator[str]:
        self.calls.append((system_prompt, user_prompt, image_bytes, image_mime_type))
        reply = self._responses.pop(0) if self._responses else "**Direct Answer**\nDefault test reply."
        for part in reply.split(" "):
            yield part + " "


def test_validate_screen_image_accepts_valid_formats_and_rejects_malicious():
    assert validate_screen_image(FAKE_JPEG_BYTES, "image/jpeg") == "image/jpeg"
    assert validate_screen_image(FAKE_JPEG_BYTES, "image/jpg") == "image/jpeg"
    assert validate_screen_image(FAKE_PNG_BYTES, "image/png") == "image/png"
    assert validate_screen_image(FAKE_WEBP_BYTES, "image/webp") == "image/webp"

    with pytest.raises(ValidationError):
        validate_screen_image(b"", "image/jpeg")

    with pytest.raises(ValidationError):
        validate_screen_image(b"<html>not an image</html>", "image/png")

    with pytest.raises(ValidationError):
        validate_screen_image(FAKE_JPEG_BYTES, "application/pdf")

    with pytest.raises(ValidationError):
        validate_screen_image(b"\xff\xd8\xff" + b"a" * (MAX_SCREEN_IMAGE_BYTES + 10), "image/jpeg")


def test_parse_screen_response_auto_and_manual_modes():
    actionable, topic, summary, body = parse_screen_response(
        "ACTIONABLE: NO | SUMMARY: Ordinary Zoom gallery grid with no code visible.",
        auto_mode=True,
        fallback_topic="Screen Analysis",
    )
    assert actionable is False
    assert "Zoom gallery grid" in summary
    assert body == ""

    actionable2, topic2, summary2, body2 = parse_screen_response(
        "ACTIONABLE: YES | TOPIC: Optimize SQL Query Missing Index\n\n"
        "**Direct Answer**\nAdd a composite index on (user_id, created_at).\n\n"
        "**Key Points**\n- Eliminates full table scan",
        auto_mode=True,
        fallback_topic="Screen Analysis",
    )
    assert actionable2 is True
    assert topic2 == "Optimize SQL Query Missing Index"
    assert "composite index" in body2
    assert "Optimize SQL Query Missing Index" in summary2

    actionable3, topic3, _, body3 = parse_screen_response(
        "TOPIC: Two Sum HashMap Solution\n\n**Direct Answer**\nUse a hash map for O(n) lookup.",
        auto_mode=False,
        fallback_topic="Screen Analysis",
    )
    assert actionable3 is True
    assert topic3 == "Two Sum HashMap Solution"
    assert "O(n) lookup" in body3


@pytest.mark.asyncio
async def test_screen_analysis_auto_manual_and_voice_screen_context_injection(client, monkeypatch):
    monkeypatch.setattr(ws_manager, "db_session_factory", TestAsyncSessionLocal)

    scripted_provider = RecordingMultimodalProvider(
        responses=[
            # 1) Auto-Watch scan on non-actionable screen
            "ACTIONABLE: NO | SUMMARY: Video call window with two participants and no technical prompt.",
            # 2) Auto-Watch scan on coding/SQL screen
            "ACTIONABLE: YES | TOPIC: Fix N+1 Query in SQLAlchemy\n\n"
            "**Direct Answer**\nUse `selectinload()` to eagerly batch-fetch child rows in 2 queries.\n\n"
            "**Key Points**\n- Prevents 1 query per parent row\n- Keeps memory overhead low",
            # 3) Subsequent voice/manual follow-up question (should see CURRENT SCREEN CONTEXT!)
            "**Direct Answer**\nUse `joinedload()` when returning a small 1-to-1 relation and `selectinload()` for 1-to-many.",
            # 4) Manual screen analysis with custom user prompt
            "TOPIC: Explain SAP PFCG Role Architecture\n\n"
            "**Direct Answer**\nThe diagram illustrates PFCG single and composite roles mapped to SU24 objects.",
        ]
    )
    monkeypatch.setattr(ws_manager, "llm_provider_factory", lambda _p=None, _m=None: scripted_provider)

    # Create session
    s_res = await client.post("/api/sessions/", json={"title": "Screen Reader Integration", "type": "technical"})
    assert s_res.status_code == 201
    session_id = s_res.json()["id"]

    # Invalid image rejected cleanly with 400
    bad_res = await client.post(
        f"/api/sessions/{session_id}/analyze-screen",
        files={"image": ("bad.png", b"not-a-real-image", "image/png")},
        data={"auto_mode": "false"},
    )
    assert bad_res.status_code == 400

    # 1) Auto-Watch non-actionable -> no question/answer created, screen context still updated
    r1 = await client.post(
        f"/api/sessions/{session_id}/analyze-screen",
        files={"image": ("frame1.jpg", FAKE_JPEG_BYTES, "image/jpeg")},
        data={"auto_mode": "true"},
    )
    assert r1.status_code == 200
    body1 = r1.json()
    assert body1["actionable"] is False
    assert body1["question"] is None
    assert body1["answer"] is None
    assert "Video call window" in (ws_manager.get_screen_context(session_id) or "")

    # 2) Auto-Watch actionable -> persists DetectedQuestion(type="screen") + GeneratedAnswer
    r2 = await client.post(
        f"/api/sessions/{session_id}/analyze-screen",
        files={"image": ("frame2.jpg", FAKE_JPEG_BYTES, "image/jpeg")},
        data={"auto_mode": "true", "style": "short"},
    )
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["actionable"] is True
    assert body2["topic"] == "Fix N+1 Query in SQLAlchemy"
    assert body2["question"]["question_type"] == "screen"
    assert "selectinload()" in body2["answer"]["answer_text"]
    assert scripted_provider.calls[1][2] == FAKE_JPEG_BYTES
    assert scripted_provider.calls[1][3] == "image/jpeg"

    # Verify persisted in DB
    q_list = (await client.get(f"/api/sessions/{session_id}/questions")).json()
    assert len(q_list) == 1
    assert q_list[0]["question_type"] == "screen"

    # 3) Voice / manual follow-up question automatically receives CURRENT SCREEN CONTEXT
    mq = await client.post(
        f"/api/sessions/{session_id}/questions",
        json={"question_text": "When should I use joinedload instead?", "auto_generate": False},
    )
    assert mq.status_code == 201
    mq_id = mq.json()["id"]

    ans_res = await client.post(
        f"/api/sessions/{session_id}/questions/{mq_id}/answer",
        json={"style": "short"},
    )
    assert ans_res.status_code == 201
    # Check 3rd LLM call received screen context in user_prompt
    _, third_user_prompt, third_img, _ = scripted_provider.calls[2]
    assert third_img is None
    assert "CURRENT SCREEN CONTEXT (VISIBLE ON SHARED SCREEN)" in third_user_prompt
    assert "Fix N+1 Query in SQLAlchemy" in third_user_prompt

    # 4) Manual screen analysis with custom prompt
    r4 = await client.post(
        f"/api/sessions/{session_id}/analyze-screen",
        files={"image": ("frame4.png", FAKE_PNG_BYTES, "image/png")},
        data={"auto_mode": "false", "prompt": "Explain this SAP role diagram"},
    )
    assert r4.status_code == 200
    body4 = r4.json()
    assert body4["actionable"] is True
    assert body4["topic"] == "Explain SAP PFCG Role Architecture"
    assert scripted_provider.calls[3][3] == "image/png"

    # Cleanup clears screen context
    await ws_manager.cleanup_session(session_id)
    assert ws_manager.get_screen_context(session_id) is None


@pytest.mark.asyncio
async def test_settings_gemini_coaching_profile_persists_and_injects_into_prompts(client, monkeypatch):
    monkeypatch.setattr(ws_manager, "db_session_factory", TestAsyncSessionLocal)

    provider = RecordingMultimodalProvider(
        responses=[
            "**Direct Answer**\nParameterize all SQL statements.\n\n**Key Points**\n- Bind variables strictly",
        ]
    )
    monkeypatch.setattr(ws_manager, "llm_provider_factory", lambda _p=None, _m=None: provider)

    # Save coaching profile in Settings
    patch_res = await client.patch(
        "/api/settings/",
        json={
            "structured_output": True,
            "target_role": "Senior Application Security Engineer",
            "custom_instructions": "Lead with OWASP mitigation and keep bullets under 12 words.",
            "few_shot_examples": [
                {
                    "question": "What is IDOR?",
                    "ideal_answer": "**Direct Answer**\nBroken object-level authorization.\n**Key Points**\n- Enforce server-side ownership checks",
                }
            ],
        },
    )
    assert patch_res.status_code == 200
    saved = patch_res.json()
    assert saved["structured_output"] is True
    assert saved["target_role"] == "Senior Application Security Engineer"
    assert "OWASP mitigation" in saved["custom_instructions"]
    assert len(saved["few_shot_examples"]) == 1
    assert saved["few_shot_examples"][0]["question"] == "What is IDOR?"

    # Verify GET /api/settings/ returns the exact persisted coaching profile
    get_res = await client.get("/api/settings/")
    assert get_res.status_code == 200
    assert get_res.json()["target_role"] == "Senior Application Security Engineer"
    assert len(get_res.json()["few_shot_examples"]) == 1

    # Trigger answer generation and verify prompts contain structured rules, role, instructions, and few-shot example
    s_res = await client.post("/api/sessions/", json={"title": "Coaching Prompt Test", "type": "technical"})
    session_id = s_res.json()["id"]
    q_res = await client.post(
        f"/api/sessions/{session_id}/questions",
        json={"question_text": "How do you prevent SQL injection?", "auto_generate": False},
    )
    q_id = q_res.json()["id"]

    a_res = await client.post(
        f"/api/sessions/{session_id}/questions/{q_id}/answer",
        json={"style": "short"},
    )
    assert a_res.status_code == 201

    sys_prompt, usr_prompt, _, _ = provider.calls[0]
    assert "STRUCTURED RESPONSE FORMAT (REQUIRED)" in sys_prompt
    assert "**Direct Answer**" in sys_prompt
    assert "Senior Application Security Engineer" in sys_prompt
    assert "Lead with OWASP mitigation" in sys_prompt
    assert "CANDIDATE PREFERRED ANSWER EXAMPLES" in usr_prompt
    assert "What is IDOR?" in usr_prompt
