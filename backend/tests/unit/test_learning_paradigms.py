"""
Unit tests for the multi-paradigm interview few-shot learning library.
"""
import pytest

from app.services.answer_generation.learning_paradigms import (
    AVAILABLE_PARADIGMS,
    PARADIGM_DEFINITIONS,
    get_learning_exemplars,
)


def test_learning_paradigms_retrieval():
    assert len(AVAILABLE_PARADIGMS) == 5
    assert "system_design" in AVAILABLE_PARADIGMS
    assert "incident_debugging" in AVAILABLE_PARADIGMS
    assert "behavioral_star" in AVAILABLE_PARADIGMS
    assert "pushback_handling" in AVAILABLE_PARADIGMS
    assert "bilingual_hinglish" in AVAILABLE_PARADIGMS

    exemplars = get_learning_exemplars(["system_design", "bilingual_hinglish"])
    assert len(exemplars) == 2
    assert "Direct Answer" in exemplars[0]["ideal_answer"]
    assert "Key Points" in exemplars[0]["ideal_answer"]

    # Check Hinglish exemplar contains bilingual phrasing and English tech terms
    hinglish = [ex for ex in exemplars if ex.get("paradigm") == "bilingual_hinglish"]
    assert len(hinglish) == 1
    assert "Redis" in hinglish[0]["ideal_answer"] or "cache" in hinglish[0]["ideal_answer"].lower()


def test_default_all_paradigms_returned():
    all_ex = get_learning_exemplars()
    assert len(all_ex) == 5
    for ex in all_ex:
        assert "question" in ex
        assert "ideal_answer" in ex
        assert "paradigm" in ex
        assert len(ex["question"]) > 10
        assert len(ex["ideal_answer"]) > 20
