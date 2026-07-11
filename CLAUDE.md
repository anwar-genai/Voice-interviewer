# CLAUDE.md

Orientation for anyone (human or agent) picking this repo up cold. Keep it short —
the *plan* lives in `ROADMAP.md`; this file is status + how-to-run + gotchas.

## What this is

AI Interview Coach: a voice mock-interview app. React/Vite frontend, FastAPI backend,
and a separate LiveKit agent worker running the voice pipeline
(Deepgram STT/TTS + Cerebras LLM on `livekit-agents` 1.x). Auth via Supabase.

## Layout

```
backend/
  app/
    core/        config (pydantic-settings), auth (Supabase JWT), ratelimit
    llm/         pure, importable AI core: prompts, extraction, interviewer, feedback
    observability/  logging + voice metrics (latency/cost)
    db/          SQLAlchemy models (Interview/Turn/Feedback), session, retention
    routers/     thin HTTP layer -> app/llm
  alembic/       DB migrations (schema as code)
  run_agent.py   the LiveKit agent worker (voice pipeline). Run separately from the API.
  evals/         offline eval suites (imports app/llm directly)
  tests/         pytest-style checks (run with plain python too)
frontend/src/    Vite + React; ui/App.tsx is the main component, lib/supabase.ts the auth client
```

Plan & rationale: `ROADMAP.md` (by phase), `CROSS_CUTTING.md` (by concern:
security/privacy/safety/evals/o11y), `DEPLOYMENT.md` (how to ship).
Phase retros (challenges faced + improvements): `PHASE0.md`–`PHASE3.md`.

## Status

- **Phase 0** (foundation: config, `app/llm` core, metrics, evals) — done, on `main`.
- **Phase 1** (auth, input hardening, prompt-injection isolation) — done, on `main`.
- **Turn-detection fix** (semantic end-of-utterance) — done, on `main`.
- **Phase 2** (persistence: SQLAlchemy + Alembic on Supabase Postgres; Interview/Turn/
  Feedback; owner-scoped list/get/erasure; retention TTL) — done, on `main`.
- **Phase 3** (product loop: agent worker persists transcript turns + interview
  lifecycle status; `/feedback/generate` scores the saved transcript once and stores
  it, `/feedback/{id}` re-reads it; feedback report + history UI; groundedness guard +
  output-safety/on-task prompt hardening; feedback calibration/groundedness evals) —
  branch `phase-3-product-loop`.
- **Next:** Phase 4 (testing, full eval harness, deeper observability).

Work is phase-by-phase per `ROADMAP.md`, one commit per phase; non-phase fixes
(like turn-detection) get their own branch off `main`.

## Run it

```bash
# API (terminal 1)
cd backend && ./venv/Scripts/activate && uvicorn uvicorn_app:app --reload --port 8000
# Agent worker (terminal 2) — the voice pipeline
cd backend && python run_agent.py dev
# Frontend (terminal 3)
cd frontend && npm run dev            # http://localhost:5173

# DB migrations (needs DATABASE_URL)
cd backend && python -m alembic upgrade head          # apply migrations
cd backend && python -m alembic revision --autogenerate -m "msg"   # after model changes
cd backend && python -m app.db.retention              # purge expired interviews (cron target)

# Checks
cd backend && python tests/test_phase1_security.py   # 8 security checks
cd backend && python tests/test_persistence.py       # ownership, cascade erasure, retention
cd backend && python tests/test_phase3.py            # transcript capture, feedback wiring, groundedness
cd backend && python tests/test_stt_fairness.py      # STT keyword mining + transcription-aware rubric
cd backend && python -m evals.runner extraction      # eval suite (calls Cerebras)
cd backend && python -m evals.runner feedback        # calibration + groundedness (calls Cerebras)
```

## Gotchas / config that bites

- **Auth (Supabase).** `AUTH_ENABLED=true` fails closed. This project's Supabase
  signs tokens with **asymmetric keys (ES256)**, verified via JWKS — so the backend
  needs only `SUPABASE_URL`, not a JWT secret. The backend also still accepts HS256
  (legacy shared secret) by routing on the token's `alg`. For backend-only local
  testing without Supabase, set `AUTH_ENABLED=false` (the frontend still needs a real
  Supabase session to render, so this is API-only). Frontend env:
  `VITE_SUPABASE_URL` + `VITE_SUPABASE_PUBLISHABLE_KEY` (the publishable key, not the
  secret/service_role).
- **Turn detection.** `TURN_DETECTION_MODEL=english` (default) is downloaded and is
  what makes turn-taking responsive. Tune `MIN/MAX_ENDPOINTING_DELAY_SECONDS` for
  pace. Noisy room (fan) interrupting the agent mid-sentence? Raise
  `VAD_ACTIVATION_THRESHOLD` (~0.65) and `MIN_INTERRUPTION_DURATION_SECONDS` (~1.0). To use **multilingual** instead: set `TURN_DETECTION_MODEL=multilingual` and
  run `python run_agent.py download-files` — the multilingual ONNX
  (`livekit/turn-detector`, ref `v0.3.0-intl`) was left partially downloaded because
  English is the default; that command finishes it. Models cache under
  `~/.cache/huggingface/hub/models--livekit--turn-detector`.
- **Database (`DATABASE_URL`).** Supabase Postgres via the **session pooler**
  (`...pooler.supabase.com:5432`) — *not* the direct connection (IPv6-only, usually
  unreachable) or the transaction pooler (port 6543, breaks Alembic DDL). Scheme must
  be `postgresql+psycopg://` (psycopg3). Keep the DB password alphanumeric — symbols
  like `@ % :` are URL-reserved and corrupt the connection string. Migrations are
  Alembic; owner = the Supabase user id, so there's no `users` table.
- **Rate limiting** is in-process (per-user, per-minute) — fine for one worker; needs
  Redis when the API scales to multiple workers (Phase 6). See `app/core/ratelimit.py`.
- **Secrets.** Real provider keys sit in `backend/.env` (gitignored). Phase 1 flagged:
  rotate them and move to a platform vault before deploying. `env.example` files list
  every setting.
- **Style:** minimal / no speculative abstractions (ponytail). Deliberate shortcuts
  are marked with `ponytail:` comments naming the ceiling + upgrade path.
```
