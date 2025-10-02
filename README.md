## Voice Interviewer (FastAPI + React)

This project scaffolds a real-time interview practice agent using a FastAPI backend and a React (Vite) frontend. The design follows the LiveKit + Cerebras tutorial “Interviewer Voice Agent with LiveKit” and prepares integration of STT, LLM, and TTS in a production-ready structure.

Reference: Interviewer Voice Agent with LiveKit (Cerebras) — see the Cookbook page: `https://inference-docs.cerebras.ai/cookbook/agents/livekit`.

### Features
- FastAPI backend with CORS and health check.
- Utilities to parse job pages (BeautifulSoup) and PDF resumes (pdfplumber).
- Agent skeleton mirroring LiveKit AgentSession with Cerebras LLM and Deepgram STT/TTS.
- React frontend (Vite) to:
  - Submit a job link and resume PDF URL
  - Preview parsed job/resume
  - Start agent and receive LiveKit room URL (placeholder)

### Repo Structure
- `backend/`
  - `app/main.py`: FastAPI app factory, CORS, `/health`.
  - `app/routers/utils.py`: `/utils/parse-link`, `/utils/parse-pdf`.
  - `app/routers/agent.py`: `/agent/start` (returns LiveKit room URL placeholder).
  - `app/agents/interviewer.py`: LiveKit+Cerebras agent coroutine skeleton.
  - `requirements.txt`: backend dependencies.
  - `env.example`: environment variable template.
- `frontend/`
  - Vite + React TypeScript app with simple UI in `src/ui/App.tsx`.

### Prerequisites
- Python 3.11+ (recommended)
- Node 18+ and PNPM/NPM/Yarn

### Backend Setup
1. Create and activate a virtualenv.
2. Install dependencies:
   - `pip install -r backend/requirements.txt`
3. Copy env file:
   - `cp backend/env.example backend/.env` (or set environment variables in your shell)
4. Run the API:
   - `uvicorn uvicorn_app:app --host 0.0.0.0 --port 8000 --reload` from `backend/`

Environment variables (from `backend/env.example`):
- `LiveKit_API_KEY`, `LiveKit_API_SECRET`, `LiveKit_URL`
- `CEREBRAS_API_KEY`, `CEREBRAS_MODEL`
- `DEEPGRAM_API_KEY`, `DEEPGRAM_TTS_MODEL`
- `AGENT_TEMPERATURE`

Notes:
- The `/agent/start` endpoint returns `room_wss` from `LiveKit_URL`. Replace with join token flow as you integrate the LiveKit server.
- Install optional voice agent deps only if you intend to run the agent locally.

### Frontend Setup
1. Install dependencies: `cd frontend && npm install` (or `pnpm i`)
2. Start dev server: `npm run dev`
3. Set API base via Vite env (optional): create `frontend/.env.local` with `VITE_API_BASE=http://localhost:8000`

### How it Works (High Level)
1. Parse job link → clean text → (later) structured fields via Cerebras LLM.
2. Parse resume PDF → full text using `pdfplumber`.
3. Start agent → front end receives room WS URL → LiveKit client connects; voice pipeline handles VAD, STT, LLM, TTS.

### Suggested Improvements
- Replace heuristic parsing with structured JSON output using Cerebras with `response_format` per tutorial.
- Implement LiveKit server join token issuance and client SDK integration in the frontend.
- Add proper auth (JWT) and rate limiting to backend endpoints.
- Store conversation context and session telemetry (e.g., Postgres) for analytics.
- Provide on-device/browser-side VAD fallback for low-latency mic controls.
- Add caching for job link fetch and PDF parsing to reduce redundant work.
- Add e2e tests (Playwright) and backend tests (pytest) for stability.
- Containerize with multi-stage Dockerfiles; ensure deterministic builds.

### Credits
- Based on the Cerebras Cookbook article “Interviewer Voice Agent with LiveKit”.


