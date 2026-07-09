# AI Interview Coach — Production Roadmap

A phased plan to take this project from a working prototype to a production-ready
product. Ordered by dependency and risk: cleanup → security → data → product loop
→ eval/observability → frontend → deploy → scale.

**Current state:** a working single-user prototype. Voice pipeline runs on
`livekit-agents` 1.x with Cerebras + Deepgram; job/resume are parsed and passed to
the agent via room metadata. Missing everything below the "runs on my machine" line:
auth, a database, persisted history, wired feedback/analytics UI, tests, evals,
observability, CI/CD, and deployment config.

> **Cross-cutting concerns** — Security, Privacy, Safety/Responsible-AI, Evals, and
> Observability span every phase. This roadmap schedules them *by phase*;
> [`CROSS_CUTTING.md`](CROSS_CUTTING.md) tracks them *by concern* (the end-to-end
> posture for each). Deployment specifics live in [`DEPLOYMENT.md`](DEPLOYMENT.md).

---

## Phase 0 — Cleanup & consolidation *(~1–2 days, low risk)*
- Keep `run_agent.py`; delete `run_agent_improved.py` and `agent_worker.py`; update docs.
- Central config module (`app/core/config.py` via `pydantic-settings`) — one typed,
  validated source for all env vars; replaces scattered `os.getenv`.
- Standardize env-var naming on `LIVEKIT_*`; fix `env.example` casing; drop the
  `or os.getenv("LiveKit_...")` fallbacks.
- Remove dead code: `PyPDF2` dep, `/agent/start`, non-LLM `/parse-link`.
- **Done when:** one worker, one config source, no unused deps, docs match reality.

## Phase 1 — Security & API hardening *(~2–4 days, do before any public URL)*
- Auth (Clerk/Auth0/Supabase Auth, or JWT sessions); protect every endpoint.
- Lock down `/agent/join-token`: derive room/identity server-side from the
  authenticated user — never trust client-supplied identity.
- Fix CORS to an explicit allowlist (currently `["*"]` + credentials).
- Rate limiting (slowapi + Redis) on the paid endpoints (parse, token).
- Stop leaking exception text to clients; log server-side, return generic errors.
- Input limits: PDF size cap, JD length cap, content-type checks.
- Rotate the local `.env` API keys before they touch a server.
- **Done when:** unauthenticated requests are rejected; one user can't burn another's quota.

## Phase 2 — Persistence layer *(~3–5 days)*
- Postgres + SQLAlchemy 2.0 + Alembic (or Supabase).
- Models: `User`, `Interview` (job + resume snapshot, room, status, timestamps),
  `Turn`/`Transcript`, `Feedback` (scores).
- Replace the in-memory analytics dict with DB queries.
- **Done when:** interviews survive restarts and belong to a user.

## Phase 3 — Complete the product loop *(~3–5 days)*
- Capture the interview transcript (persist user/agent turns from the session).
- Wire feedback: End Interview → `/feedback/generate` → scored feedback screen.
  Fix `calculate_interview_metrics` taking a bare `str` (FastAPI treats it as a
  query param, not a body).
- History/analytics dashboard: past interviews, scores, trends.
- **Done when:** a candidate finishes and gets a saved, actionable score.

## Phase 4 — Evals, Testing & Observability *(start early; deepen ~3–5 days)*

This app is LLM-driven end-to-end **and** real-time voice, so evals and observability
are first-class, not a sub-bullet of testing. Cheap wins (the metrics hook, extraction
evals) should land during Phase 0/3; judge-based evals depend on Phase 3 transcripts.

### 4a. Testing (traditional)
- Backend: `pytest` + `httpx`; mock Cerebras/LiveKit/Deepgram; cover parsing, token
  creation, feedback scoring. Convert the manual `test_*.py` scripts to real tests.
- Frontend: Vitest + React Testing Library; a smoke test of setup → interview.

### 4b. Evals — three LLM surfaces, three strategies
1. **Job/resume extraction** (`app/llm/extraction.py`) — structured output, the easy one.
   Golden dataset of ~30–50 labeled JDs → assert schema validity, per-field accuracy,
   hallucination rate. Cheap, deterministic, CI-gateable. This is the safety net when
   swapping models (e.g. the forced `llama3.3-70b` → `gpt-oss-120b` migration).
2. **Interviewer agent quality** (`app/llm/interviewer.py`) — open-ended, the hard one.
   - Scripted scenarios: simulated candidate transcript → assert phase adherence,
     job-relevant questions, one-at-a-time, and that it does **not** answer for the candidate.
   - LLM-as-judge on transcripts against a rubric (relevance, professionalism,
     non-repetition, personalization), scored 1–5. Use a strong judge model.
3. **Feedback scoring** (`app/llm/feedback.py`) — the riskiest; users trust the score.
   - Calibration: score the same transcript N times → measure variance.
   - Groundedness: feedback must cite what's actually in the transcript.
   - Rubric adherence across runs.

**Voice-layer evals:** STT accuracy (WER) on reference audio; latency SLOs from SDK
metrics (`LLMMetrics.ttft`, `TTSMetrics.ttfb`, `EOUMetrics.end_of_utterance_delay` —
target perceived round-trip < ~1.5s); turn-taking (false interruptions vs missed endpoints).

**Tooling & process:** start with Promptfoo (lightweight, YAML, provider-agnostic,
CI-native); graduate to Braintrust/Langfuse for dataset management + a prod-trace→eval
loop. Prompts are code — gate CI on evals whenever interviewer instructions or the
feedback rubric change. Sample real interviews (needs Phase 3 storage), judge them
offline, catch drift on model swaps.

### 4c. Observability — mostly free from the SDK
Highest-leverage 30 minutes in the roadmap: hook the session's metrics event in the
agent worker.

```python
from livekit.agents import metrics, MetricsCollectedEvent

usage = metrics.UsageCollector()

@session.on("metrics_collected")
def _on_metrics(ev: MetricsCollectedEvent):
    metrics.log_metrics(ev.metrics)   # per-turn ttft / ttfb / EOU delay
    usage.collect(ev.metrics)         # aggregate for cost

# at interview end: usage.get_summary() -> tokens, tts_characters, stt_audio_duration -> $
```

Build out from there:
- **LLM o11y:** cost/interview, cached-token ratio, latency, error rate by provider.
  Trace prompts/completions with Langfuse or Helicone (Helicone = one-line `base_url`
  swap since Cerebras is OpenAI-compatible).
- **Provider failures mid-call:** subscribe to `ErrorEvent`/`LLMError`/`STTError`/`TTSError`
  — otherwise a Deepgram hiccup just sounds like awkward silence.
- **Traces:** OpenTelemetry across FastAPI → LLM → LiveKit session, correlated by `interview_id`.
- **Metrics/dashboards:** LiveKit's built-in `prometheus_port` → Grafana; add app metrics
  (interviews started vs completed, drop rate).
- **Errors:** Sentry on backend and frontend.
- **SLOs + alerting:** turn-latency p95 < 1.5s, completion rate, cost/interview.
- **Cost attribution** per user/interview (LiveKit + LLM + STT + TTS each meter separately).

- **Done when:** every interview emits latency + cost telemetry; prompt/model changes
  are gated by evals in CI; provider errors page someone.

## Phase 5 — Frontend maturity *(~3–5 days)*
- Decompose the 380-line `App.tsx` into components (`JobInput`, `ResumeUpload`,
  `ReadinessPanel`, `InterviewRoom`, `FeedbackReport`) + a `useInterviewRoom` hook.
- Type the `job` state properly (generate types from the backend OpenAPI schema).
- Routing (React Router): setup / interview / history / feedback.
- React Query for server state; robust mic-permission + reconnection handling; a11y; mobile.
- **Done when:** no god-component, no `any`, network/mic failures handled gracefully.

## Phase 6 — Deployment & DevOps *(~3–5 days)*
- Dockerize three things separately: API, agent worker (long-running, scales
  differently — not serverless), frontend static build.
- Host: API + worker on Fly.io/Render/Railway; frontend on Vercel/Cloudflare.
- Secrets via platform vault, not `.env`.
- CI/CD (GitHub Actions): ruff + eslint, mypy + tsc, tests + evals, build, deploy.
- Health checks, graceful shutdown, worker autoscaling.
- **Done when:** push-to-deploy with health checks.

## Phase 7 — Scale, cost & compliance *(ongoing)*
- Cost controls: per-user quotas, max interview duration, concurrency caps.
- Privacy: you store resumes + voice — privacy policy, retention limits, GDPR delete.
- Caching, progress dashboards, teams/multi-tenancy.

---

## Where evals & observability live in the codebase

They have opposite lifecycles, so they live in different places.

| Concern | Nature | Location | Analogy |
|---|---|---|---|
| **Observability** | Cross-cutting, runtime | `app/observability/` (config) + inline hooks | Logging |
| **Evals** | Offline, not shipped | top-level `evals/` | `tests/` |
| **AI core** | The thing both measure | `app/llm/` (pure, importable) | Domain layer |

**The enabling refactor:** pull prompts and LLM calls out of the FastAPI handlers and
the agent worker into a pure, importable `app/llm/` package. Then the app *and* the
eval harness call the same functions — no HTTP or LiveKit needed to run an eval.

```
backend/
  app/
    core/config.py            # settings (Phase 0)
    llm/                      # ← AI core: pure, importable, no transport
      prompts.py              #   versioned prompt templates + rubrics
      extraction.py           #   job/resume extraction
      interviewer.py          #   interviewer instruction builder
      feedback.py             #   feedback scoring
    observability/            # ← o11y: configure once, instrument inline
      tracing.py              #   OpenTelemetry setup
      metrics.py              #   LiveKit metrics hook + exporters
      logging.py              #   structlog config
    routers/                  # thin transport; call app/llm/*
  evals/                      # ← offline, CI-run, imports app/llm/*
    datasets/                 #   golden sets (JDs, transcripts)
    extraction/ interviewer/ feedback/
    judges/                   #   LLM-judge rubrics
    runner.py
  tests/                      # unit/integration
```

**Principles (industry best practice):**
1. **Prompts are code** — versioned in `app/llm/prompts.py`, never inline strings
   scattered across handlers. This is what makes them eval-able and diff-able.
2. **Separate the AI core from transport** — the eval harness imports `app/llm/`
   directly; it must not need to boot FastAPI or connect to LiveKit.
3. **Observability can't be fully "separated"** — the config lives in one module, but
   the instrumentation calls sit inline on the code they measure. Central setup +
   local hooks.
4. **Evals are offline tooling** — a sibling of `tests/`, run in CI, excluded from the
   deployed image. At scale, back them with a platform (Braintrust/Langfuse).
5. **The two connect at the data layer** — production traces (o11y) become eval
   datasets (the prod→eval loop). Instrument first; it feeds your eval sets later.
