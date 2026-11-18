"""
Factory for instantiating the configured LLMProvider.
"""
from typing import Optional

from app.core.config import settings
from app.services.answer_generation.base import LLMProvider
from app.services.answer_generation.gemini_provider import GeminiProvider
from app.services.answer_generation.openai_provider import OpenAIProvider


def get_llm_provider(
    provider_name: Optional[str] = None,
    model: Optional[str] = None,
) -> LLMProvider:
    name = (provider_name or settings.llm_provider or "gemini").lower()
    if name == "openai":
        return OpenAIProvider(model=model)
    return GeminiProvider(model=model)
