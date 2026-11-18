"""
AnswerGenerationService — Orchestrates streaming LLM answer generation with
timeout handling, retry logic, per-session task cancellation, keyword extraction,
and latency measurement.
"""
import asyncio
import logging
import re
import time
from typing import Awaitable, Callable, Dict, List, Optional, Set

from app.services.answer_generation.base import (
    AnswerContext,
    AnswerGenerationResult,
    LLMProvider,
    LLMProviderError,
)
from app.services.answer_generation.context_manager import ContextManager
from app.services.question_detection.patterns import TECHNICAL_KEYWORDS

logger = logging.getLogger(__name__)


def extract_keywords(question: str, answer: str, max_keywords: int = 8) -> List[str]:
    """Extract important technical and topical keywords from the Q&A text."""
    combined = f"{question} {answer}".lower()
    found: List[str] = []
    for kw in sorted(TECHNICAL_KEYWORDS, key=len, reverse=True):
        if re.search(rf"\b{re.escape(kw)}\b", combined):
            label = kw.upper() if len(kw) <= 4 else kw.title()
            if label not in found:
                found.append(label)
        if len(found) >= max_keywords:
            break
    return found


class AnswerGenerationService:
    """
    Generates streaming, context-grounded interview answers behind an LLMProvider interface.
    """

    def __init__(
        self,
        provider: LLMProvider,
        context_manager: Optional[ContextManager] = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 1,
        retry_delay_seconds: float = 0.4,
    ):
        self.provider = provider
        self.context_manager = context_manager or ContextManager()
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        self._active_tasks: Dict[str, Set[asyncio.Task]] = {}
        self.ttft_samples_ms: List[int] = []
        self.total_latency_samples_ms: List[int] = []

    def register_task(self, session_id: str, task: asyncio.Task) -> None:
        tasks = self._active_tasks.setdefault(session_id, set())
        tasks.add(task)
        task.add_done_callback(lambda t: tasks.discard(t))

    def cancel_session_tasks(self, session_id: str) -> int:
        """Cancel all in-flight answer generation tasks for a session."""
        tasks = list(self._active_tasks.pop(session_id, set()))
        cancelled = 0
        for task in tasks:
            if not task.done():
                task.cancel()
                cancelled += 1
        if cancelled:
            logger.info("Cancelled %d active answer generation task(s) for session %s", cancelled, session_id)
        return cancelled

    async def generate_answer(
        self,
        context: AnswerContext,
        on_chunk: Optional[Callable[[str, str], Awaitable[None]]] = None,
    ) -> AnswerGenerationResult:
        """
        Stream an answer from the configured LLMProvider with timeout & retry.

        Args:
            context: Fully assembled AnswerContext.
            on_chunk: Optional async callback `(question_id, text_chunk)` invoked per streamed chunk.

        Raises:
            LLMProviderError: On timeout, rate limit, auth/config failure, or provider outage.
            asyncio.CancelledError: If cancelled because the session ended.
        """
        system_prompt, user_prompt = self.context_manager.build_prompts(context)
        max_tokens = 600 if context.style == "short" else 1400

        attempt = 0
        last_error: Optional[LLMProviderError] = None

        while attempt <= self.max_retries:
            t_start = time.perf_counter()
            ttft_ms: Optional[int] = None
            chunks: List[str] = []

            try:
                async with asyncio.timeout(self.timeout_seconds):
                    async for token in self.provider.stream_generate(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        max_tokens=max_tokens,
                        temperature=0.3,
                    ):
                        if not token:
                            continue
                        if ttft_ms is None:
                            ttft_ms = int((time.perf_counter() - t_start) * 1000)
                        chunks.append(token)
                        if on_chunk is not None:
                            await on_chunk(context.question_id, token)

                total_ms = int((time.perf_counter() - t_start) * 1000)
                full_text = "".join(chunks).strip()
                if not full_text:
                    raise LLMProviderError(
                        provider=self.provider.name,
                        message="LLM returned an empty response.",
                        code="LLM_EMPTY_RESPONSE",
                        retryable=True,
                    )

                # Enforce grounding disclaimer prefix if personal background requested without resume
                if (
                    context.needs_customization
                    and "customization" not in full_text.lower()
                    and "resume" not in full_text.lower()
                ):
                    prefix = "[Needs customization — upload your resume for personalized details]\n\n"
                    full_text = prefix + full_text

                final_ttft = ttft_ms if ttft_ms is not None else total_ms
                self.ttft_samples_ms.append(final_ttft)
                self.total_latency_samples_ms.append(total_ms)

                return AnswerGenerationResult(
                    question_id=context.question_id,
                    style=context.style,
                    answer_text=full_text,
                    model_used=f"{self.provider.name}:{self.provider.model_name}",
                    ttft_ms=final_ttft,
                    generation_time_ms=total_ms,
                    keywords=extract_keywords(context.question, full_text),
                    needs_customization=context.needs_customization,
                )

            except asyncio.CancelledError:
                logger.info("Answer generation cancelled for question %s", context.question_id)
                raise
            except TimeoutError as exc:
                last_error = LLMProviderError(
                    provider=self.provider.name,
                    message=f"Answer generation timed out after {self.timeout_seconds}s.",
                    code="LLM_TIMEOUT",
                    retryable=True,
                )
                logger.warning(
                    "Answer generation timeout (attempt %d/%d) for question %s",
                    attempt + 1,
                    self.max_retries + 1,
                    context.question_id,
                )
                if attempt < self.max_retries:
                    attempt += 1
                    await asyncio.sleep(self.retry_delay_seconds)
                    continue
                raise last_error from exc
            except LLMProviderError as err:
                last_error = err
                logger.warning(
                    "LLM error (%s, retryable=%s, attempt %d/%d): %s",
                    err.code,
                    err.retryable,
                    attempt + 1,
                    self.max_retries + 1,
                    err.message,
                )
                if err.retryable and attempt < self.max_retries and not chunks:
                    attempt += 1
                    await asyncio.sleep(self.retry_delay_seconds)
                    continue
                raise

        assert last_error is not None
        raise last_error
