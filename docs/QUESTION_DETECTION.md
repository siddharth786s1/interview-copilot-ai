# Question Detection Results — Interview Copilot AI

Last updated: 2026-11-18 (Phase 5 Completed)

---

## Labeled Test Set (`backend/tests/fixtures/sample_interview.jsonl`)

| # | Source | Input | Label | Expected Detect | Actual Detect | Classified Type |
|---|--------|-------|-------|-----------------|---------------|-----------------|
| 1 | tab | "Hello, good morning! Nice to meet you." | small_talk | ❌ no | ❌ no | — |
| 2 | tab | "Can you hear me okay?" | small_talk (logistics) | ❌ no | ❌ no | — |
| 3 | tab | "Tell me about yourself." | question | ✅ yes | ✅ yes | `indirect` |
| 4 | tab | "Okay, sounds good." | small_talk | ❌ no | ❌ no | — |
| 5 | tab | "Explain the difference between authentication and authorization." | question | ✅ yes | ✅ yes | `technical` |
| 6 | tab | "What is SQL injection?" | question | ✅ yes | ✅ yes | `technical` |
| 7 | tab | "What is SQL injection?" | duplicate | ❌ no | ❌ no | suppressed |
| 8 | tab | "Explain the SAP authorization concept." | question | ✅ yes | ✅ yes | `technical` |
| 9 | tab | "What is the difference between OTBI and BI Publisher?" | question | ✅ yes | ✅ yes | `technical` |
| 10 | tab | "Great, let's move on." | small_talk | ❌ no | ❌ no | — |
| 11 | tab | "Explain your previous project." | question | ✅ yes | ✅ yes | `indirect` |
| 12 | mic | "In my previous project, I built an API gateway with FastAPI and JWT role-based access control." | candidate_answer | context only | context only | recorded |
| 13 | tab | "Can you explain how you handled that in your project?" | followup | ✅ yes | ✅ yes | `followup` (linked to #11) |
| 14 | tab | "And can you elaborate on that?" | followup | ✅ yes | ✅ yes | `followup` (linked to #13) |
| 15 | tab | "How would you troubleshoot an application security issue?" | question | ✅ yes | ✅ yes | `technical` |
| 16 | tab | "Could you..." | fragment | ❌ no (buffered) | ❌ no (buffered) | merged w/ #17 |
| 17 | tab | "walk me through how you secure REST APIs against OWASP top ten?" | merged_question | ✅ yes | ✅ yes | `technical` (merged) |
| 18 | tab | "Can you see my screen?" | small_talk (logistics) | ❌ no | ❌ no | — |
| 19 | tab | "Alright, thanks for your time today." | small_talk | ❌ no | ❌ no | — |

---

## Phase 5 Metrics (Measured via `tests/unit/test_question_detection.py`)

| Metric | Value | Notes |
|--------|-------|-------|
| True Positives (TP) | 10 | All 7 mandatory questions + 2 follow-ups + 1 merged multi-segment question |
| False Positives (FP) | 0 | Zero small-talk, logistics, fragment, or duplicate leaks |
| False Negatives (FN) | 0 | Zero missed questions |
| True Negatives (TN) | 8 | Small talk, logistics, fragment, exact duplicate suppressed |
| **Precision** | **1.00 (100%)** | `TP / (TP + FP)` |
| **Recall** | **1.00 (100%)** | `TP / (TP + FN)` |
| **F1 Score** | **1.00 (100%)** | |
| Duplicate suppression | **100%** | Exact + Jaccard similarity ≥ 0.80 within 5 min window |
| Follow-up detection | **100%** | Links `parent_question_id` to prior question |
| Avg Detection Latency | **0.281 ms** | Max: 1.496 ms (zero LLM calls needed for detection) |

---

## Caveats & Future Tuning

- Rule/pattern-based detection runs in sub-millisecond time with zero API cost, making it ideal for real-time gating before calling a paid/rate-limited LLM.
- Highly ambiguous implicit questions (e.g., declarative statements like *"I'd be curious about database locking"* without cue verbs) may occasionally be missed; the **Manual Question Input** (`POST /api/sessions/{id}/questions`) is always available in the live workspace as an instant fallback.
