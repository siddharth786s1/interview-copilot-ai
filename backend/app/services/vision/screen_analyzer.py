"""
ScreenAnalyzerService — Permitted visual screen reader & multimodal analyzer.

Validates user-shared screen snapshots (JPEG/PNG/WebP), analyzes what is visible
on screen (coding prompts, architecture diagrams, SQL schemas, slides, error logs)
using the configured multimodal LLMProvider, decides whether an actionable reply
is needed (in auto_mode), and produces structured interview-ready guidance.
"""
import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from app.core.exceptions import ValidationError
from app.services.answer_generation.base import (
    AnswerContext,
    LLMProvider,
    LLMProviderError,
)
from app.services.answer_generation.context_manager import ContextManager
from app.services.answer_generation.service import extract_keywords

logger = logging.getLogger(__name__)

MAX_SCREEN_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}


@dataclass
class ScreenAnalysisResult:
    actionable: bool
    topic: str
    screen_summary: str
    answer_text: str
    model_used: str
    style: str
    ttft_ms: int
    generation_time_ms: int
    keywords: List[str] = field(default_factory=list)


def validate_screen_image(data: bytes, content_type: Optional[str]) -> str:
    """Validate screenshot bytes, size, MIME type, and image magic header."""
    if not data:
        raise ValidationError("Screen image payload is empty.")
    if len(data) > MAX_SCREEN_IMAGE_BYTES:
        raise ValidationError("Screen image exceeds 5 MB limit.")

    mime = (content_type or "").split(";")[0].strip().lower()
    if mime == "image/jpg":
        mime = "image/jpeg"
    if mime and mime not in ALLOWED_IMAGE_MIMES:
        raise ValidationError(f"Unsupported image MIME type '{mime}'. Allowed: JPEG, PNG, WebP.")

    # Verify magic bytes strictly
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"

    raise ValidationError("Uploaded bytes do not match a valid JPEG, PNG, or WebP image.")


def parse_screen_response(
    raw_text: str,
    auto_mode: bool,
    fallback_topic: str,
) -> Tuple[bool, str, str, str]:
    """
    Parse structured metadata line from the vision LLM response.
    Returns (actionable, topic, screen_summary, clean_answer_body).
    """
    text = raw_text.strip()
    if not text:
        return False, fallback_topic, "Empty screen response.", ""

    lines = text.splitlines()
    first_line = lines[0].strip()
    rest = "\n".join(lines[1:]).strip()

    # Check for explicit ACTIONABLE: NO
    no_match = re.match(
        r"^\[?ACTIONABLE\s*:\s*NO(?:\s*\|\s*(?:SUMMARY|TOPIC)\s*:\s*(.+?))?\]?$",
        first_line,
        re.I,
    )
    if auto_mode and no_match:
        summary = (no_match.group(1) or rest or "Ordinary screen view; no question detected.").strip()
        return False, "No action needed", summary[:400], ""

    # Check for ACTIONABLE: YES | TOPIC: ...
    yes_match = re.match(
        r"^\[?ACTIONABLE\s*:\s*YES(?:\s*\|\s*(?:TOPIC|SUMMARY)\s*:\s*(.+?))?\]?$",
        first_line,
        re.I,
    )
    if yes_match:
        topic = (yes_match.group(1) or fallback_topic).strip().strip("[]")
        body = rest if rest else text
        summary = f"Screen shows: {topic}. {body[:350]}"
        return True, topic[:180], summary, body

    # Check for TOPIC: ... header (manual mode)
    topic_match = re.match(r"^\[?TOPIC\s*:\s*(.+?)\]?$", first_line, re.I)
    if topic_match:
        topic = topic_match.group(1).strip().strip("[]")
        body = rest if rest else text
        summary = f"Screen shows: {topic}. {body[:350]}"
        return True, topic[:180], summary, body

    # Fallback: treat as actionable with clean topic
    summary = f"Screen shows: {fallback_topic}. {text[:350]}"
    return True, fallback_topic[:180], summary, text


class ScreenAnalyzerService:
    """Analyzes permitted screen captures with a multimodal LLMProvider."""

    def __init__(
        self,
        provider: LLMProvider,
        context_manager: Optional[ContextManager] = None,
        timeout_seconds: float = 30.0,
    ):
        self.provider = provider
        self.context_manager = context_manager or ContextManager()
        self.timeout_seconds = timeout_seconds

    async def analyze_screen(
        self,
        image_bytes: bytes,
        image_mime_type: str,
        context: AnswerContext,
        custom_prompt: Optional[str] = None,
        auto_mode: bool = False,
    ) -> ScreenAnalysisResult:
        """
        Inspect the shared screen image and return structured interview guidance.
        In auto_mode=True, replies only if actionable interview content is visible.
        """
        base_system, base_user = self.context_manager.build_prompts(context)

        if auto_mode:
            vision_rules = (
                "\n\nSCREEN READER AUTO-WATCH MODE:\n"
                "Inspect the attached screenshot carefully. Decide if the screen currently displays "
                "ACTIONABLE interview content that warrants a reply — such as a coding challenge, "
                "algorithm prompt, SQL query/schema, architecture/system design diagram, error stack trace, "
                "interview slide question, or technical whiteboard.\n"
                "- If the screen ONLY shows an ordinary video call grid, blank desktop, normal chat window, "
                "or the Interview Copilot AI dashboard itself with no new technical problem, respond with EXACTLY one line:\n"
                "ACTIONABLE: NO | SUMMARY: <1 short sentence describing what is visible>\n"
                "- If actionable technical/interview content IS visible, respond starting with:\n"
                "ACTIONABLE: YES | TOPIC: <short 4-10 word title of the problem/question seen>\n"
                "followed by a blank line and your structured, grounded answer."
            )
        else:
            vision_rules = (
                "\n\nSCREEN READER MANUAL ANALYSIS MODE:\n"
                "Read and analyze everything relevant visible in the attached screenshot (code, problem statement, "
                "diagram, SQL table, error message, or slide). Start with a concise first line:\n"
                "TOPIC: <short 4-10 word summary of what is on screen>\n"
                "followed by a blank line and your clear, structured interview answer."
            )

        system_prompt = base_system + vision_rules

        focus_note = (
            f"Candidate's specific question about the screen: {custom_prompt.strip()}"
            if custom_prompt and custom_prompt.strip()
            else "Analyze what is shown on the shared screen and help the candidate answer or explain it clearly."
        )
        user_prompt = f"{base_user}\n\n### VISUAL SCREEN ANALYSIS REQUEST\n{focus_note}"

        t0 = time.perf_counter()
        ttft_ms: Optional[int] = None
        chunks: List[str] = []
        max_tokens = 800 if context.style == "short" else 1400

        try:
            async with asyncio.timeout(self.timeout_seconds):
                async for token in self.provider.stream_generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_tokens=max_tokens,
                    temperature=0.25,
                    image_bytes=image_bytes,
                    image_mime_type=image_mime_type,
                ):
                    if not token:
                        continue
                    if ttft_ms is None:
                        ttft_ms = int((time.perf_counter() - t0) * 1000)
                    chunks.append(token)
        except TimeoutError as exc:
            raise LLMProviderError(
                provider=self.provider.name,
                message=f"Screen analysis timed out after {self.timeout_seconds}s.",
                code="LLM_TIMEOUT",
                retryable=True,
            ) from exc

        total_ms = int((time.perf_counter() - t0) * 1000)
        raw_output = "".join(chunks).strip()
        fallback_topic = (
            custom_prompt.strip()[:120]
            if custom_prompt and custom_prompt.strip()
            else "Screen Analysis"
        )

        actionable, topic, screen_summary, clean_answer = parse_screen_response(
            raw_output, auto_mode=auto_mode, fallback_topic=fallback_topic
        )

        return ScreenAnalysisResult(
            actionable=actionable,
            topic=topic,
            screen_summary=screen_summary,
            answer_text=clean_answer,
            model_used=f"{self.provider.name}:{self.provider.model_name}",
            style=context.style,
            ttft_ms=ttft_ms if ttft_ms is not None else total_ms,
            generation_time_ms=total_ms,
            keywords=extract_keywords(topic, clean_answer) if actionable else [],
        )
