"""
OpenAI / OpenAI-compatible LLM provider using AsyncOpenAI with streaming.
"""
import logging
from typing import AsyncIterator, Optional

from app.core.config import settings
from app.services.answer_generation.base import LLMProvider, LLMProviderError

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """Streaming OpenAI (and OpenAI-compatible) provider."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self._api_key = api_key if api_key is not None else settings.openai_api_key
        self._model = model or settings.openai_model or "gpt-4o-mini"
        self._base_url = base_url
        self._client = None

    @property
    def name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model

    def _get_client(self):
        if not self._api_key or "your-openai-api-key" in self._api_key:
            raise LLMProviderError(
                provider="openai",
                message="OPENAI_API_KEY is not configured in .env.",
                code="LLM_CONFIG_ERROR",
                retryable=False,
            )
        if self._client is None:
            from openai import AsyncOpenAI

            kwargs = {"api_key": self._api_key}
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._client = AsyncOpenAI(**kwargs)
        return self._client

    async def stream_generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 800,
        temperature: float = 0.3,
        image_bytes: Optional[bytes] = None,
        image_mime_type: str = "image/jpeg",
    ) -> AsyncIterator[str]:
        client = self._get_client()
        import base64
        import openai

        if image_bytes:
            b64 = base64.b64encode(image_bytes).decode("ascii")
            user_content = [
                {"type": "text", "text": user_prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{image_mime_type};base64,{b64}"},
                },
            ]
        else:
            user_content = user_prompt

        try:
            stream = await client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
            )
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                content = getattr(delta, "content", None)
                if content:
                    yield content
        except openai.RateLimitError as exc:
            raise LLMProviderError(
                provider="openai",
                message="OpenAI API rate limit reached (429).",
                code="LLM_RATE_LIMIT",
                retryable=True,
                status_code=429,
            ) from exc
        except openai.AuthenticationError as exc:
            raise LLMProviderError(
                provider="openai",
                message="OpenAI API key is invalid or unauthorized.",
                code="LLM_AUTH_ERROR",
                retryable=False,
                status_code=401,
            ) from exc
        except openai.APITimeoutError as exc:
            raise LLMProviderError(
                provider="openai",
                message="OpenAI API request timed out.",
                code="LLM_TIMEOUT",
                retryable=True,
            ) from exc
        except openai.APIStatusError as exc:
            retryable = exc.status_code >= 500
            raise LLMProviderError(
                provider="openai",
                message=f"OpenAI API error ({exc.status_code}): {str(exc)[:200]}",
                code="LLM_PROVIDER_ERROR",
                retryable=retryable,
                status_code=exc.status_code,
            ) from exc
        except Exception as exc:
            raise LLMProviderError(
                provider="openai",
                message=f"OpenAI generation failed: {str(exc)[:240]}",
                code="LLM_PROVIDER_ERROR",
                retryable=True,
            ) from exc
