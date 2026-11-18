"""
Structured logging setup with automatic API key / credential redaction.
"""
import logging
import re
import sys

from app.core.config import settings

_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{12,}"),
    re.compile(r"AIza[A-Za-z0-9_\-]{20,}"),
    re.compile(r"(api[_-]?key|token|secret|authorization)\s*[=:]\s*['\"]?[^\s'\",;]+", re.I),
]


def redact_secrets(text: str) -> str:
    masked = text
    for pat in _SECRET_PATTERNS:
        masked = pat.sub("[REDACTED]", masked)
    return masked


class SecretRedactionFilter(logging.Filter):
    """Scrub API keys and secrets from log messages before emission."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            rendered = record.getMessage()
            redacted = redact_secrets(rendered)
            if redacted != rendered:
                record.msg = redacted
                record.args = ()
        except Exception:
            pass
        return True


def setup_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.addFilter(SecretRedactionFilter())
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [handler]

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("multipart").setLevel(logging.WARNING)
