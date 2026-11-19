"""
ContextManager — Assembles recent transcript, prior Q&A, resume facts,
and knowledge base excerpts into grounded LLM prompts with strict anti-fabrication rules.
"""
import json
import re
from typing import Callable, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.resume import Resume
from app.models.session import (
    DetectedQuestion,
    GeneratedAnswer,
    Session,
    TranscriptSegment,
)
from app.models.settings import AppSettings
from app.services.answer_generation.base import AnswerContext

PERSONAL_BACKGROUND_PATTERNS = [
    re.compile(r"\b(tell me about yourself|introduce yourself|your background|walk me through your resume)\b", re.I),
    re.compile(r"\b(your (previous|last|recent|current) (project|role|job|company|experience|work))\b", re.I),
    re.compile(r"\b(handled that in your project|in your project|projects? you(?:'ve| have) (built|worked on|led))\b", re.I),
    re.compile(r"\b(have you worked with|tell me about a time you|describe a time you|your strengths|your weaknesses)\b", re.I),
    re.compile(r"\b(why do you want|why are you leaving|where do you see yourself)\b", re.I),
]

STYLE_INSTRUCTIONS: Dict[str, str] = {
    "short": (
        "ANSWER STYLE: SHORT.\n"
        "Respond in 2 to 4 crisp, direct, natural conversational sentences ready to speak aloud. "
        "Lead with the core answer immediately. No fluff or filler."
    ),
    "detailed": (
        "ANSWER STYLE: DETAILED.\n"
        "Provide a comprehensive, well-structured technical explanation covering core concepts, "
        "underlying mechanics, key terminology, and important trade-offs or edge cases."
    ),
    "practical": (
        "ANSWER STYLE: PRACTICAL.\n"
        "Explain the concept using a concrete, real-world production example with practical "
        "implementation details, tools/patterns involved, and common pitfalls to avoid."
    ),
    "stepbystep": (
        "ANSWER STYLE: STEP-BY-STEP.\n"
        "Break the answer down into clear, numbered sequential steps (e.g., diagnosis, architecture, "
        "workflow, or troubleshooting order) so the candidate can walk through it methodically."
    ),
}

DEPTH_INSTRUCTIONS: Dict[str, str] = {
    "low": "TECHNICAL DEPTH: LOW — Keep terminology accessible and high-level.",
    "medium": "TECHNICAL DEPTH: MEDIUM — Use accurate engineering terminology appropriate for a mid-to-senior practitioner.",
    "high": "TECHNICAL DEPTH: HIGH — Go deep into internals, security/performance nuances, protocols, and architectural trade-offs.",
}


def is_personal_background_question(question: str) -> bool:
    """Return True if answering accurately requires personal resume/experience facts."""
    return any(p.search(question) for p in PERSONAL_BACKGROUND_PATTERNS)


def _safe_json_loads(raw: Optional[str]):
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


class ContextManager:
    """
    Loads session context from SQLite (and optional KB retriever) and constructs
    system + user prompts with strict grounding constraints.
    """

    def __init__(
        self,
        kb_retriever: Optional[Callable[[str, int], List[Dict[str, str]]]] = None,
        transcript_window: int = 12,
        qa_window: int = 5,
        kb_top_k: int = 3,
    ):
        self.kb_retriever = kb_retriever
        self.transcript_window = transcript_window
        self.qa_window = qa_window
        self.kb_top_k = kb_top_k

    async def build_context(
        self,
        db: AsyncSession,
        session_id: str,
        question_id: str,
        question_text: str,
        question_type: str = "direct",
        style: str = "short",
        technical_depth: str = "medium",
        expand_previous_answer: Optional[str] = None,
        kb_excerpts_override: Optional[List[Dict[str, str]]] = None,
        screen_context: Optional[str] = None,
    ) -> AnswerContext:
        # 1. Load session metadata
        session_obj = await db.get(Session, session_id)
        session_type = session_obj.type if session_obj else "general"

        # 2. Load recent finalized transcript segments
        t_res = await db.execute(
            select(TranscriptSegment)
            .where(TranscriptSegment.session_id == session_id)
            .order_by(TranscriptSegment.sequence.desc())
            .limit(self.transcript_window)
        )
        t_rows = list(reversed(t_res.scalars().all()))
        recent_transcript = [
            {
                "speaker": r.speaker_label or ("Interviewer" if r.source == "tab" else "Me"),
                "text": r.text,
            }
            for r in t_rows
        ]

        # 3. Load prior Q&A pairs (excluding current question)
        q_res = await db.execute(
            select(DetectedQuestion)
            .where(
                DetectedQuestion.session_id == session_id,
                DetectedQuestion.id != question_id,
            )
            .order_by(DetectedQuestion.detected_at.desc())
            .limit(self.qa_window)
        )
        prior_questions = list(reversed(q_res.scalars().all()))
        prior_qa: List[Dict[str, str]] = []
        for pq in prior_questions:
            a_res = await db.execute(
                select(GeneratedAnswer)
                .where(GeneratedAnswer.question_id == pq.id)
                .order_by(GeneratedAnswer.generated_at.desc())
                .limit(1)
            )
            ans = a_res.scalar_one_or_none()
            prior_qa.append(
                {
                    "question": pq.question_text,
                    "answer": ans.answer_text if ans else "(unanswered)",
                }
            )

        # 4. Load active resume if uploaded
        r_res = await db.execute(
            select(Resume)
            .where(Resume.is_active == True)  # noqa: E712
            .order_by(Resume.uploaded_at.desc())
            .limit(1)
        )
        resume_row = r_res.scalar_one_or_none()
        resume_summary: Optional[Dict[str, object]] = None
        if resume_row and (resume_row.extracted_text or resume_row.skills or resume_row.projects):
            resume_summary = {
                "filename": resume_row.filename,
                "skills": _safe_json_loads(resume_row.skills) or [],
                "experience": _safe_json_loads(resume_row.experience) or [],
                "projects": _safe_json_loads(resume_row.projects) or [],
                "education": _safe_json_loads(resume_row.education) or [],
                "certifications": _safe_json_loads(resume_row.certifications) or [],
                "extracted_text": (resume_row.extracted_text or "")[:3000],
            }

        # 5. Retrieve relevant KB excerpts via BM25 retriever
        if kb_excerpts_override is not None:
            kb_excerpts = kb_excerpts_override
        elif self.kb_retriever is not None:
            kb_excerpts = self.kb_retriever(question_text, self.kb_top_k)
        else:
            from app.services.knowledge_base.retriever import retrieve_from_db

            raw_hits = await retrieve_from_db(db=db, query=question_text, top_k=self.kb_top_k)
            kb_excerpts = [
                {
                    "category": str(hit.get("category", "Custom Topics")),
                    "filename": str(hit.get("filename", "doc")),
                    "excerpt": str(hit.get("excerpt", "")),
                }
                for hit in raw_hits
            ]

        # 6. Load Gemini structured answer & coaching preferences from AppSettings
        cfg_res = await db.execute(select(AppSettings).where(AppSettings.id == 1))
        app_cfg = cfg_res.scalar_one_or_none()
        structured_output = app_cfg.structured_output if app_cfg is not None else True
        target_role = (app_cfg.target_role or "").strip() if app_cfg else ""
        custom_instructions = (app_cfg.custom_instructions or "").strip() if app_cfg else ""
        raw_examples = _safe_json_loads(app_cfg.few_shot_examples) if app_cfg else None
        few_shot_examples = (
            [
                {"question": str(e["question"]), "ideal_answer": str(e["ideal_answer"])}
                for e in raw_examples
                if isinstance(e, dict) and e.get("question") and e.get("ideal_answer")
            ]
            if isinstance(raw_examples, list)
            else []
        )

        needs_customization = (
            is_personal_background_question(question_text) and resume_summary is None
        )

        return AnswerContext(
            session_id=session_id,
            question_id=question_id,
            question=question_text,
            question_type=question_type,
            session_type=session_type,
            style=style if style in STYLE_INSTRUCTIONS else "short",
            technical_depth=technical_depth if technical_depth in DEPTH_INSTRUCTIONS else "medium",
            recent_transcript=recent_transcript,
            prior_qa=prior_qa,
            resume_summary=resume_summary,
            kb_excerpts=kb_excerpts,
            expand_previous_answer=expand_previous_answer,
            needs_customization=needs_customization,
            structured_output=structured_output,
            target_role=target_role,
            custom_instructions=custom_instructions,
            few_shot_examples=few_shot_examples,
            screen_context=screen_context,
        )

    def build_prompts(self, ctx: AnswerContext) -> Tuple[str, str]:
        """Build (system_prompt, user_prompt) pair enforcing style, structure, coaching, and grounding."""
        style_rule = STYLE_INSTRUCTIONS.get(ctx.style, STYLE_INSTRUCTIONS["short"])
        depth_rule = DEPTH_INSTRUCTIONS.get(ctx.technical_depth, DEPTH_INSTRUCTIONS["medium"])

        grounding_rules = (
            "STRICT GROUNDING & HONESTY RULES:\n"
            "1. NEVER invent, fabricate, or assume work experience, companies, job titles, "
            "projects, metrics, dates, certifications, or technical skills that are NOT "
            "explicitly stated in the Candidate Resume or Knowledge Base below.\n"
            "2. Keep answers natural, accurate, technically sound, and easy to deliver in a live interview.\n"
        )

        if ctx.needs_customization:
            grounding_rules += (
                "3. MISSING PERSONAL CONTEXT DETECTED: No resume has been uploaded yet, and this "
                "question asks about the candidate's personal background or projects. "
                "You MUST begin your response with: '[Needs customization — upload your resume for personalized details]' "
                "and provide ONLY an honest, adaptable structure using clear placeholders like [Your Role] or [Your Project], "
                "without inventing fake achievements.\n"
            )
        else:
            grounding_rules += (
                "3. When referencing the candidate's background, rely exclusively on the provided "
                "Resume and Knowledge Base context. If a specific personal detail is missing, explicitly "
                "mark that part as needing customization rather than fabricating it.\n"
            )

        structure_block = ""
        if ctx.structured_output:
            if ctx.style == "short":
                structure_block = (
                    "\nSTRUCTURED RESPONSE FORMAT (REQUIRED):\n"
                    "Organize the response cleanly using these exact Markdown headings so the candidate can scan it in 2 seconds:\n"
                    "**Direct Answer**\n"
                    "<1–2 crisp, directly speakable sentences>\n\n"
                    "**Key Points**\n"
                    "- <2–3 tight, high-signal bullets>\n\n"
                    "**Quick Tip**\n"
                    "<1 brief practical example or follow-up pointer>"
                )
            else:
                structure_block = (
                    "\nSTRUCTURED RESPONSE FORMAT (REQUIRED):\n"
                    "Organize the response cleanly using these exact Markdown headings:\n"
                    "**Direct Answer**\n"
                    "<1–2 sentence executive summary>\n\n"
                    "**Key Points**\n"
                    "- <3–5 crisp technical bullets or numbered steps>\n\n"
                    "**Practical Example**\n"
                    "<Concrete real-world example, code snippet, or workflow>\n\n"
                    "**Follow-up Tip**\n"
                    "<1 important edge case, trade-off, or follow-up talking point>"
                )

        coaching_block = ""
        if ctx.target_role:
            coaching_block += f"\nTARGET CANDIDATE ROLE: {ctx.target_role}\nTailor terminology and examples to this role."
        if ctx.custom_instructions:
            coaching_block += f"\nCANDIDATE COACHING INSTRUCTIONS (FOLLOW CLOSELY):\n{ctx.custom_instructions}"

        system_prompt = (
            f"You are Interview Copilot AI, a personal real-time interview co-pilot and coach "
            f"supporting a candidate during a {ctx.session_type.upper()} interview.\n"
            f"You continuously analyze the live conversation, technical context, and ongoing dialogue. "
            f"When the interviewer presents a technical scenario, architecture challenge, constraint, "
            f"objection, system requirement, or discussion point (even without asking a formal question), "
            f"you immediately provide the candidate with a reliable, structured, high-signal response to speak aloud.\n\n"
            f"{grounding_rules}\n"
            f"{style_rule}\n\n"
            f"{depth_rule}"
            f"{structure_block}"
            f"{coaching_block}"
        )

        sections: List[str] = []

        if ctx.few_shot_examples:
            ex_lines = [
                f"Example {i + 1}:\nQ: {ex['question']}\nIdeal Answer:\n{ex['ideal_answer']}"
                for i, ex in enumerate(ctx.few_shot_examples[:5])
            ]
            sections.append(
                "### CANDIDATE PREFERRED ANSWER EXAMPLES (MATCH THIS STRUCTURE & TONE)\n"
                + "\n\n".join(ex_lines)
            )

        if ctx.screen_context:
            sections.append(
                "### CURRENT SCREEN CONTEXT (VISIBLE ON SHARED SCREEN)\n"
                + ctx.screen_context[:2500]
            )

        if ctx.resume_summary:
            r = ctx.resume_summary
            resume_parts = []
            if r.get("skills"):
                resume_parts.append(f"Skills: {r['skills']}")
            if r.get("experience"):
                resume_parts.append(f"Experience: {r['experience']}")
            if r.get("projects"):
                resume_parts.append(f"Projects: {r['projects']}")
            if r.get("education"):
                resume_parts.append(f"Education: {r['education']}")
            if r.get("certifications"):
                resume_parts.append(f"Certifications: {r['certifications']}")
            if not resume_parts and r.get("extracted_text"):
                resume_parts.append(str(r["extracted_text"]))
            sections.append("### CANDIDATE RESUME (VERIFIED FACTS)\n" + "\n".join(resume_parts))
        else:
            sections.append("### CANDIDATE RESUME\n(No resume uploaded yet.)")

        if ctx.kb_excerpts:
            kb_lines = [
                f"- [{ex.get('category', 'General')} / {ex.get('filename', 'doc')}]: {ex.get('excerpt', '')}"
                for ex in ctx.kb_excerpts
            ]
            sections.append("### PERSONAL KNOWLEDGE BASE EXCERPTS\n" + "\n".join(kb_lines))

        if ctx.prior_qa:
            qa_lines = [
                f"Q: {item['question']}\nA: {item['answer'][:400]}"
                for item in ctx.prior_qa
            ]
            sections.append("### PREVIOUS QUESTIONS & ANSWERS IN THIS SESSION\n" + "\n\n".join(qa_lines))

        if ctx.recent_transcript:
            t_lines = [f"{item['speaker']}: {item['text']}" for item in ctx.recent_transcript]
            sections.append("### RECENT TRANSCRIPT CONTEXT\n" + "\n".join(t_lines))

        if ctx.expand_previous_answer:
            sections.append(
                "### TASK: EXPAND EXISTING ANSWER\n"
                f"Topic / Question: {ctx.question}\n"
                f"Previous Answer:\n{ctx.expand_previous_answer}\n\n"
                "Expand on the previous answer with deeper technical detail, a concrete example, "
                "and any important edge cases or follow-up talking points."
            )
        elif ctx.question_type == "conversation":
            sections.append(
                "### INTERVIEWER DISCUSSION POINT / TECHNICAL SCENARIO\n"
                f"{ctx.question}\n\n"
                "The interviewer shared this technical scenario, system constraint, or discussion point during the ongoing conversation. "
                "Provide an immediate, reliable, structured response the candidate can speak to directly address this scenario, trade-offs, and recommended technical approach."
            )
        else:
            sections.append(
                f"### INTERVIEWER QUESTION ({ctx.question_type.upper()})\n{ctx.question}\n\n"
                "Generate the suggested answer now."
            )

        user_prompt = "\n\n".join(sections)
        return system_prompt, user_prompt
