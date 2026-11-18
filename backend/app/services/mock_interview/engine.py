"""
MockInterviewEngine — Generates one mock interview question at a time and evaluates
candidate answers (typed or spoken) with score, feedback, missing technical concepts,
and an improved answer.

Uses the configured LLMProvider when available, and falls back transparently to a
curated offline question bank & concept rubric when no cloud API key is set.
"""
import json
import logging
import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from app.services.answer_generation.base import LLMProvider, LLMProviderError
from app.services.answer_generation.factory import get_llm_provider

logger = logging.getLogger(__name__)


@dataclass
class MockQuestionResult:
    question_text: str
    mode: str  # "llm" | "offline_bank"


@dataclass
class MockEvaluationResult:
    score: int  # 0..100
    feedback: str
    missing_concepts: List[str]
    improved_answer: str
    evaluation_mode: str  # "llm" | "local_rubric"

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "feedback": self.feedback,
            "missing_concepts": self.missing_concepts,
            "improved_answer": self.improved_answer,
            "evaluation_mode": self.evaluation_mode,
        }


# Curated local practice bank with expected concepts & reference answers
OFFLINE_QUESTION_BANK: Dict[str, List[dict]] = {
    "Application Security": [
        {
            "question": "Explain the difference between authentication and authorization.",
            "concepts": ["identity", "credentials", "permissions", "access control", "jwt", "rbac"],
            "reference": (
                "Authentication verifies who a user or service is using credentials such as passwords, MFA, or signed tokens (OAuth2/OIDC). "
                "Authorization determines what an authenticated principal is permitted to do, typically enforced via RBAC or ABAC policies on every protected resource."
            ),
        },
        {
            "question": "What is SQL injection and how do you prevent it?",
            "concepts": ["parameterized queries", "prepared statements", "input validation", "orm", "least privilege"],
            "reference": (
                "SQL injection occurs when untrusted user input is concatenated directly into a database query, allowing an attacker to alter query logic. "
                "Prevent it primarily with parameterized queries (prepared statements), safe ORM bindings, strict allow-list input validation, and least-privilege DB accounts."
            ),
        },
        {
            "question": "How would you troubleshoot an application security issue in production?",
            "concepts": ["reproduce", "logs", "scope", "containment", "root cause", "patch", "regression test"],
            "reference": (
                "Start by triaging severity and scoping impact via audit logs and traces, then contain active exposure (rotate secrets, block vectors, or disable affected endpoints). "
                "Reproduce safely in staging, identify root cause, deploy a minimal fix with regression tests, and perform a post-incident review."
            ),
        },
    ],
    "SAP Security": [
        {
            "question": "Explain the SAP authorization concept.",
            "concepts": ["authorization object", "pfcg", "role", "profile", "field", "su53", "least privilege"],
            "reference": (
                "SAP authorization controls access through authorization objects composed of up to 10 authorization fields. "
                "Administrators bundle objects and field values into roles via transaction PFCG, generate authorization profiles, assign roles to user master records, and diagnose missing checks using SU53 or ST01/STAUTHTRACE."
            ),
        },
        {
            "question": "What is Segregation of Duties (SoD) in SAP GRC and how do you remediate conflicts?",
            "concepts": ["sod", "grc", "risk", "mitigating control", "remediation", "role redesign"],
            "reference": (
                "Segregation of Duties prevents any single user from holding conflicting privileges (such as creating a vendor and approving payment) that could enable fraud. "
                "Conflicts are identified in SAP GRC Access Risk Analysis and addressed through role redesign, removing redundant transactions, or documenting compensating mitigating controls."
            ),
        },
    ],
    "Oracle Fusion HCM / OTBI": [
        {
            "question": "What is the difference between OTBI and BI Publisher?",
            "concepts": ["real-time", "ad-hoc", "subject areas", "pixel-perfect", "sql", "bursting", "scheduled"],
            "reference": (
                "OTBI (Oracle Transactional Business Intelligence) is designed for real-time, self-service ad-hoc analysis built on pre-defined Subject Areas without writing SQL. "
                "BI Publisher excels at pixel-perfect, high-volume formatted documents (payslips, checks, statutory extracts) powered by custom SQL data models and scheduled bursting."
            ),
        },
        {
            "question": "How does Role-Based Access Control work in Oracle Fusion HCM?",
            "concepts": ["job role", "duty role", "data role", "security profile", "abstract role"],
            "reference": (
                "Oracle Fusion HCM uses Abstract, Job, Duty, and Data roles. Job roles inherit Duty roles that grant functional privileges, "
                "while Data roles combine a Job role with HCM Security Profiles (e.g. Person, Organization, Country) to restrict which records a user can view or edit."
            ),
        },
    ],
    "Python & Backend": [
        {
            "question": "How does asyncio work in Python and when should you avoid it?",
            "concepts": ["event loop", "coroutine", "non-blocking", "i/o-bound", "cpu-bound", "gil"],
            "reference": (
                "Python asyncio runs cooperative coroutines on a single-threaded event loop, suspending tasks on await points during network or disk I/O. "
                "It excels at high-concurrency I/O-bound workloads, whereas CPU-bound tasks block the event loop and should be offloaded to ProcessPoolExecutor or native extensions."
            ),
        },
        {
            "question": "How do you design a resilient REST API with proper error handling and timeouts?",
            "concepts": ["status codes", "validation", "timeout", "retry", "idempotency", "rate limiting"],
            "reference": (
                "Validate all payloads at the boundary (e.g. Pydantic), return consistent structured error payloads with accurate HTTP status codes, "
                "enforce upstream timeouts with bounded exponential-backoff retries on idempotent operations, and protect endpoints with rate limiting."
            ),
        },
    ],
    "HR & Behavioral": [
        {
            "question": "Tell me about yourself.",
            "concepts": ["current role", "key skills", "achievement", "impact", "motivation"],
            "reference": (
                "Use a 60-90 second Present-Past-Future arc: summarize your current role and core strengths, highlight one concrete project with measurable impact, "
                "and connect your background directly to why this role is a strong fit."
            ),
        },
        {
            "question": "Explain your previous project and the toughest technical challenge you solved.",
            "concepts": ["situation", "architecture", "challenge", "action", "result", "metrics"],
            "reference": (
                "Frame your answer using STAR: briefly describe the system architecture and goal, pinpoint the hardest bottleneck or security constraint, "
                "explain the specific engineering trade-offs you implemented, and close with concrete measurable results."
            ),
        },
    ],
}


def _match_topic_bank(topic: str) -> List[dict]:
    lower = topic.lower()
    for key, items in OFFLINE_QUESTION_BANK.items():
        if key.lower() in lower or lower in key.lower():
            return items
    if any(k in lower for k in ("sap", "pfcg", "grc")):
        return OFFLINE_QUESTION_BANK["SAP Security"]
    if any(k in lower for k in ("otbi", "oracle", "fusion", "hcm", "bi publisher")):
        return OFFLINE_QUESTION_BANK["Oracle Fusion HCM / OTBI"]
    if any(k in lower for k in ("sec", "owasp", "sql", "auth", "cyber")):
        return OFFLINE_QUESTION_BANK["Application Security"]
    if any(k in lower for k in ("hr", "behav", "general")):
        return OFFLINE_QUESTION_BANK["HR & Behavioral"]
    return OFFLINE_QUESTION_BANK["Python & Backend"]


class MockInterviewEngine:
    """Orchestrates mock interview question generation and structured answer evaluation."""

    def __init__(
        self,
        llm_provider_factory: Callable[[Optional[str], Optional[str]], LLMProvider] = get_llm_provider,
    ):
        self.llm_provider_factory = llm_provider_factory

    async def generate_question(
        self,
        topic: str,
        previous_questions: List[str],
        provider_name: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> MockQuestionResult:
        """Generate one focused mock interview question for `topic`, avoiding prior questions."""
        system_prompt = (
            "You are a senior technical & behavioral interviewer conducting a mock interview. "
            "Ask ONE clear, realistic interview question on the requested topic. "
            "Return ONLY the question text — no preamble, numbering, or commentary."
        )
        prior_block = "\n".join(f"- {q}" for q in previous_questions) or "(none yet)"
        user_prompt = (
            f"Topic: {topic}\n"
            f"Questions already asked in this mock session (do NOT repeat):\n{prior_block}\n\n"
            "Generate the next single interview question:"
        )

        try:
            provider = self.llm_provider_factory(provider_name, model_name)
            text = (await provider.generate(system_prompt, user_prompt, max_tokens=160, temperature=0.5)).strip()
            if text:
                return MockQuestionResult(question_text=text.strip('"\' '), mode="llm")
        except LLMProviderError as err:
            logger.info("Mock question falling back to offline bank (%s: %s)", err.code, err.message)
        except Exception as exc:
            logger.warning("Mock question LLM fallback due to unexpected error: %s", exc)

        # Deterministic offline question bank fallback
        bank = _match_topic_bank(topic)
        asked_lower = {q.lower().strip() for q in previous_questions}
        for entry in bank:
            if entry["question"].lower().strip() not in asked_lower:
                return MockQuestionResult(question_text=entry["question"], mode="offline_bank")

        # If all topic-specific questions asked, generate a fresh topic-scoped follow-up prompt
        q_num = len(previous_questions) + 1
        return MockQuestionResult(
            question_text=f"Walk through a real-world troubleshooting or design scenario you have handled involving {topic} (Question #{q_num}).",
            mode="offline_bank",
        )

    async def evaluate_answer(
        self,
        topic: str,
        question_text: str,
        user_answer: str,
        provider_name: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> MockEvaluationResult:
        """Evaluate a candidate's mock answer into score, feedback, missing concepts, and improved answer."""
        system_prompt = (
            "You are an expert interview coach evaluating a candidate's mock interview response. "
            "Respond ONLY with valid JSON containing these exact keys:\n"
            '{"score": <int 0-100>, "feedback": "<concise constructive feedback>", '
            '"missing_concepts": ["<concept1>", ...], "improved_answer": "<clear strong model answer>"}\n'
            "Do not fabricate personal work history for the candidate."
        )
        user_prompt = (
            f"Topic: {topic}\n"
            f"Question: {question_text}\n"
            f"Candidate's Answer:\n{user_answer}\n\n"
            "Return the JSON evaluation:"
        )

        try:
            provider = self.llm_provider_factory(provider_name, model_name)
            raw = (await provider.generate(system_prompt, user_prompt, max_tokens=700, temperature=0.2)).strip()
            parsed = self._parse_evaluation_json(raw)
            if parsed is not None:
                return parsed
        except LLMProviderError as err:
            logger.info("Mock evaluation falling back to local rubric (%s: %s)", err.code, err.message)
        except Exception as exc:
            logger.warning("Mock evaluation LLM fallback due to unexpected error: %s", exc)

        return self._evaluate_offline_rubric(topic, question_text, user_answer)

    def _parse_evaluation_json(self, raw: str) -> Optional[MockEvaluationResult]:
        # Strip optional markdown code fences
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.I)
        try:
            data = json.loads(cleaned)
        except Exception:
            match = re.search(r"\{.*\}", cleaned, re.S)
            if not match:
                return None
            try:
                data = json.loads(match.group(0))
            except Exception:
                return None

        if not isinstance(data, dict) or "score" not in data:
            return None
        score = max(0, min(100, int(data.get("score", 60))))
        feedback = str(data.get("feedback", "")).strip() or "Good attempt; see missing concepts and improved answer."
        missing = [str(x).strip() for x in data.get("missing_concepts", []) if str(x).strip()]
        improved = str(data.get("improved_answer", "")).strip()
        return MockEvaluationResult(
            score=score,
            feedback=feedback,
            missing_concepts=missing,
            improved_answer=improved,
            evaluation_mode="llm",
        )

    def _evaluate_offline_rubric(
        self, topic: str, question_text: str, user_answer: str
    ) -> MockEvaluationResult:
        """Honest, deterministic rubric evaluation when running offline without an LLM key."""
        bank = _match_topic_bank(topic)
        matched_entry = None
        q_lower = question_text.lower()
        for entry in bank:
            if entry["question"].lower() == q_lower:
                matched_entry = entry
                break

        ans_lower = user_answer.lower()
        word_count = len(re.findall(r"\w+", ans_lower))

        if matched_entry:
            expected_concepts = matched_entry["concepts"]
            reference_answer = matched_entry["reference"]
        else:
            expected_concepts = ["definition", "example", "trade-off", "best practices"]
            reference_answer = (
                f"Structure your response on {topic} by defining the core mechanism clearly, "
                "walking through a concrete real-world example, and noting key security or performance trade-offs."
            )

        covered = [c for c in expected_concepts if c in ans_lower]
        missing = [c for c in expected_concepts if c not in ans_lower]

        coverage_ratio = len(covered) / max(len(expected_concepts), 1)
        length_bonus = min(20, int(word_count * 0.5))
        score = max(10, min(100, int(coverage_ratio * 80) + length_bonus))
        if word_count < 8:
            score = min(score, 30)

        if score >= 80:
            feedback = (
                f"Strong response covering {len(covered)}/{len(expected_concepts)} key concepts "
                f"({', '.join(covered) or 'core ideas'}). Tightening conciseness and adding concrete metrics will make it even stronger."
            )
        elif score >= 50:
            feedback = (
                f"Solid foundation ({len(covered)}/{len(expected_concepts)} key concepts addressed). "
                "Strengthen your answer by explicitly incorporating the missing concepts listed below."
            )
        else:
            feedback = (
                "Your response is brief or misses several core technical concepts expected by interviewers. "
                "Review the missing concepts and compare your structure with the improved answer below."
            )

        return MockEvaluationResult(
            score=score,
            feedback=feedback,
            missing_concepts=missing,
            improved_answer=reference_answer,
            evaluation_mode="local_rubric",
        )
