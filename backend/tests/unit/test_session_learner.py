"""
Unit tests for SessionLearner dynamic context and constraint extraction.
"""
import pytest

from app.services.answer_generation.session_learner import SessionLearner, SessionLearnings


def test_session_learner_synthesizes_constraints_and_language():
    learner = SessionLearner()
    recent_transcript = [
        {"speaker": "Interviewer", "text": "In our system, we cannot use two-phase commit across microservices."},
        {"speaker": "Me", "text": "Understood, so distributed transactions with locking are ruled out."},
        {"speaker": "Interviewer", "text": "Haan, bilkul. Aur latency SLA sub-50ms hona chahiye."},
    ]
    prior_qa = [
        {"question": "How to handle distributed payments?", "answer": "Use Saga pattern with compensating transactions."}
    ]
    learnings = learner.extract_session_learnings(recent_transcript, prior_qa)
    assert isinstance(learnings, SessionLearnings)
    assert learnings.detected_language_style in ("hinglish", "bilingual")
    assert any("two-phase commit" in c.lower() or "2pc" in c.lower() for c in learnings.established_constraints)
    assert any("sub-50ms" in c.lower() or "latency" in c.lower() for c in learnings.established_constraints)
    prompt_str = learnings.to_prompt_section()
    assert "### DYNAMIC CONVERSATION MEMORY & LEARNED CONSTRAINTS" in prompt_str
    assert "two-phase commit" in prompt_str.lower() or "2pc" in prompt_str.lower()


def test_session_learner_empty_context():
    learner = SessionLearner()
    learnings = learner.extract_session_learnings([], [])
    assert learnings.detected_language_style == "english"
    assert len(learnings.established_constraints) == 0
    assert learnings.to_prompt_section() == ""
