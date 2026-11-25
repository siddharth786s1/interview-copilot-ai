"""
SessionLearner — Synthesizes dynamic conversation context, architectural constraints,
and linguistic style across evolving interview transcripts and prior Q&A.
"""
from dataclasses import dataclass, field
import re
from typing import Dict, List, Optional


HINGLISH_DETECTION_WORDS = {
    "haan", "bilkul", "karna", "karein", "karenge", "kare", "hona", "chahiye",
    "nahi", "hum", "aap", "tum", "accha", "theek", "kaise", "kya", "kyun",
    "maan", "lijiye", "agar", "mein", "aur", "toh", "batao", "samjhao",
}

CONSTRAINT_PATTERNS = [
    re.compile(r"\b(cannot use|can'?t use|don'?t use|do not use|disallowed|ruled out|avoid|prohibit|nahi use karna|nahi use karein)\s+([^,.;!?]+)", re.I),
    re.compile(r"\b(must (have|be|use)|requirement is|require|latency (?:under|below|sla)|sla (?:is|under)|must meet|strictly)\s+([^,.;!?]+)", re.I),
    re.compile(r"\b(limited to|budget is|single node|fixed size|max (?:memory|throughput|capacity))\s+([^,.;!?]+)", re.I),
    re.compile(r"\b(in our (?:system|architecture|stack|setup)[^,.;!?]*(?:we (?:cannot|can'?t|don'?t|only use|require)[^,.;!?]*))", re.I),
]

DEVANAGARI_REGEX = re.compile(r"[\u0900-\u097F]")


@dataclass
class SessionLearnings:
    active_topic: str = "General Engineering Discussion"
    established_constraints: List[str] = field(default_factory=list)
    detected_language_style: str = "english"  # english | hinglish | hindi

    def to_prompt_section(self) -> str:
        if not self.established_constraints and self.detected_language_style == "english" and not self.active_topic:
            return ""
        if not self.established_constraints and self.detected_language_style == "english":
            return ""

        lines = ["### DYNAMIC CONVERSATION MEMORY & LEARNED CONSTRAINTS"]
        lines.append(f"- **Detected Dialogue Style**: {self.detected_language_style.capitalize()}")
        if self.active_topic:
            lines.append(f"- **Active Conversation Focus**: {self.active_topic}")
        if self.established_constraints:
            lines.append("- **Established Session Constraints & Decisions**:")
            for c in self.established_constraints[:6]:
                lines.append(f"  * {c.strip()}")
            lines.append(
                "- **Continuity Directive**: Build naturally on prior discussion. Do NOT propose technologies, "
                "protocols, or approaches that contradict these established constraints."
            )
        return "\n".join(lines)


class SessionLearner:
    """
    Extracts high-signal architectural constraints, conversation topics,
    and code-switching patterns from recent dialogue turns.
    """

    def extract_session_learnings(
        self,
        recent_transcript: List[Dict[str, str]],
        prior_qa: List[Dict[str, str]],
    ) -> SessionLearnings:
        if not recent_transcript and not prior_qa:
            return SessionLearnings(active_topic="", established_constraints=[], detected_language_style="english")

        all_texts: List[str] = []
        for t in recent_transcript:
            all_texts.append(t.get("text", ""))
        for qa in prior_qa:
            all_texts.append(qa.get("question", ""))
            all_texts.append(qa.get("answer", ""))

        combined = " ".join(all_texts)
        lower_combined = combined.lower()

        # 1. Detect language style
        lang_style = "english"
        if DEVANAGARI_REGEX.search(combined):
            lang_style = "hindi"
        else:
            tokens = set(re.findall(r"\b[a-z]{2,}\b", lower_combined))
            hinglish_count = len(tokens & HINGLISH_DETECTION_WORDS)
            if hinglish_count >= 2:
                lang_style = "hinglish"

        # 2. Extract technical constraints
        constraints: List[str] = []
        seen_constraints: set[str] = set()

        for text in all_texts:
            for pat in CONSTRAINT_PATTERNS:
                for match in pat.finditer(text):
                    cleaned = match.group(0).strip()
                    norm = re.sub(r"\s+", " ", cleaned).lower()
                    if norm not in seen_constraints and len(cleaned) > 10:
                        seen_constraints.add(norm)
                        constraints.append(cleaned)

        # 3. Infer active topic
        topic = "General Technical Dialogue"
        if "redis" in lower_combined or "cache" in lower_combined:
            topic = "Caching & Redis Architecture"
        elif "microservice" in lower_combined or "saga" in lower_combined or "2pc" in lower_combined:
            topic = "Distributed Systems & Microservices"
        elif "database" in lower_combined or "sql" in lower_combined or "deadlock" in lower_combined:
            topic = "Database Concurrency & Persistence"
        elif "auth" in lower_combined or "jwt" in lower_combined or "oauth" in lower_combined or "security" in lower_combined:
            topic = "Authentication & Application Security"
        elif "kafka" in lower_combined or "queue" in lower_combined or "event" in lower_combined:
            topic = "Event-Driven Messaging & Streaming"

        return SessionLearnings(
            active_topic=topic,
            established_constraints=constraints[:6],
            detected_language_style=lang_style,
        )
