# Architecture — Interview Copilot AI

Last updated: 2026-11-18

---

## System Overview

Interview Copilot AI is a local-first, single-user, web-based personal AI interview assistant. It captures permitted audio from browser tabs or microphone, converts speech to text in real time, detects questions, and streams AI-generated answers to a live dashboard.

---

## High-Level Data Flow

```
┌─────────────────────────────────────────────────┐
│                   BROWSER (Next.js)             │
│                                                 │
│  ┌──────────────┐   ┌────────────────────────┐  │
│  │ AudioCapture │   │   Live Dashboard       │  │
│  │ Provider     │   │  (Transcript + Answer) │  │
│  │              │   │                        │  │
│  │ getUserMedia │   │  WebSocket Client      │  │
│  │ getDisplay   │   └──────────┬─────────────┘  │
│  │ Media        │              │ WS events       │
│  └──────┬───────┘              │                 │
│         │ audio chunks (PCM)   │                 │
│         │ via WebSocket        │                 │
└─────────┼──────────────────────┼─────────────────┘
          │                      │
          ▼                      ▲
┌─────────────────────────────────────────────────┐
│                FASTAPI BACKEND                  │
│                                                 │
│  WS /ws/audio  ──▶ AudioStreamHandler           │
│                        │                        │
│                        ▼                        │
│               SpeechToTextProvider (interface)  │
│               ├── WhisperProvider (local)       │
│               └── DeepgramProvider (cloud)      │
│                        │                        │
│                        ▼                        │
│               TranscriptManager                 │
│               (dedupe, timestamps, segments)    │
│                        │                        │
│                        ▼                        │
│               QuestionDetectionEngine           │
│               (interrogative, indirect,         │
│                follow-up, duplicate prevention) │
│                        │                        │
│                        ▼                        │
│               ContextManager                    │
│               ├── Recent transcript window      │
│               ├── Prior Q&A history             │
│               ├── Resume facts                  │
│               └── KB retrieval (BM25)           │
│                        │                        │
│                        ▼                        │
│               AnswerGenerationService           │
│               ├── OpenAIProvider                │
│               └── GeminiProvider               │
│                        │                        │
│               WS /ws/session ──▶ Browser        │
│                                                 │
│  REST API (/api/*)                              │
│  ├── sessions (CRUD)                            │
│  ├── resume (upload, extract, delete)           │
│  ├── knowledge_base (upload, retrieve, delete)  │
│  ├── history (list, open, search, export)       │
│  ├── mock_interview (generate, evaluate)        │
│  └── settings (get, update)                     │
│                                                 │
│  Database (SQLite via SQLModel)                 │
│  └── Repository Pattern (PostgreSQL-swappable)  │
└─────────────────────────────────────────────────┘
```

---

## Component Descriptions

### Frontend (Next.js + React + TypeScript)

| Component | Responsibility |
|-----------|---------------|
| `AudioCaptureProvider` | Browser API wrapper; `getUserMedia` + `getDisplayMedia`; emits PCM chunks |
| `WebSocketClient` | Manages WS connection to backend; reconnect logic |
| `LiveDashboard` | Main interview workspace; left: transcript; right: answer |
| `SessionManager` | Create/start/pause/end session, audio source selection |
| `ResumeManager` | Upload, preview, delete resume |
| `KnowledgeBase` | Upload, categorize, delete KB documents |
| `HistoryViewer` | Browse/search past sessions |
| `MockInterview` | Independent mock interview flow |
| `Settings` | Provider, model, audio, theme, retention config |

### Backend (FastAPI + Python)

| Service | Responsibility |
|---------|---------------|
| `AudioStreamHandler` | Receives WebSocket audio chunks; routes to STT provider |
| `SpeechToTextProvider` | Interface: `transcribe_chunk(audio: bytes) → TranscriptSegment` |
| `WhisperProvider` | Local faster-whisper implementation |
| `DeepgramProvider` | Cloud streaming implementation |
| `TranscriptManager` | Accumulates segments; deduplication; timestamps; partial/final distinction |
| `QuestionDetectionEngine` | Pattern + heuristic question detection; follow-up linking |
| `ContextManager` | Assembles context dict for LLM: transcript window, Q&A history, resume, KB |
| `KnowledgeBaseRetriever` | BM25 keyword search over chunked documents |
| `AnswerGenerationService` | Interface: `generate_answer(context) → AsyncIterator[str]` |
| `OpenAIProvider` | OpenAI GPT-4o / gpt-4o-mini implementation |
| `GeminiProvider` | Google Gemini 2.0 Flash implementation |
| `SessionRepository` | DB operations for sessions (SQLModel + SQLite) |
| `ResumeRepository` | DB + file operations for resumes |
| `KnowledgeBaseRepository` | DB + file ops for KB documents |

---

## Database Schema (SQLite / SQLModel)

```
sessions
  id: UUID PK
  title: str
  type: enum (technical|hr|behavioral|general|mock|custom)
  status: enum (created|active|paused|ended)
  created_at: datetime
  ended_at: datetime | null
  duration_seconds: int | null
  settings_snapshot: JSON  # provider, model at time of session

transcript_segments
  id: UUID PK
  session_id: UUID FK → sessions
  source: enum (tab|mic|manual)
  speaker_label: str | null
  text: str
  is_final: bool
  timestamp: datetime
  sequence: int

detected_questions
  id: UUID PK
  session_id: UUID FK → sessions
  segment_ids: JSON  # list of transcript_segment IDs that compose the question
  question_text: str
  question_type: enum (direct|indirect|technical|followup|manual)
  detected_at: datetime
  answered: bool

generated_answers
  id: UUID PK
  question_id: UUID FK → detected_questions
  style: enum (short|detailed|practical|stepbystep)
  answer_text: str
  model_used: str
  generated_at: datetime
  generation_time_ms: int

resumes
  id: UUID PK
  filename: str
  file_path: str
  uploaded_at: datetime
  extracted_text: text
  skills: JSON
  experience: JSON
  education: JSON
  certifications: JSON
  projects: JSON
  is_active: bool

kb_documents
  id: UUID PK
  filename: str
  file_path: str
  category: str
  uploaded_at: datetime
  extracted_text: text
  chunks: JSON  # list of {text, start_char, end_char}
  is_active: bool

settings
  id: int PK (single row, id=1)
  stt_provider: str
  llm_provider: str
  llm_model: str
  whisper_model_size: str
  language: str
  default_answer_style: str
  default_technical_depth: str
  theme: str
  retention_days: int | null
  updated_at: datetime

mock_sessions
  id: UUID PK
  topic: str
  created_at: datetime
  ended_at: datetime | null

mock_exchanges
  id: UUID PK
  mock_session_id: UUID FK → mock_sessions
  question_text: str
  user_answer: str
  evaluation: JSON  # score, missing_concepts, improved_answer
  created_at: datetime
```

---

## WebSocket Event Contract

### Client → Server (audio stream)

```jsonc
// Connection: ws://localhost:8000/ws/audio/{session_id}
// Binary frames: raw PCM audio (16kHz, 16-bit mono)
// OR JSON control frames:
{ "type": "control", "action": "pause" | "resume" | "end" }
```

### Server → Client (session events)

```jsonc
// Connection: ws://localhost:8000/ws/session/{session_id}

// Transcript event
{ "type": "transcript", "source": "tab"|"mic", "text": "...", "is_final": true, "timestamp": "ISO8601", "sequence": 42 }

// Question detected event
{ "type": "question", "question_id": "uuid", "text": "...", "question_type": "technical" }

// Answer stream event (one per token/chunk)
{ "type": "answer_chunk", "question_id": "uuid", "text": "token..." }

// Answer complete event
{ "type": "answer_complete", "question_id": "uuid", "full_text": "...", "generation_ms": 3200 }

// Status event
{ "type": "status", "session_status": "active"|"paused"|"ended", "audio_sources": {"tab": true, "mic": true} }

// Error event
{ "type": "error", "code": "STT_UNAVAILABLE"|"LLM_TIMEOUT"|..., "message": "..." }
```

---

## Provider Interfaces (Python)

```python
# STT Provider
class SpeechToTextProvider(ABC):
    async def transcribe_chunk(self, audio: bytes, source: str) -> list[TranscriptSegment]: ...
    async def close(self) -> None: ...

# LLM Provider  
class LLMProvider(ABC):
    async def generate_answer(self, context: AnswerContext) -> AsyncIterator[str]: ...

# Audio Capture (frontend abstraction)
interface AudioCaptureProvider {
  startTabCapture(): Promise<MediaStream>
  startMicCapture(): Promise<MediaStream>
  stop(): void
  onChunk: (audio: ArrayBuffer, source: 'tab' | 'mic') => void
  onError: (error: AudioCaptureError) => void
  onTrackEnded: (source: 'tab' | 'mic') => void
}
```

---

## Directory Structure

```
interview-copilot-ai/
├── frontend/
│   ├── app/                        # Next.js App Router pages
│   │   ├── page.tsx                # Dashboard
│   │   ├── session/[id]/page.tsx   # Live interview workspace
│   │   ├── history/page.tsx
│   │   ├── resume/page.tsx
│   │   ├── knowledge-base/page.tsx
│   │   ├── mock/page.tsx
│   │   └── settings/page.tsx
│   ├── components/
│   │   ├── dashboard/
│   │   ├── session/
│   │   ├── audio/
│   │   ├── transcript/
│   │   ├── answers/
│   │   ├── resume/
│   │   ├── knowledge-base/
│   │   ├── history/
│   │   ├── mock/
│   │   └── ui/                     # shadcn/ui components
│   ├── hooks/
│   │   ├── useAudioCapture.ts
│   │   ├── useWebSocket.ts
│   │   ├── useSession.ts
│   │   └── useTranscript.ts
│   ├── services/
│   │   ├── api.ts                  # REST client
│   │   └── audioCapture.ts        # AudioCaptureProvider impl
│   ├── types/
│   │   └── index.ts                # Shared TypeScript types
│   └── styles/
│       └── globals.css
│
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app + startup
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── sessions.py
│   │   │   │   ├── resume.py
│   │   │   │   ├── knowledge_base.py
│   │   │   │   ├── history.py
│   │   │   │   ├── mock_interview.py
│   │   │   │   └── settings.py
│   │   │   └── websockets/
│   │   │       ├── audio_ws.py     # /ws/audio/{session_id}
│   │   │       └── session_ws.py   # /ws/session/{session_id}
│   │   ├── core/
│   │   │   ├── config.py           # Settings from env
│   │   │   ├── logging.py
│   │   │   └── exceptions.py
│   │   ├── models/                 # SQLModel table definitions
│   │   │   ├── session.py
│   │   │   ├── transcript.py
│   │   │   ├── question.py
│   │   │   ├── answer.py
│   │   │   ├── resume.py
│   │   │   ├── knowledge_base.py
│   │   │   ├── settings.py
│   │   │   └── mock.py
│   │   ├── schemas/                # Pydantic request/response schemas
│   │   ├── services/
│   │   │   ├── audio/
│   │   │   │   └── audio_handler.py
│   │   │   ├── transcription/
│   │   │   │   ├── base.py         # SpeechToTextProvider ABC
│   │   │   │   ├── whisper_provider.py
│   │   │   │   └── deepgram_provider.py
│   │   │   ├── question_detection/
│   │   │   │   ├── engine.py
│   │   │   │   └── patterns.py
│   │   │   ├── answer_generation/
│   │   │   │   ├── base.py         # LLMProvider ABC
│   │   │   │   ├── openai_provider.py
│   │   │   │   ├── gemini_provider.py
│   │   │   │   ├── service.py      # AnswerGenerationService
│   │   │   │   └── context_manager.py
│   │   │   └── knowledge_base/
│   │   │       ├── retriever.py    # BM25 search
│   │   │       └── chunker.py
│   │   └── database/
│   │       ├── connection.py       # engine + session factory
│   │       ├── init_db.py          # create all tables
│   │       └── repositories/
│   │           ├── session_repo.py
│   │           ├── resume_repo.py
│   │           └── kb_repo.py
│   ├── tests/
│   │   ├── fixtures/
│   │   │   ├── sample_interview.jsonl  # labeled transcript
│   │   │   └── sample_audio.wav        # synthetic test audio
│   │   ├── unit/
│   │   │   ├── test_question_detection.py
│   │   │   ├── test_transcript_manager.py
│   │   │   └── test_context_manager.py
│   │   ├── integration/
│   │   │   ├── test_sessions_api.py
│   │   │   ├── test_resume_api.py
│   │   │   └── test_websocket.py
│   │   └── pipeline/
│   │       └── test_full_pipeline.py   # mocked providers
│   └── requirements.txt
│
├── storage/
│   ├── uploads/
│   ├── resumes/
│   ├── sessions/
│   └── models/                     # Whisper model cache
│
├── docs/
│   ├── ENVIRONMENT.md
│   ├── ARCHITECTURE.md
│   ├── ROADMAP.md
│   ├── RISKS.md
│   ├── API_KEYS.md
│   ├── COSTS.md
│   ├── PERF.md
│   ├── AUDIO_QA.md
│   ├── QUESTION_DETECTION.md
│   └── KNOWN_LIMITATIONS.md
│
├── scripts/
│   ├── setup.ps1                   # Windows setup script
│   └── dev.ps1                     # Start frontend + backend together
│
├── PROGRESS.md
├── DECISIONS.md
├── KNOWN_ISSUES.md
├── .env.example
├── .gitignore
└── README.md
```

---

## Security Design

- All secrets in `.env`, loaded by `python-dotenv`. Never in code or frontend.
- FastAPI validates all inputs via Pydantic schemas at the boundary.
- File uploads: validate MIME type, extension whitelist, max 50MB per file.
- Extracted text capped at 100K characters per document.
- `storage/` is local-only, not committed to git.
- WebSocket connections require a valid session ID (UUID).
- No authentication system needed (single-user local app).
- Structured logs never contain API keys, raw credentials, or transcript PII.
