"""
Unit tests for QuestionDetectionEngine covering:
- All 7 mandatory test questions
- Labeled conversation fixture (precision/recall/F1 evaluation)
- Small talk & meeting logistics suppression
- Multi-segment fragment merging
- Follow-up detection with parent question linking
- Exact and near-duplicate suppression
- Manual question registration
"""
import json
from pathlib import Path

import pytest

from app.services.question_detection.engine import QuestionDetectionEngine

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "sample_interview.jsonl"


def _load_fixture():
    lines = FIXTURE_PATH.read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(line) for line in lines]


def test_mandatory_seven_questions_all_detected():
    mandatory = [
        "Explain the difference between authentication and authorization.",
        "What is SQL injection?",
        "Explain the SAP authorization concept.",
        "What is the difference between OTBI and BI Publisher?",
        "Explain your previous project.",
        "How would you troubleshoot an application security issue?",
        "Tell me about yourself.",
    ]
    engine = QuestionDetectionEngine(session_id="s-mandatory")
    for idx, q in enumerate(mandatory):
        event = engine.process_segment(q, source="tab", now_mono=100.0 + idx * 10.0)
        assert event is not None, f"Failed to detect mandatory question: {q}"
        assert event.question_text == q
        assert event.detection_latency_ms < 50.0


def test_labeled_conversation_fixture_precision_and_recall():
    items = _load_fixture()
    engine = QuestionDetectionEngine(session_id="s-fixture")

    tp = fp = fn = tn = 0
    now = 1000.0

    for item in items:
        now += 2.0
        if item["source"] == "mic":
            engine.record_user_speech(item["text"])
            continue

        result = engine.process_segment(item["text"], source=item["source"], now_mono=now)
        detected = result is not None
        expected = item["expect_detect"]

        if expected and detected:
            tp += 1
            if "expect_type" in item:
                assert result.question_type == item["expect_type"], (
                    f"Item #{item['id']} ({item['text']}): expected type "
                    f"{item['expect_type']}, got {result.question_type}"
                )
        elif not expected and detected:
            fp += 1
        elif expected and not detected:
            fn += 1
        else:
            tn += 1

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0

    assert precision == 1.0, f"Precision below 1.0: tp={tp}, fp={fp}, fn={fn}, tn={tn}"
    assert recall == 1.0, f"Recall below 1.0: tp={tp}, fp={fp}, fn={fn}, tn={tn}"
    assert tp == 10
    assert tn == 8


def test_multi_segment_fragment_merging():
    engine = QuestionDetectionEngine(session_id="s-merge")

    ev1 = engine.process_segment("What is the difference between", source="tab", segment_id="seg-1", now_mono=10.0)
    assert ev1 is None

    ev2 = engine.process_segment("authentication and authorization?", source="tab", segment_id="seg-2", now_mono=12.0)
    assert ev2 is not None
    assert ev2.question_text == "What is the difference between authentication and authorization?"
    assert ev2.segment_ids == ["seg-1", "seg-2"]
    assert ev2.question_type == "technical"


def test_duplicate_and_near_duplicate_suppression():
    engine = QuestionDetectionEngine(session_id="s-dedup")

    first = engine.process_segment("What is SQL injection?", source="tab", now_mono=10.0)
    assert first is not None

    # Exact repeat
    dup1 = engine.process_segment("What is SQL injection?", source="tab", now_mono=15.0)
    assert dup1 is None

    # Minor punctuation/case variation
    dup2 = engine.process_segment("what is sql injection", source="tab", now_mono=20.0)
    assert dup2 is None


def test_followup_links_to_parent_question():
    engine = QuestionDetectionEngine(session_id="s-followup")

    parent = engine.process_segment("Explain your previous project.", source="tab", now_mono=10.0)
    assert parent is not None

    engine.record_user_speech("I migrated our legacy auth service to OAuth2 and JWT.")

    followup = engine.process_segment(
        "Can you explain how you handled that in your project?",
        source="tab",
        now_mono=25.0,
    )
    assert followup is not None
    assert followup.question_type == "followup"
    assert followup.parent_question_id == parent.id


def test_small_talk_and_logistics_suppressed():
    engine = QuestionDetectionEngine(session_id="s-smalltalk")
    negatives = [
        "Okay, sounds good.",
        "Great, let's move on.",
        "Can you hear me?",
        "Can you see my screen?",
        "How are you doing today?",
        "Thank you for joining.",
        "Nice to meet you.",
        "One moment, let me share my screen.",
    ]
    for idx, text in enumerate(negatives):
        res = engine.process_segment(text, source="tab", now_mono=50.0 + idx * 5.0)
        assert res is None, f"Small talk falsely detected as question: {text}"


def test_manual_question_registration_enables_followup():
    engine = QuestionDetectionEngine(session_id="s-manual")
    manual = engine.register_manual_question("Have you worked with SAP security?", question_id="q-manual-1")
    assert manual.question_type == "manual"
    assert manual.id == "q-manual-1"

    followup = engine.process_segment("And can you elaborate on that?", source="tab", now_mono=100.0)
    assert followup is not None
    assert followup.question_type == "followup"
    assert followup.parent_question_id == "q-manual-1"
