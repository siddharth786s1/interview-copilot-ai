"""
Application configuration loaded from environment variables.
"""
import json
import os
from pathlib import Path
from typing import Any, List, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve repository root so .env and storage/ work identically regardless of CWD
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_STORAGE = os.getenv(
    "STORAGE_PATH",
    "/tmp/interview_copilot_storage" if os.getenv("VERCEL") else (_REPO_ROOT / "storage").as_posix(),
)
_DEFAULT_DB_URL = f"sqlite+aiosqlite:///{(Path(_DEFAULT_STORAGE) / 'interview_copilot.db').as_posix()}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(_REPO_ROOT / ".env"), ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_secret: str = "change-me-random-string"
    environment: str = "development"
    log_level: str = "INFO"

    # CORS — supports JSON list or comma-separated origins + optional regex (e.g. https://.*\.vercel\.app)
    cors_origins: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    cors_origin_regex: Optional[str] = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: Any) -> List[str]:
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        return [str(v).strip().rstrip("/") for v in parsed if str(v).strip()]
                except json.JSONDecodeError:
                    pass
            return [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(v).strip().rstrip("/") for v in value if str(v).strip()]
        return ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Storage
    storage_path: str = _DEFAULT_STORAGE

    # LLM
    llm_provider: str = "gemini"  # gemini | openai
    google_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # STT
    stt_provider: str = "whisper"  # whisper | deepgram | openai_whisper
    whisper_model_size: str = "base"
    deepgram_api_key: str = ""

    # Language
    default_language: str = "en"

    # Answer defaults
    default_answer_style: str = "short"  # short | detailed | practical | stepbystep
    default_technical_depth: str = "medium"  # low | medium | high

    # Database
    database_url: str = _DEFAULT_DB_URL

    # Server
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000


settings = Settings()
