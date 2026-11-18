# Production Deployment Guide — Interview Copilot AI

This repository is configured for **split production deployment** (recommended) or single-host Docker Compose self-hosting:

| Component | Recommended Host | Why |
|-----------|------------------|-----|
| **Frontend (Next.js 15)** | **Vercel** (`Root Directory: frontend`) | Global edge CDN + automatic HTTPS (required by browsers for `getUserMedia` mic and `getDisplayMedia` screen sharing) |
| **Backend (FastAPI + WebSockets + Whisper + SQLite)** | **Railway** (`Root Directory: backend`) | Long-lived Docker container, full `wss://` WebSocket streaming (`/ws/audio/{id}`, `/ws/session/{id}`), persistent `/data` volume |

---

## 1. Deploy Backend on Railway

1. Create a Railway project and attach this GitHub repository with **Root Directory** set to `backend` (Railway automatically reads `backend/railway.json` and builds `backend/Dockerfile`).
2. Attach a **Persistent Volume** mounted at `/data`.
3. Configure environment variables on the Railway service:

| Variable | Example / Value |
|----------|-----------------|
| `ENVIRONMENT` | `production` |
| `STORAGE_PATH` | `/data` |
| `GOOGLE_API_KEY` | Your Gemini API key from Google AI Studio |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` |
| `LLM_PROVIDER` | `gemini` |
| `STT_PROVIDER` | `whisper` *(or `deepgram` with `DEEPGRAM_API_KEY` for lower CPU usage)* |
| `WHISPER_MODEL_SIZE` | `base` *(or `tiny` on smaller RAM plans)* |
| `APP_SECRET` | Random 64-char hex secret |
| `CORS_ORIGINS` | `https://<your-vercel-domain>.vercel.app` |
| `CORS_ORIGIN_REGEX` | `https://.*\.vercel\.app` *(optional, for Vercel preview URLs)* |

4. Generate a public Railway domain (e.g. `https://interview-copilot-api.up.railway.app`) and verify `GET /health` returns `{"status": "ok"}`.

---

## 2. Deploy Frontend on Vercel

1. Import this GitHub repository into Vercel and set **Root Directory** to `frontend`.
2. Set the environment variable in Vercel Project Settings (Production & Preview):

| Variable | Value |
|----------|-------|
| `NEXT_PUBLIC_API_URL` | `https://<your-railway-domain>.up.railway.app` |
| `NEXT_PUBLIC_WS_URL` | *(Optional — automatically derived as `wss://<your-railway-domain>.up.railway.app`)* |

3. Deploy to production (`main` branch auto-deploys on push).
4. Copy the final Vercel URL back into Railway's `CORS_ORIGINS` variable if you aren't using `CORS_ORIGIN_REGEX`.

---

## 3. Self-Hosting with Docker Compose

```bash
copy .env.example .env   # add GOOGLE_API_KEY & APP_SECRET
docker compose up -d --build
```

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000/health`
