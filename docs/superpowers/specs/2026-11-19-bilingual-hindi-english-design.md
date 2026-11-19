# Design Document: Bilingual (Hindi + English & Hinglish) Interview Co-pilot

**Date:** 2026-11-19  
**Status:** Pending Approval  
**Scope:** STT, Question & Scenario Detection, Gemini Mirror Prompting, and UI Language Selection.

---

## 1. Intent & Context
Technical and behavioral interviews in India and multinational organizations frequently involve code-switching between English and Hindi ("Hinglish"). Interviewers often state technical questions or real-world system design scenarios in Hindi or Romanized Hindi mixed with English technical terms (e.g., *"Aapka previous project explain karo"*, *"Maan lijiye hamare system mein Redis high memory le raha hai, usko kaise handle karoge?"*).

Currently, the copilot only has English pattern matching in `patterns.py` and single-language presets (`en`, `hi`, `auto`). This feature adds native bilingual support where the system seamlessly detects questions/scenarios in English, Hindi, and Hinglish, and generates structured answers mirroring the interviewer's language style with technical terminology preserved in standard English.

---

## 2. Goals & Non-Goals

### Goals
1. **Bilingual Question & Turn Detection:** Support questions and conversational scenario statements in:
   - Standard English
   - Romanized Hindi (Hinglish): e.g., `kya hai`, `kaise karenge`, `explain karo`, `maan lijiye`, `problem yeh hai ki`
   - Devanagari Hindi: e.g., `क्या है`, `कैसे`, `समझाओ`, `मान लीजिए`, `समस्या यह है कि`
2. **Spoken Language Mirroring:** Gemini dynamically detects whether the interviewer spoke in English or Hindi/Hinglish.
   - If **English**: Returns standard crisp English structured response.
   - If **Hindi / Hinglish**: Returns a natural, professional bilingual technical Hinglish response (conversational explanations in natural Hindi/Hinglish, architecture & code terminology in English).
3. **STT Multilingual Routing:** Support `bilingual_hi_en` option in Whisper and Deepgram providers that enables multi-language transcription without locking to a single language.
4. **UI Language Selection:** Expose `"bilingual_hi_en"` ("Bilingual (Hindi + English)") in Settings and the live Session workspace header.

### Non-Goals
- Translating programming code, command line snippets, or SQL queries into Hindi. Code remains standard English.
- Fabricating or translating resume facts into Hindi.
- Disabling English detection (English remains 100% supported simultaneously).

---

## 3. Approaches Considered

- **Approach 1: Mirror Spoken Language & Hinglish Support (Selected)**
  - Detects language of interviewer's turn; Gemini mirrors the conversational style (English for English, Hinglish for Hindi/Hinglish). Core tech terms remain in English.
  - *Why selected:* Best user experience for live interviews; matches natural workplace communication.
- **Approach 2: Dual Output (English + Hindi Side-by-Side)**
  - Shows two complete answers for every question.
  - *Why discarded:* Doubles LLM latency, consumes screen real estate, causes information overload during live interviews.
- **Approach 3: Strict Manual Language Toggle**
  - Requires candidate to manually switch between English and Hindi modes during the call.
  - *Why discarded:* Unusable when interviewers switch between English and Hindi mid-conversation.

---

## 4. Detailed Component Design

### A. Question & Scenario Detection Patterns (`patterns.py` & `engine.py`)
Add compiled regex patterns:
- `HINGLISH_QUESTION_PATTERNS`:
  - Question starters: `\b(kya (aap|tum|hum|ye)|kaise (karenge|hota|handle|solve)|kyun (use|karna)|bataiye|batao|explain karo|elaborate karo)\b`
  - Question endings: `\b(kya hai|kya hoga|kaise kaam karta hai|kaise kare|bata sakte ho)\??$`
- `HINDI_QUESTION_PATTERNS` (Devanagari):
  - `\b(क्या|कैसे|क्यों|समझाओ|बताइए|बताओ|का क्या मतलब है)\b`
- `HINGLISH_CONVERSATION_CUE_PATTERNS`:
  - Scenarios & constraints: `\b(maan lijiye|suppose karo|agar hamare (system|server|architecture|database) mein|problem yeh hai ki|issue yeh aa raha hai|outage hua tha|hum use nahi kar sakte|trade-?off yeh hai)\b`
- `HINDI_CONVERSATION_CUE_PATTERNS` (Devanagari):
  - `\b(मान लीजिए|अगर हमारे|समस्या यह है कि|दिक्कत यह है कि)\b`

### B. Gemini Bilingual Mirroring Prompt (`context_manager.py`)
In `ContextManager.build_prompts()`:
- Add a helper `is_hindi_or_hinglish(text: str) -> bool` using character range (Devanagari `\u0900-\u097F`) and Hinglish keyword patterns.
- Inject `BILINGUAL_INSTRUCTIONS`:
  > "BILINGUAL INTERVIEW RULES (ENGLISH + HINDI / HINGLISH):  
  > 1. If the interviewer speaks in English, generate the response in clear, professional English.  
  > 2. If the interviewer speaks in Hindi or Hinglish, generate the response in natural, fluent bilingual Hinglish (e.g. 'Is scenario mein best approach yeh hogi ki hum Redis LRU eviction policy enable karein...').  
  > 3. ALWAYS keep technical terminology, architecture patterns, metric names, and code in standard English."

### C. STT Multilingual Support (`whisper_provider.py`, `transcript_manager.py`)
- Map `"bilingual_hi_en"` to Whisper's automatic language detection (`language=None`) so it transcribes both Hindi and English speech without forcing a single language.

### D. Frontend UI Updates
- In `frontend/app/settings/page.tsx` and `frontend/app/session/[id]/page.tsx`:
  - Add `<option value="bilingual_hi_en">Bilingual: Hindi + English (Hinglish)</option>` to the language selector dropdowns.

---

## 5. Verification Plan
1. **Unit Tests:**
   - Test detecting Hinglish questions (e.g., *"Aapka previous project explain karo"*).
   - Test detecting Devanagari Hindi questions (e.g., *"क्या आप ऑथेंटिकेशन और ऑथराइजेशन में अंतर समझा सकते हैं?"*).
   - Test detecting Hinglish scenario cues (e.g., *"Maan lijiye hamare system mein Redis cluster memory full ho rahi hai"*).
   - Test that small talk in Hindi (e.g., *"Theek hai"*, *"Dhanyawad"*, *"Aap sun sakte ho?"*) remains suppressed.
   - Test prompt construction injecting bilingual mirroring instructions when `bilingual_hi_en` is active or Hindi is detected.
2. **Integration & E2E Tests:**
   - Full test suite run (`pytest backend/tests/ -v`).
   - Frontend lint & build (`npm run lint`, `npm run build`).
   - Live browser test in session workspace verifying that Hindi/Hinglish questions produce properly structured answers with English technical terms.
