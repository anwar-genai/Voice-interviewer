# AI Interview Coach — Production Roadmap

A phased plan from working prototype to production. Ordered by dependency and risk.
Every item is tagged by concern so cross-cutting work lands in the phase it belongs to:

`[Feature]` product/functionality · `[Sec]` security · `[Priv]` privacy ·
`[Safety]` safety / responsible-AI · `[Evals]` evals & quality · `[Obs]` observability ·
`[Test]` testing · `[Infra]` build/deploy.

**Current state:** a working single-user prototype. Voice pipeline runs on
`livekit-agents` 1.x with Cerebras + Deepgram; job/resume are parsed and passed to the
agent via room metadata. Missing everything below the "runs on my machine" line.

> **Two views, kept in sync:** this roadmap is organized *by phase*.
> [`CROSS_CUTTING.md`](CROSS_CUTTING.md) is the same work organized *by concern*
> (end-to-end posture for Security/Privacy/Safety/Evals/Observability).
> [`DEPLOYMENT.md`](DEPLOYMENT.md) covers how to ship it.

## Concern × phase coverage

Proof that every concern is carried across the phases (● primary · ○ seed/partial).

| Concern | P0 | P1 | P2 | P3 | P4 | P5 | P6 | P7 |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| Feature / product | ● | | ● | ● | | ● | | ● |
| Security | ○ | ● | | | | | ● | |
| Privacy | | ● | ● | | ○ | ● | | ● |
| Safety / responsible-AI | | ● | | ● | ● | ● | | ● |
| Evals & quality | ○ | | | ● | ● | | ○ | |
| Observability | ● | | | ○ | ● | ○ | ● | |
| Testing | | | | | ● | ● | ● | |

---

## Phase 0 — Foundation & cleanup *(~2–3 days, low risk)*
Set up the structure everything else leans on.
- `[Feature]` Keep `run_agent.py`; delete `run_agent_improved.py` and `agent_worker.py`; update docs.
- `[Feature]` Central config module (`app/core/config.py`, `pydantic-settings`) — one typed, validated source; standardize `LIVEKIT_*` naming; drop the `LiveKit_*` fallbacks. Remove dead code (`PyPDF2`, `/agent/start`, non-LLM `/parse-link`).
- `[Feature]` **Enabling refactor:** extract prompts + LLM calls into a pure, importable `app/llm/` core (`prompts.py`, `extraction.py`, `interviewer.py`, `feedback.py`). This is what makes Safety, Evals, and Obs possible — do it now.
- `[Obs]` Drop in the LiveKit `MetricsCollectedEvent` hook + `UsageCollector` — free per-turn latency and per-interview cost. Highest-leverage 30 minutes in the plan.
- `[Sec]` ○ Config ready for injected secrets (no code change needed to move `.env` → vault later).
- `[Evals]` ○ Scaffold `evals/` with a tiny extraction golden-set (possible now that extraction is pure).
- **Done when:** one worker, one config source, `app/llm/` core in place, every interview emits latency + cost telemetry.

## Phase 1 — Security, identity & untrusted input *(~3–5 days — before any public URL)*
Harden the front door and everything untrusted that flows into a prompt.
- `[Sec]` Auth on every endpoint (Clerk/Auth0/Supabase or JWT sessions); authorization scoped to the owning user.
- `[Sec]` Lock down `/agent/join-token`: derive room/identity server-side; never trust client input.
- `[Sec]` CORS allowlist from config (kill `["*"]` + credentials); rate limiting (Redis) on paid endpoints; generic client errors (log details server-side); PDF-size / JD-length / content-type limits.
- `[Sec]` Secrets → platform vault; **rotate the current local keys**.
- `[Safety]` **Prompt-injection isolation** — JD, resume, and transcript are untrusted input concatenated into prompts today (e.g. `f"...from: {text}"` in `utils.py`). Delimit/structure them as *data, not instructions*; never let them override the system prompt or feedback rubric. Same surface as the input hardening above — belongs here.
- `[Priv]` Capture **consent** for voice recording + resume processing at entry (store the record in Phase 2's schema).
- **Done when:** unauthenticated requests are rejected, one user can't burn another's quota, and a malicious resume can't hijack the agent or its scoring.

## Phase 2 — Persistence & data lifecycle *(~3–5 days)*
Real data model, with privacy built into the schema — not bolted on later.
- `[Feature]` Postgres + SQLAlchemy 2.0 + Alembic (or Supabase). Models: `User`, `Interview` (job + resume snapshot, room, status, timestamps), `Turn`/`Transcript`, `Feedback`.
- `[Feature]` Replace the in-memory analytics dict with DB queries.
- `[Priv]` Retention TTL on transcripts/recordings; **user-initiated deletion** (GDPR erasure); data minimization (avoid raw-audio retention unless justified); persist the consent record from Phase 1.
- **Done when:** interviews survive restarts, belong to a user, and can be fully deleted on request.

## Phase 3 — Complete the product loop *(~3–5 days)*
Make it valuable end-to-end, with output-side safety where the model faces the user.
- `[Feature]` Capture the transcript (persist user/agent turns from the session).
- `[Feature]` Wire feedback: End Interview → `/feedback/generate` → scored feedback screen. Fix `calculate_interview_metrics` taking a bare `str` (FastAPI treats it as a query param, not a body).
- `[Feature]` History/analytics dashboard: past interviews, scores, trends.
- `[Safety]` Output guardrails in the wired feedback flow: **groundedness** (cite the actual transcript, no hallucinated strengths/weaknesses), output safety (no defamatory/discriminatory content), and on-task moderation for the live agent.
- `[Evals]` Feedback **calibration** (score-the-same-transcript variance) + groundedness evals — possible now that feedback is wired and transcripts exist.
- `[Obs]` ○ Emit interview lifecycle events (started/completed/dropped) for the dashboards.
- **Done when:** a candidate finishes and gets a saved, grounded, actionable score.

## Phase 4 — Quality: testing, evals & observability *(deepen; ~4–6 days)*
The systematic quality layer the earlier phases seeded.
- `[Test]` Backend `pytest` + `httpx` (mock Cerebras/LiveKit/Deepgram); frontend Vitest + RTL smoke test. Convert the manual `test_*.py` scripts.
- `[Evals]` Full harness in `evals/`: extraction golden-set (expand), interviewer scripted-scenario + LLM-judge, voice SLOs (WER, `ttft`/`ttfb`, turn-detection). Gate CI on evals when prompts change. Strong, *different* judge model. Prod→eval loop feeding from telemetry.
- `[Safety]` **Bias & fairness evals** — guard feedback scoring against name/gender/accent/phrasing influence (needs the eval harness). Document intended use ("coaching, not screening").
- `[Obs]` Deepen: prompt/completion tracing (Langfuse/Helicone), OpenTelemetry across FastAPI → LLM → session (correlated by `interview_id`), Sentry, provider-error events (`LLMError`/`STTError`/`TTSError`), SLOs + alerting.
- `[Priv]` ○ **PII redaction** before resumes/transcripts enter logs, traces, or eval datasets.
- **Done when:** prompt/model changes are gated by evals in CI, provider errors page someone, and no PII leaks into the o11y layer.

## Phase 5 — Frontend maturity *(~3–5 days)*
Product-grade UI, including the user-facing privacy/transparency surface.
- `[Feature]` Decompose the 380-line `App.tsx` into components (`JobInput`, `ResumeUpload`, `ReadinessPanel`, `InterviewRoom`, `FeedbackReport`) + a `useInterviewRoom` hook. Type `job` properly (generate from OpenAPI). Routing (React Router). React Query for server state; robust mic-permission + reconnection handling; a11y; mobile.
- `[Priv]` Consent UI and a self-serve **data-deletion** flow (front-end for Phase 2's erasure).
- `[Safety]` **Transparency** — clearly disclose the interviewer and feedback are AI-generated.
- `[Test]` Component tests for the new structure.
- **Done when:** no god-component, no `any`, failures handled gracefully, and users can see/withdraw consent and delete their data.

## Phase 6 — Deployment & DevOps *(~3–5 days)*
Ship it. See [`DEPLOYMENT.md`](DEPLOYMENT.md) for the target architecture.
- `[Infra]` Dockerize three components separately (API, persistent agent worker, static frontend). Host per `DEPLOYMENT.md` (recommended: Fly.io + LiveKit Cloud + Supabase). Health checks, graceful shutdown, worker autoscaling on concurrent sessions with `drain_timeout`.
- `[Sec]` Edge hardening (TLS, WAF/CORS at the edge), dependency scanning (Dependabot / `pip-audit` / `npm audit`) in CI.
- `[Obs]` Wire exporters to the platform (LiveKit `prometheus_port` → Grafana; ship logs/traces).
- `[Test]` CI/CD (GitHub Actions): ruff + eslint, mypy + tsc, tests + evals, build, deploy.
- **Done when:** push-to-deploy with health checks, green gates, and live dashboards.

## Phase 7 — Scale, cost & compliance *(ongoing)*
The org/compliance/scale layer.
- `[Feature]` Cost controls: per-user quotas, max interview duration, concurrency caps; caching; teams/multi-tenancy.
- `[Priv]` Privacy policy, subprocessor list + DPAs (Cerebras/Deepgram/LiveKit), data-residency posture (incl. in-boundary LLM if required — see `DEPLOYMENT.md`).
- `[Safety]` Responsible-AI policy: documented intended use, EU AI Act / EEOC posture for hiring-adjacent AI, periodic bias audits.
- **Done when:** usage is bounded by cost, and the legal/responsible-AI posture is documented and defensible.

---

## Where evals & observability live in the codebase

Opposite lifecycles → different locations.

| Concern | Nature | Location | Analogy |
|---|---|---|---|
| **Observability** | Cross-cutting, runtime | `app/observability/` (config) + inline hooks | Logging |
| **Evals** | Offline, not shipped | top-level `evals/` | `tests/` |
| **Safety guardrails** | Runtime, wraps LLM calls | `app/llm/` (prompts, isolation) + a guardrail layer | Input/output validation |
| **AI core** | The thing all three target | `app/llm/` (pure, importable) | Domain layer |

```
backend/
  app/
    core/config.py            # settings (Phase 0)
    llm/                      # AI core: pure, importable, no transport (Phase 0)
      prompts.py              #   versioned prompts + rubrics + untrusted-input isolation
      extraction.py  interviewer.py  feedback.py
    observability/            # o11y: configure once, instrument inline (Phase 0/4)
      tracing.py  metrics.py  logging.py
    routers/                  # thin transport; call app/llm/*
  evals/                      # offline, CI-run, imports app/llm/* (Phase 0/3/4)
    datasets/  extraction/  interviewer/  feedback/  judges/  runner.py
  tests/                      # unit/integration (Phase 4)
```

**Principles:** prompts are code (versioned, not inline) · separate the AI core from
transport so evals import it directly · observability = central config + inline hooks
(can't be fully separated) · evals are offline tooling (sibling of `tests/`) · the two
connect at the data layer (prod traces → eval datasets).
