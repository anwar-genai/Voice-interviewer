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
Phase retros (challenges faced + improvements): `PHASE0.md`–`PHASE6.md`.

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
  done, on `main`.
- **Phase 4** (quality: pytest suite incl. API tests with mocked LLM; frontend Vitest
  smoke test; full eval harness — interviewer LLM-judge, fairness counterfactuals,
  semantic groundedness, voice SLO check, prod→eval export; **name-blind feedback
  scoring** (the fairness eval caught scores moving 2 points on the candidate's name
  alone); PII redaction, llm_trace logs, Sentry hook, provider-error events; CI with
  an eval gate on prompt changes) — done, on `main`.
- **Phase 5** (frontend maturity: decomposed the 380-line `App.tsx` into per-screen
  components + a `useInterviewRoom` hook + an `InterviewProvider` context; React Router
  (deep-linkable feedback/history, refresh-safe, nav hidden mid-interview); hand-written
  API types (kills every `any`, no OpenAPI codegen); graceful mic-permission +
  reconnection handling; self-serve data-deletion UI + AI-transparency; a11y + mobile;
  component + api tests; **"On Air" visual redesign** — pine/amber identity with
  waveform / VU-meter / score-ring canvas instruments) — done, on `main`.
- **Phase 6** (deployment & DevOps: one backend Docker image — API + worker as two
  Fly process groups in `backend/fly.toml` — with health checks, graceful drain,
  worker Prometheus→Grafana metrics, and Alembic migrations as the release command;
  frontend stays static (Vercel/CF Pages, no container); CI gains ruff + tsc gates,
  a push-to-deploy job (skips until `FLY_API_TOKEN` exists), and Dependabot) — done.
  **The one-time account setup (Fly launch, secrets + key rotation, Vercel import)
  is a runbook the user executes** — see `DEPLOYMENT.md` § Runbook.
- **Next:** first real deploy (runbook above), then Phase 7 (scale, cost & compliance).

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
cd backend && python -m pytest -q          # full test suite (mocked LLM + SQLite; each tests/*.py also runs standalone)
cd frontend && npm test                    # Vitest smoke test
cd backend && python -m evals.runner       # eval suites (call Cerebras): extraction, interviewer, feedback, fairness
cd backend && python -m evals.voice_slo agent.log    # voice SLOs (p95 latency) from a captured worker log
cd backend && python -m evals.export_prod  # prod->eval export (PII-redacted, output gitignored)

# Lint + deploy (see DEPLOYMENT.md § Runbook for one-time setup)
cd backend && ruff check .                 # same gate CI runs
cd backend && docker build -t voice-interviewer .   # verify the image locally
cd backend && fly deploy                   # API + worker; migrations run first
```

CI (`.github/workflows/`): `ci.yml` runs backend ruff+pytest + frontend test/build
(`npm run build` now type-checks via `tsc --noEmit`) on every push/PR, then deploys
`main` to Fly — the deploy step skips cleanly until the `FLY_API_TOKEN` repo secret
exists; `evals.yml` gates changes to `app/llm/**` or `evals/**` on the eval suites
(needs the `CEREBRAS_API_KEY` repo secret — without it the gate fails closed).
Dependabot files weekly dependency-update PRs (pip / npm / actions).

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
- **Rate limiting** is in-process (per-user, per-minute) — why `fly.toml` keeps the
  API at one machine. Move to Redis (Upstash) before scaling `api` past 1. See
  `app/core/ratelimit.py`.
- **Secrets.** Real provider keys sit in `backend/.env` (gitignored; `.dockerignore`
  keeps it out of images). Phase 1 flagged: those local keys count as exposed —
  generate fresh ones when you run `fly secrets set` (DEPLOYMENT.md runbook step 2).
  `env.example` files list every setting.
- **Evals & error tracking.** The LLM judge (`EVAL_JUDGE_MODEL`, default
  `zai-glm-4.7`) must exist on your Cerebras account — models come and go, and a
  404 means "pick another from `GET /v1/models`". Sentry is dormant until
  `SENTRY_DSN` is set; once set, every `logger.error`/`exception` (LLM failures,
  worker `provider_error` events) becomes an alerting event.
- **Style:** minimal / no speculative abstractions (ponytail). Deliberate shortcuts
  are marked with `ponytail:` comments naming the ceiling + upgrade path.
```
