"""
Unit tests for AnswerGenerationService, ContextManager, Grounding Guard,
all 4 answer styles, timeout/retry/cancellation, and provider config validation.
"""
import asyncio
from typing import AsyncIterator, List, Optional

import pytest

from app.services.answer_generation.base import (
    AnswerContext,
    LLMProvider,
    LLMProviderError,
)
from app.services.answer_generation.context_manager import (
    ContextManager,
    is_personal_background_question,
)
from app.services.answer_generation.gemini_provider import GeminiProvider
from app.services.answer_generation.openai_provider import OpenAIProvider
from app.services.answer_generation.service import (
    AnswerGenerationService,
    extract_keywords,
)


class FakeStreamingLLM(LLMProvider):
    """Configurable streaming LLM test double."""

    def __init__(
        self,
        chunks: Optional[List[str]] = None,
        fail_times: int = 0,
        error: Optional[LLMProviderError] = None,
        delay_per_chunk: float = 0.0,
    ):
        self._chunks = chunks or ["Authentication ", "verifies identity; ", "authorization ", "checks permissions."]
        self._fail_times = fail_times
        self._error = error
        self._delay = delay_per_chunk
        self.calls: List[dict] = []

    @property
    def name(self) -> str:
        return "fake-llm"

    @property
    def model_name(self) -> str:
        return "fake-v1"

    async def stream_generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 800,
        temperature: float = 0.3,
    ) -> AsyncIterator[str]:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "max_tokens": max_tokens,
            }
        )
        if len(self.calls) <= self._fail_times:
            raise self._error or LLMProviderError(
                provider="fake-llm",
                message="Transient 500 error",
                code="LLM_PROVIDER_ERROR",
                retryable=True,
                status_code=500,
            )
        for ch in self._chunks:
            if self._delay > 0:
                await asyncio.sleep(self._delay)
            yield ch


@pytest.mark.asyncio
@pytest.mark.parametrize("style", ["short", "detailed", "practical", "stepbystep"])
async def test_all_four_styles_stream_and_inject_prompt_rules(style: str):
    llm = FakeStreamingLLM(chunks=["Part 1. ", "Part 2."])
    service = AnswerGenerationService(provider=llm)
    ctx = AnswerContext(
        session_id="s1",
        question_id="q1",
        question="What is SQL injection?",
        style=style,
        technical_depth="high",
        recent_transcript=[{"speaker": "Interviewer", "text": "What is SQL injection?"}],
        prior_qa=[{"question": "Tell me about web security.", "answer": "I focus on OWASP Top 10."}],
        kb_excerpts=[{"category": "AppSec", "filename": "owasp.md", "excerpt": "Always use parameterized queries."}],
    )

    streamed: List[str] = []

    async def on_chunk(qid: str, token: str):
        assert qid == "q1"
        streamed.append(token)

    result = await service.generate_answer(ctx, on_chunk=on_chunk)

    assert streamed == ["Part 1. ", "Part 2."]
    assert result.answer_text == "Part 1. Part 2."
    assert result.style == style
    assert result.model_used == "fake-llm:fake-v1"
    assert result.ttft_ms >= 0
    assert result.generation_time_ms >= result.ttft_ms

    # Verify prompt contains style, depth, transcript, prior QA, and KB excerpt
    sys_p = llm.calls[0]["system_prompt"]
    usr_p = llm.calls[0]["user_prompt"]
    assert style.upper().replace("STEPBYSTEP", "STEP-BY-STEP") in sys_p
    assert "TECHNICAL DEPTH: HIGH" in sys_p
    assert "parameterized queries" in usr_p
    assert "OWASP Top 10" in usr_p


@pytest.mark.asyncio
async def test_grounding_guard_refuses_to_fabricate_when_resume_missing():
    assert is_personal_background_question("Tell me about yourself.") is True
    assert is_personal_background_question("Explain your previous project.") is True
    assert is_personal_background_question("What is SQL injection?") is False

    # Even if an LLM forgets to include the disclaimer, service enforces it
    llm = FakeStreamingLLM(chunks=["Start with your current role and highlight key achievements."])
    service = AnswerGenerationService(provider=llm)
    ctx = AnswerContext(
        session_id="s1",
        question_id="q-personal",
        question="Explain your previous project.",
        resume_summary=None,
        needs_customization=True,
    )

    res = await service.generate_answer(ctx)
    assert res.needs_customization is True
    assert "Needs customization" in res.answer_text
    assert "NEVER invent, fabricate" in llm.calls[0]["system_prompt"]
    assert "MISSING PERSONAL CONTEXT DETECTED" in llm.calls[0]["system_prompt"]


@pytest.mark.asyncio
async def test_grounding_with_resume_injects_verified_facts():
    llm = FakeStreamingLLM(chunks=["In my previous project, I built a FastAPI security gateway."])
    cm = ContextManager()
    ctx = AnswerContext(
        session_id="s1",
        question_id="q-proj",
        question="Explain your previous project.",
        resume_summary={
            "filename": "my_resume.pdf",
            "skills": ["Python", "FastAPI", "SAP Security"],
            "projects": ["API Security Gateway"],
        },
        needs_customization=False,
    )
    sys_p, usr_p = cm.build_prompts(ctx)
    assert "MISSING PERSONAL CONTEXT DETECTED" not in sys_p
    assert "API Security Gateway" in usr_p
    assert "SAP Security" in usr_p


@pytest.mark.asyncio
async def test_retry_recovers_from_transient_429_or_500():
    llm = FakeStreamingLLM(
        chunks=["Recovered answer."],
        fail_times=1,
        error=LLMProviderError("fake-llm", "Rate limited", code="LLM_RATE_LIMIT", retryable=True, status_code=429),
    )
    service = AnswerGenerationService(provider=llm, max_retries=1, retry_delay_seconds=0.01)
    ctx = AnswerContext(session_id="s1", question_id="q1", question="What is SQL injection?")

    res = await service.generate_answer(ctx)
    assert res.answer_text == "Recovered answer."
    assert len(llm.calls) == 2


@pytest.mark.asyncio
async def test_non_retryable_auth_error_fails_immediately():
    llm = FakeStreamingLLM(
        fail_times=5,
        error=LLMProviderError("fake-llm", "Invalid API key", code="LLM_AUTH_ERROR", retryable=False, status_code=401),
    )
    service = AnswerGenerationService(provider=llm, max_retries=2, retry_delay_seconds=0.01)
    ctx = AnswerContext(session_id="s1", question_id="q1", question="What is SQL injection?")

    with pytest.raises(LLMProviderError) as exc_info:
        await service.generate_answer(ctx)

    assert exc_info.value.code == "LLM_AUTH_ERROR"
    assert len(llm.calls) == 1  # No wasted retries


@pytest.mark.asyncio
async def test_timeout_retries_then_raises_llm_timeout():
    llm = FakeStreamingLLM(chunks=["Slow..."], delay_per_chunk=0.25)
    service = AnswerGenerationService(
        provider=llm,
        timeout_seconds=0.05,
        max_retries=1,
        retry_delay_seconds=0.01,
    )
    ctx = AnswerContext(session_id="s1", question_id="q1", question="What is SQL injection?")

    with pytest.raises(LLMProviderError) as exc_info:
        await service.generate_answer(ctx)

    assert exc_info.value.code == "LLM_TIMEOUT"
    assert len(llm.calls) == 2


@pytest.mark.asyncio
async def test_cancellation_on_session_end():
    llm = FakeStreamingLLM(chunks=["Chunk1", "Chunk2", "Chunk3"], delay_per_chunk=0.2)
    service = AnswerGenerationService(provider=llm, timeout_seconds=5.0)
    ctx = AnswerContext(session_id="s-cancel", question_id="q1", question="Explain SAP authorization.")

    task = asyncio.create_task(service.generate_answer(ctx))
    service.register_task("s-cancel", task)

    await asyncio.sleep(0.05)
    cancelled_count = service.cancel_session_tasks("s-cancel")
    assert cancelled_count == 1

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_real_providers_raise_config_error_when_key_missing():
    gemini = GeminiProvider(api_key="")
    with pytest.raises(LLMProviderError) as g_err:
        await gemini.generate("sys", "user")
    assert g_err.value.code == "LLM_CONFIG_ERROR"

    openai_p = OpenAIProvider(api_key="")
    with pytest.raises(LLMProviderError) as o_err:
        await openai_p.generate("sys", "user")
    assert o_err.value.code == "LLM_CONFIG_ERROR"


def test_keyword_extraction():
    kws = extract_keywords(
        "Explain the difference between authentication and authorization.",
        "Authentication verifies identity using JWT or OAuth, while authorization enforces RBAC permissions.",
    )
    lower_kws = {k.lower() for k in kws}
    assert "authentication" in lower_kws
    assert "authorization" in lower_kws
    assert "jwt" in lower_kws
    assert "oauth" in lower_kws


def test_conversation_scenario_prompt_formatting():
    cm = ContextManager()
    ctx = AnswerContext(
        session_id="s-conv-prompt",
        question_id="q-conv-1",
        question="In our architecture, we cannot use two-phase commit across microservices.",
        question_type="conversation",
        session_type="technical",
        style="short",
        technical_depth="high",
        target_role="Staff Distributed Systems Architect",
        custom_instructions="Focus on the Saga pattern, outbox pattern, and idempotency keys.",
    )
    system_prompt, user_prompt = cm.build_prompts(ctx)
    assert "co-pilot and coach" in system_prompt
    assert "live conversation" in system_prompt
    assert "TARGET CANDIDATE ROLE: Staff Distributed Systems Architect" in system_prompt
    assert "Saga pattern" in system_prompt
    assert "### INTERVIEWER DISCUSSION POINT / TECHNICAL SCENARIO" in user_prompt
    assert "In our architecture, we cannot use two-phase commit across microservices." in user_prompt


def test_context_manager_injects_dynamic_session_learnings_and_paradigms():
    cm = ContextManager()
    ctx = AnswerContext(
        session_id="s-learn-test",
        question_id="q-learn-1",
        question="Aapka previous project explain karo aur database architecture discuss karo.",
        question_type="conversation",
        session_type="technical",
        recent_transcript=[
            {"speaker": "Interviewer", "text": "Hamare paas high-volume write traffic hai aur PostgreSQL use kar rahe hain."},
            {"speaker": "Interviewer", "text": "Latency SLA under 50ms strictly required hai."},
        ],
        prior_qa=[],
        session_learnings_prompt="### DYNAMIC CONVERSATION MEMORY & LEARNED CONSTRAINTS\n- Detected Dialogue Style: Hinglish\n- Established Session Constraints:\n  * Latency SLA under 50ms strictly required",
        few_shot_examples=[
            {"question": "Sample Q?", "ideal_answer": "**Direct Answer**\nSample A."}
        ],
    )
    system_prompt, user_prompt = cm.build_prompts(ctx)
    assert "BILINGUAL & HINGLISH INTERVIEW RULES" in system_prompt
    assert "### DYNAMIC CONVERSATION MEMORY & LEARNED CONSTRAINTS" in user_prompt
    assert "Latency SLA under 50ms strictly required" in user_prompt
    assert "### CANDIDATE PREFERRED ANSWER EXAMPLES" in user_prompt
