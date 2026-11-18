# API Keys & Accounts Required — Interview Copilot AI

Last updated: 2026-11-18

> All keys go in `.env` only. Never in code or commits.

---

## Required for Core Pipeline

### Option A: Local STT (faster-whisper) + Cloud LLM

| Service | Account | Key Name | Cost | Notes |
|---------|---------|----------|------|-------|
| OpenAI API | openai.com | `OPENAI_API_KEY` | ~\$0.01–\$0.03 / 1K tokens | GPT-4o-mini cheapest |
| OR Google Gemini | aistudio.google.com | `GOOGLE_API_KEY` | \$0 (free tier 15 req/min) | Gemini 2.0 Flash recommended |
| faster-whisper | (local, no key) | — | \$0 | ✅ Already installed |

**Recommended starter setup:** `GOOGLE_API_KEY` (Gemini free tier) + local faster-whisper = \$0/month for personal use.

---

### Option B: Cloud STT + Cloud LLM (best latency)

| Service | Account | Key Name | Cost | Notes |
|---------|---------|----------|------|-------|
| Deepgram | deepgram.com | `DEEPGRAM_API_KEY` | \$0 (12,000 min/month free) ⚠️ verify | Nova-2 model, true streaming |
| OpenAI API | openai.com | `OPENAI_API_KEY` | ~\$0.60/1M tokens (GPT-4o-mini) | |
| OR Google Gemini | aistudio.google.com | `GOOGLE_API_KEY` | \$0 free tier | Gemini 2.0 Flash |

> ⚠️ Verify Deepgram's current free tier at https://deepgram.com/pricing — pricing changes.

---

### Option C: OpenAI STT + LLM

| Service | Account | Key Name | Cost | Notes |
|---------|---------|----------|------|-------|
| OpenAI API | openai.com | `OPENAI_API_KEY` | \$0.006/min (Whisper API) + LLM tokens | No streaming STT via API |

---

## Optional / Enhancement Keys

| Service | Purpose | Key Name | Cost |
|---------|---------|----------|------|
| AssemblyAI | Alternative streaming STT | `ASSEMBLYAI_API_KEY` | \$0.37/hr real-time, \$0 tier (verify) |
| Google Cloud STT | Alternative streaming STT | GCP service account JSON | \$0.016/min streaming (verify) |
| Anthropic Claude | Alternative LLM | `ANTHROPIC_API_KEY` | Paid only |

---

## Permission Requirements

| Resource | Why | When |
|----------|-----|------|
| Browser microphone permission | Capture user's voice | Phase 3 |
| Browser screen/tab share permission | Capture interviewer's audio via tab | Phase 3 |
| Windows WASAPI (native) | Capture Zoom/Teams system audio | Phase 10 only |

---

## Environment Variable Reference

```env
# LLM Provider (pick one)
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AIza...

# STT Provider (pick one; leave blank to use local Whisper)
DEEPGRAM_API_KEY=...
ASSEMBLYAI_API_KEY=...

# Provider selection
STT_PROVIDER=whisper          # whisper | deepgram | assemblyai | openai
LLM_PROVIDER=gemini           # openai | gemini

# Models
OPENAI_MODEL=gpt-4o-mini
GEMINI_MODEL=gemini-2.0-flash
WHISPER_MODEL_SIZE=base       # tiny | base | small | medium | large-v3

# Storage
STORAGE_PATH=./storage

# App
APP_SECRET=change-me-random-string
ENVIRONMENT=development
LOG_LEVEL=INFO
```

---

## Accounts to Create Before Phase 4

1. **Google AI Studio** (free) — https://aistudio.google.com → Get API key → set `GOOGLE_API_KEY`
2. **Deepgram** (optional, for cloud STT) — https://deepgram.com → Create project → API key

That's it. Local Whisper + Gemini Free = \$0/month for personal use.
