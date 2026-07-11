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
    routers/     thin HTTP layer -> app/llm
  run_agent.py   the LiveKit agent worker (voice pipeline). Run separately from the API.
  evals/         offline eval suites (imports app/llm directly)
  tests/         pytest-style checks (run with plain python too)
frontend/src/    Vite + React; ui/App.tsx is the main component, lib/supabase.ts the auth client
```

Plan & rationale: `ROADMAP.md` (by phase), `CROSS_CUTTING.md` (by concern:
security/privacy/safety/evals/o11y), `DEPLOYMENT.md` (how to ship).

## Status

- **Phase 0** (foundation: config, `app/llm` core, metrics, evals) — done, on `main`.
- **Phase 1** (auth, input hardening, prompt-injection isolation) — done, on `main`.
- **Turn-detection fix** (semantic end-of-utterance) — done, branch `fix-turn-detection`.
- **Next:** Phase 2 (Postgres + schema: User/Interview/Turn/Feedback; retention/deletion).
  The transcript "look back at Q&A" feature is Phase 2 (store) + Phase 3 (capture + view).

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

# Checks
cd backend && python tests/test_phase1_security.py   # 8 security checks
cd backend && python -m evals.runner extraction      # eval suite (calls Cerebras)
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
  pace. To use **multilingual** instead: set `TURN_DETECTION_MODEL=multilingual` and
  run `python run_agent.py download-files` — the multilingual ONNX
  (`livekit/turn-detector`, ref `v0.3.0-intl`) was left partially downloaded because
  English is the default; that command finishes it. Models cache under
  `~/.cache/huggingface/hub/models--livekit--turn-detector`.
- **Rate limiting** is in-process (per-user, per-minute) — fine for one worker; needs
  Redis when the API scales to multiple workers (Phase 6). See `app/core/ratelimit.py`.
- **Secrets.** Real provider keys sit in `backend/.env` (gitignored). Phase 1 flagged:
  rotate them and move to a platform vault before deploying. `env.example` files list
  every setting.
- **Style:** minimal / no speculative abstractions (ponytail). Deliberate shortcuts
  are marked with `ponytail:` comments naming the ceiling + upgrade path.
```
