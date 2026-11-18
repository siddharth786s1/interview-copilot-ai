"""
LLM Provider interface and shared data structures for AI Answer Generation.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator, Dict, List, Optional

from app.core.exceptions import ProviderError


class LLMProviderError(ProviderError):
    """Structured LLM provider error with retryability and error code metadata."""

    def __init__(
        self,
        provider: str,
        message: str,
        code: str = "LLM_PROVIDER_ERROR",
        retryable: bool = False,
        status_code: Optional[int] = None,
    ):
        super().__init__(provider, message)
        self.code = code
        self.retryable = retryable
        self.status_code = status_code


@dataclass
class AnswerContext:
    """All inputs assembled by ContextManager for generating a grounded interview answer."""
    session_id: str
    question_id: str
    question: str
    question_type: str = "direct"
    session_type: str = "general"
    style: str = "short"  # short | detailed | practical | stepbystep
    technical_depth: str = "medium"  # low | medium | high
    recent_transcript: List[Dict[str, str]] = field(default_factory=list)
    prior_qa: List[Dict[str, str]] = field(default_factory=list)
    resume_summary: Optional[Dict[str, object]] = None
    kb_excerpts: List[Dict[str, str]] = field(default_factory=list)
    expand_previous_answer: Optional[str] = None
    needs_customization: bool = False
    # Structured answer coaching & live screen context
    structured_output: bool = True
    target_role: str = ""
    custom_instructions: str = ""
    few_shot_examples: List[Dict[str, str]] = field(default_factory=list)
    screen_context: Optional[str] = None


@dataclass
class AnswerGenerationResult:
    """Completed answer generation output with measured timing metrics."""
    question_id: str
    style: str
    answer_text: str
    model_used: str
    ttft_ms: int
    generation_time_ms: int
    keywords: List[str] = field(default_factory=list)
    needs_customization: bool = False


class LLMProvider(ABC):
    """Provider-independent interface for streaming LLM answer generation."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (e.g. 'gemini', 'openai')."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Model name (e.g. 'gemini-2.0-flash', 'gpt-4o-mini')."""
        ...

    @abstractmethod
    async def stream_generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 800,
        temperature: float = 0.3,
        image_bytes: Optional[bytes] = None,
        image_mime_type: str = "image/jpeg",
    ) -> AsyncIterator[str]:
        """Yield incremental text chunks as the model streams its response (text or multimodal)."""
        if False:  # pragma: no cover — makes type checkers recognize AsyncIterator
            yield ""

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 800,
        temperature: float = 0.3,
        image_bytes: Optional[bytes] = None,
        image_mime_type: str = "image/jpeg",
    ) -> str:
        """Convenience helper that collects all streamed chunks into a single string."""
        chunks: List[str] = []
        kwargs: Dict[str, object] = {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if image_bytes is not None:
            kwargs["image_bytes"] = image_bytes
            kwargs["image_mime_type"] = image_mime_type
        async for chunk in self.stream_generate(**kwargs):  # type: ignore[arg-type]
            chunks.append(chunk)
        return "".join(chunks)
