# Phase 4 — Quality: Testing, Evals & Observability

What shipped, what was genuinely hard, and what I'd improve. Companion to
`ROADMAP.md` Phase 4.

## What shipped

The roadmap's bar: prompt/model changes are gated by evals in CI, provider
errors page someone, and no PII leaks into the o11y layer.

- **Backend test suite** — `pytest` + `httpx` against the real FastAPI app,
  LLM mocked at the one choke point (`structured_completion`), DB a throwaway
  SQLite file. New `tests/test_api.py` covers routing, ownership, idempotent
  scoring, and generic error responses. Every existing manual `test_*.py`
  script now also runs under pytest (shared `tests/_bootstrap.py` +
  `conftest.py`) without losing its plain-`python` entry point.
- **Frontend smoke test** — Vitest + React Testing Library, Supabase mocked at
  the module boundary; renders both the signed-out and signed-in shells.
- **Full eval harness** — four suites (`extraction`, `interviewer`, `feedback`,
  `fairness`), a shared `judges/judge.py` that grades on a **different model
  family** than the app so the judge doesn't share the graded model's blind
  spots, a voice SLO checker over worker logs (`evals.voice_slo`), and a
  prod→eval export (`evals.export_prod`) that pulls real interviews into
  redacted datasets.
- **Bias & fairness evals** — counterfactual pairs (name swapped, phrasing made
  non-native) must not move the score. This is the suite that found a real bug
  (below).
- **Observability, deepened** — `llm_trace` log line per completion (model,
  latency, token counts, `interview_id` via a contextvar), `provider_error`
  events from the voice session, a Sentry hook gated behind `SENTRY_DSN`.
- **PII redaction** — `app/observability/redaction.py` strips emails, phones,
  and known names before anything reaches a log or an eval export.
- **CI** — `ci.yml` runs tests + build on every push; `evals.yml` gates any
  change to `app/llm/**` or `evals/**` on the eval suites.

## Challenges faced (and how they were solved)

### 1. The fairness eval caught a real bug on its first run
The point of writing a fairness suite was to find out whether the concern was
theoretical. It wasn't: scoring the *identical* interview transcript at
temperature 0, `technical_score` came back 6 for "Michael Anderson" and 8 for
every other name in the set (Ayesha Khan, Rajesh Patel, Emily Carter, Wei
Zhang) — a 2-point swing driven by nothing but the name on the resume. The
honest fix was not raising the eval's tolerance until it passed; it was
removing the variable the model was reacting to. `generate_feedback` now
redacts the candidate's name (and email/phone, for free) *before* building the
scoring prompt, so the model never sees it. The eval was rewritten to match:
instead of asserting "scores stay close" (still vulnerable to sampling noise
masking a smaller bias), it asserts every name counterfactual produces one
**byte-identical** scoring prompt — the causal path is closed, not just
statistically quiet.

### 2. Tests silently ran against zero tables
The first `pytest` run of the new API tests failed with `no such table:
interviews` — but only in `test_api.py` and only for tests that hit
`Interview`/`Turn` rows the security suite's probes hadn't touched. Root cause:
`Base.metadata.create_all()` only knows about tables whose model classes have
been *imported* somewhere; the bootstrap called `create_all` before anything
had imported `app.db.models`, so it created zero tables and no error, because
SQLAlchemy has nothing to complain about — it did exactly what an empty
metadata told it to. One-line fix: `import app.db.models` (for its
side effect of registering the tables) before `create_all()`.

### 3. The "different model family" judge needs a model that actually exists
The plan was to judge with `llama-3.3-70b` against the app's `gpt-oss-120b`.
Every judged eval failed identically: `404 model_not_found`. The account
simply didn't have that model — `GET /v1/models` listed `gpt-oss-120b`,
`gemma-4-31b`, and `zai-glm-4.7`. Swapped the default judge to `zai-glm-4.7`
and documented the lookup command in `CLAUDE.md`, since "pick a stronger
different model" is a decision that silently expires as provider catalogs
change.

### 4. Tests vs. evals is a real fork, not a formality
Everything in `tests/` mocks the LLM and must be fast, free, and deterministic;
everything in `evals/` calls the real model and is allowed to be slow, cost
money, and vary run to run within a threshold. Mixing the two — mocking the
LLM in something that's meant to catch a fairness regression, say — would have
made every eval in this phase pass trivially and prove nothing. Keeping them in
separate directories with separate CI triggers (`ci.yml` always, `evals.yml`
only on prompt/eval changes) makes the fork a structural fact, not a discipline
someone has to remember.

### 5. Voice SLOs needed a source of truth that already existed
"Voice SLOs (WER, `ttft`/`ttfb`, turn-detection)" sounds like it needs new
instrumentation. It didn't: Phase 0's `MetricsCollectedEvent` hook already logs
a `turn_latency` line per step. `evals/voice_slo.py` just reads that log back
and holds p95 against a ceiling — the prod→eval loop in its simplest form,
telemetry that was already being emitted turned into a pass/fail gate with no
new logging code.

## Deliberate shortcuts (with upgrade paths)

| Shortcut | Ceiling | Upgrade when |
|---|---|---|
| No WER eval | Needs retained audio + reference scripts, which data minimization forbids | Only if STT accuracy complaints appear despite the per-interview vocabulary hints (`tests/test_stt_fairness.py`) |
| `llm_trace` log lines instead of Langfuse/OTel | No UI, no cross-request search | Wire a real exporter in Phase 6 alongside the other platform exporters — same fields, just a sink |
| Sentry SDK installed but dormant until `SENTRY_DSN` is set | Errors don't page anyone in dev | Set the DSN before any real deployment |
| Redaction is regex (email/phone shapes + caller-supplied names) | Misses names not on the resume's first line, free-text PII in odd shapes | NER pass if a name leaks through in practice |
| Fairness suite has 5 names + 1 non-native sample | A small, hand-picked probe, not statistical coverage | Grow via `evals.export_prod` once there's real traffic to sample from |
| Judge model is same-provider (Cerebras), different family | Shares infra failure modes (rate limits, outages) with the app | Point `EVAL_JUDGE_MODEL`-equivalent at an external provider if that shared blast radius matters |

## Post-phase discussion: does Langfuse mean dockerizing the app?

Came up after the phase landed, while deciding whether to close the
`llm_trace`-instead-of-Langfuse gap: self-hosted Langfuse needs Docker (its
own Postgres + web server containers). This repo has no Docker anywhere —
the only place it's even planned is Phase 6 ("Dockerize three components").
That raised the real question: does adopting Langfuse *now* mean pulling
Phase 6's Docker work forward?

**No.** Langfuse is just an HTTP sink at `LANGFUSE_BASE_URL`. The app doesn't
care whether the thing on the other end of that URL is a container or
`cloud.langfuse.com` — same SDK, same env vars either way. Self-hosting
Langfuse via `docker compose up -d` in its own folder and continuing to run
`uvicorn`, `python run_agent.py dev`, and `npm run dev` natively (venv/npm, no
containers) is a completely ordinary setup — two unrelated processes on one
machine, only one of which happens to be containers. Nothing couples them,
and the Langfuse containers don't need to run continuously: bring them up
when actively inspecting traces, `docker compose down` otherwise.

Three options, in order of laziness, with the tradeoff that actually matters
for this app:

| Option | Docker? | Tradeoff |
|---|---|---|
| Langfuse Cloud | None | Real prompt tracing ships prompt/completion *content* off-machine — unlike today's metadata-only `llm_trace`. Fine for synthetic/test data; a real privacy question once actual candidate transcripts flow through it, given the redaction/data-minimization stance already in `CROSS_CUTTING.md`. |
| Self-host, rest of the app stays native | Local only, on-demand | Keeps transcript data on the machine. Cost is Docker Desktop running + ~1-2GB of images + a few minutes on first pull (seconds after). |
| Dockerize the whole app too | Full | This is just Phase 6 arriving early — an unrelated, bigger decision. If both happen, the compose files would naturally merge, but Langfuse doesn't require it. |

**Where this landed:** still deferred, per the shortcuts table above — no
code changed. Recorded here so the *decision*, not just the gap, survives:
skip Docker for now (Cloud, only against synthetic data, if tracing is
wanted before Phase 6), self-host specifically once real candidate
transcripts are involved, or fold in naturally when Phase 6 dockerizes the
app anyway.

## What to improve next (feeds Phase 5/6)

- **Citation-level groundedness** — the semantic judge checks a strength has
  *some* transcript evidence; it doesn't yet verify a literal quote exists.
- **Fairness eval breadth** — more names, more transcripts, ideally sourced
  from real (redacted) interviews via `evals.export_prod` rather than one
  hand-written dataset.
- **OTel / Langfuse wiring** — the OTel SDK is already installed (a
  `livekit-agents` dependency); actually exporting spans/traces is Phase 6,
  once there's a collector (or a Langfuse instance, see above) to point at.
- **App.tsx decomposition** — still one ~700-line component; the smoke test
  covers the shell, not the screens inside it — scheduled Phase 5 work.
