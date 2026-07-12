# Phase 6 — Deployment & DevOps

What shipped, what was genuinely hard, and what I'd improve. Companion to
`ROADMAP.md` Phase 6.

## What shipped

The roadmap's bar: push-to-deploy with health checks, green gates, and live
dashboards.

- **One Docker image, two processes** — `backend/Dockerfile` builds a single
  image; `fly.toml`'s `[processes]` runs it as `api` (uvicorn) and `worker`
  (`run_agent.py start`). Same code, same deps, one build — a separate worker
  image would have been two Dockerfiles differing by one line. The turn-detector
  model is baked in at build time so worker cold-starts don't pull ~100MB from
  HuggingFace. Non-root user; `.dockerignore` hard-excludes `.env`.
- **The frontend stays static** — no third container. The recommended host
  (Vercel/Cloudflare Pages) builds `frontend/` from git with `VITE_API_BASE` +
  Supabase vars; a container would only re-wrap what a CDN does better.
- **Health checks & graceful drain** — API: the existing `GET /health` wired to
  Fly's `http_service` checks. Worker: `livekit-agents` already serves a health
  endpoint on :8081 in `start` mode — zero code, just a `[checks]` block.
  Deploys SIGTERM the worker, which stops accepting rooms and drains; Fly's
  `kill_timeout` is maxed at 5m (see challenge 2).
- **Migrations as the release command** — `alembic upgrade head` runs in a
  throwaway machine before new code starts. Push-to-deploy includes the schema.
- **Dashboards** — the SDK's built-in `prometheus_port` (one `WorkerOptions`
  kwarg off a new `PROMETHEUS_PORT` setting) + fly.toml `[[metrics]]` → Fly's
  managed Grafana at fly-metrics.net. Sentry was already wired in Phase 4; it
  goes live the moment the DSN secret is set.
- **CI gates grew** — `ruff check` on the backend (found exactly one issue: the
  intentional `uvicorn_app` re-export, fixed with `import app as app`);
  `tsc --noEmit` now runs inside `npm run build` (passed clean on first run —
  Phase 5's typing paid off); a `deploy` job runs on `main` after both gates
  and skips cleanly until `FLY_API_TOKEN` exists, so the pipeline is green
  before the Fly account is.
- **Dependency scanning** — Dependabot (pip/npm/actions, weekly). One YAML file;
  CI + the evals gate decide whether an update is safe to merge.
- **Runbook** — `DEPLOYMENT.md` § Runbook: the exact one-time commands (Fly
  launch, secrets-set-as-key-rotation, Vercel import, retention as a Fly
  scheduled machine, deploy token). That part needs the user's accounts, so it
  ships as steps, not code.

Deliberately **not** built (`ponytail:` where it's code, here where it's not):

| Skipped | Why / upgrade when |
|---|---|
| eslint + mypy | `tsc --noEmit` (zero new deps) covers the type-bug class; ruff covers Python correctness lints. Add eslint when a hooks-deps bug actually bites; mypy on an untyped-at-the-edges codebase is a phase of its own. |
| Frontend Dockerfile | Static host builds from git. Write it only if self-hosting behind nginx ever happens. |
| Redis rate limiting | fly.toml pins `api` to one machine, where the in-process limiter is correct. Upstash + a swap in `app/core/ratelimit.py` before `fly scale count api=2`. |
| Session-count autoscaling | The worker already reports load (`load_threshold=0.7`) so LiveKit stops dispatching to a busy one; adding machines is `fly scale count worker=N`. Automate only when manual scaling is a recurring chore. |
| Langfuse/OTel exporter | Still the Phase 4 decision: `llm_trace` logs now ship via `fly logs`; self-host Langfuse when real candidate transcripts need trace-level inspection. |
| WAF | TLS is automatic (Fly/Vercel edge), CORS enforced in-app, auth on every route. A WAF in front of an authed JSON API is Phase 7 posture, not Phase 6 need. |

## Challenges faced (and how they were solved)

### 1. Baking the model into the image vs. config that fails closed
`python run_agent.py download-files` is the supported way to pre-fetch the
turn-detector ONNX, but `main()` validates LiveKit/Cerebras/Deepgram config
*before* handing off to the CLI — correct at runtime (fail fast, fail closed),
hostile at build time, when no secrets exist (and must not: build args leak
into image history). Solution: dummy env values on that one `RUN` line. The
subcommand never connects to anything, so the values satisfy validation and
touch nothing. The alternative — weakening the validation with an "am I in a
build?" escape hatch — would have traded a build-time annoyance for a
runtime foot-gun.

### 2. Graceful drain has a platform ceiling, not an SDK one
The SDK side is generous: `drain_timeout` defaults to 1800s and the worker
stops taking new rooms on SIGTERM. But Fly force-kills at `kill_timeout` max
**300s** — so the *effective* grace for a live interview during a deploy is
5 minutes, whatever the SDK is willing to wait. There's no config that fixes
this, only honesty: fly.toml documents the ceiling and the mitigation (deploy
when idle). The general lesson: graceful shutdown is min(app, platform), and
the platform usually wins.

### 3. Verification found the environment, not the code, broken
First `docker build` failed instantly: Docker Desktop's Linux engine wasn't
running (the CLI answers `--version` fine without a daemon — a check that
proves less than it looks). Started the engine, built clean. The
`/health`-in-container smoke test then verified the image end-to-end:
dependency install, non-root user, model bake, uvicorn boot. The image is
2.15GB — almost all of it the voice stack (onnxruntime, noise cancellation,
baked models); acceptable for a persistent worker, and slimming it (multi-stage
build, API-only variant without the voice deps) is a known lever if image pull
time ever matters.

## What to improve next (feeds Phase 7)

- **Actually deploy** — everything past `git push` is runbook: Fly app +
  rotated secrets, Vercel import, `FLY_API_TOKEN` into GitHub. First deploy
  turns the CI deploy job from "skips cleanly" to real.
- **Redis rate limiting** — the first thing real traffic forces (it's the only
  thing pinning the API to one machine).
- **Per-interview cost attribution → quotas** — the usage summaries already
  exist; Phase 7 turns them into per-user caps.
- **Alerting on SLOs** — metrics are in Grafana now; alerts (p95 latency,
  provider-error rate) are a dashboard-side follow-up, no code.
