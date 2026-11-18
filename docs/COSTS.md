# Cost Estimates — Interview Copilot AI

Last updated: 2026-11-18

> All costs are estimates based on publicly listed pricing. Verify before choosing a provider.

---

## Usage Assumptions (Personal Use)

| Metric | Value |
|--------|-------|
| Interviews per week | 3–5 |
| Average interview duration | 45–60 minutes |
| Questions per interview | 15–25 |
| Average answer tokens | 300 tokens |
| STT: audio per interview | ~50 minutes of actual speech |

---

## Scenario 1: 100% Free / Local (Recommended Starter)

| Component | Provider | Monthly Cost |
|-----------|---------|-------------|
| STT | faster-whisper (local) | \$0 |
| LLM | Google Gemini 2.0 Flash (free tier) | \$0 |
| DB | SQLite local | \$0 |
| Hosting | Local machine | \$0 |
| **Total** | | **\$0/month** |

**Limitations:**
- faster-whisper on CPU: ~2–5 sec chunk latency (acceptable for personal use)
- Gemini free tier: 15 req/min, 1500 req/day — plenty for interview use
- Requires local compute (fine for personal workstation)

---

## Scenario 2: Cloud STT + Free LLM

| Component | Provider | Monthly Cost |
|-----------|---------|-------------|
| STT | Deepgram Nova-2 | \$0 (12,000 min/month free ⚠️ verify) |
| LLM | Google Gemini 2.0 Flash | \$0 (free tier) |
| **Total** | | **\$0/month** |

**Advantage:** True streaming STT → ~200–400ms latency improvement.

**Verification required:** Deepgram free tier terms at https://deepgram.com/pricing

---

## Scenario 3: OpenAI Everything

| Component | Provider | Per Interview | Monthly (15 interviews) |
|-----------|---------|--------------|------------------------|
| STT | OpenAI Whisper API | ~\$0.27 (45 min × \$0.006/min) | ~\$4.00 |
| LLM | GPT-4o-mini | ~\$0.06 (20 Q × 300 tokens) | ~\$0.90 |
| **Total** | | **~\$0.33** | **~\$5/month** |

---

## Scenario 4: OpenAI GPT-4o (High Quality)

| Component | Provider | Per Interview | Monthly (15 interviews) |
|-----------|---------|--------------|------------------------|
| STT | OpenAI Whisper API | ~\$0.27 | ~\$4.00 |
| LLM | GPT-4o | ~\$0.75 (20 Q × 500 tokens) | ~\$11.25 |
| **Total** | | **~\$1.00** | **~\$15/month** |

---

## Per-Call Cost Breakdown (reference)

| Provider | Model | Input | Output |
|---------|-------|-------|--------|
| OpenAI | gpt-4o-mini | \$0.15/1M tokens | \$0.60/1M tokens |
| OpenAI | gpt-4o | \$2.50/1M tokens | \$10.00/1M tokens |
| Google | gemini-2.0-flash | Free (15 req/min) | Free |
| Google | gemini-1.5-pro | \$3.50/1M tokens | \$10.50/1M tokens |
| Deepgram | Nova-2 | \$0.0043/min streaming | — |
| OpenAI | whisper-1 | \$0.006/min | — |

> ⚠️ All pricing approximate. Verify at provider pricing pages before production use.

---

## Recommendation

**Start with Scenario 1 (fully local/free).**
- Configure `GOOGLE_API_KEY` for Gemini 2.0 Flash.
- Use `faster-whisper` base model locally.
- Upgrade to Deepgram only if STT latency is a problem.
- The settings panel makes provider switching trivial.
