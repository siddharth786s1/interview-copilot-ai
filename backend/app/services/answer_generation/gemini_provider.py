"""
Google Gemini LLM provider using the current google-genai SDK with async streaming.
"""
import logging
from typing import AsyncIterator, Optional

from app.core.config import settings
from app.services.answer_generation.base import LLMProvider, LLMProviderError

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """Streaming Gemini provider backed by google-genai."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self._api_key = api_key if api_key is not None else settings.google_api_key
        self._model = model or settings.gemini_model or "gemini-3.5-flash-lite"
        self._client = None

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model

    def _get_client(self):
        if not self._api_key or "your-google-api-key" in self._api_key:
            raise LLMProviderError(
                provider="gemini",
                message="GOOGLE_API_KEY is not configured in .env. Add your key from https://aistudio.google.com.",
                code="LLM_CONFIG_ERROR",
                retryable=False,
            )
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self._api_key)
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
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        if image_bytes:
            contents = [
                types.Part.from_bytes(data=image_bytes, mime_type=image_mime_type),
                user_prompt,
            ]
        else:
            contents = user_prompt

        try:
            stream = await client.aio.models.generate_content_stream(
                model=self._model,
                contents=contents,
                config=config,
            )
            async for chunk in stream:
                text = getattr(chunk, "text", None)
                if text:
                    yield text
        except LLMProviderError:
            raise
        except Exception as exc:
            err_str = str(exc)
            status_code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
            if status_code == 429 or "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                raise LLMProviderError(
                    provider="gemini",
                    message="Gemini API rate limit reached (429). Retrying or try again shortly.",
                    code="LLM_RATE_LIMIT",
                    retryable=True,
                    status_code=429,
                ) from exc
            if status_code in (401, 403) or "API_KEY_INVALID" in err_str:
                raise LLMProviderError(
                    provider="gemini",
                    message="Gemini API key is invalid or unauthorized.",
                    code="LLM_AUTH_ERROR",
                    retryable=False,
                    status_code=status_code or 401,
                ) from exc
            is_server_err = (
                (isinstance(status_code, int) and status_code >= 500)
                or "500" in err_str
                or "503" in err_str
                or "UNAVAILABLE" in err_str
            )
            raise LLMProviderError(
                provider="gemini",
                message=f"Gemini generation failed: {err_str[:240]}",
                code="LLM_PROVIDER_ERROR",
                retryable=is_server_err,
                status_code=status_code if isinstance(status_code, int) else None,
            ) from exc
