# Phase 0 — Foundation & Cleanup

What shipped, what was genuinely hard, and what I'd improve. Companion to
`ROADMAP.md` Phase 0. (Reconstructed retro — written after the phase landed.)

## What shipped

One worker, one config source, a pure importable AI core, and free
per-interview telemetry — the structure every later phase leans on:

- **One agent worker** — deleted two competing worker files
  (`run_agent_improved.py`, `agent_worker.py`); `run_agent.py` is transport-only.
- **Central config** — `app/core/config.py` on pydantic-settings: one typed,
  validated source; standardized `LIVEKIT_*` naming; secrets env-only so
  `.env` → vault later needs no code change.
- **The enabling refactor** — prompts + LLM calls extracted into a pure
  `app/llm/` core (no FastAPI, no LiveKit), so evals, guardrails, and tracing
  all wrap one place instead of strings scattered through routers.
- **Free observability** — LiveKit's `MetricsCollectedEvent` + `UsageCollector`
  wired in: per-turn latency and a per-interview usage + cost summary.
- **Evals scaffold** — `evals/` with an extraction golden-set and a CI-gating
  runner.
- **Dead code removed** — PyPDF2, `/agent/start`, the non-LLM `/parse-link`.

## Challenges faced (and how they were solved)

### 1. Planning before building: concerns kept falling between phases
The first roadmap draft dumped security/privacy/safety/evals/observability
into single phases or left them floating. Reworked the plan so every
cross-cutting concern lands in the phase it naturally attaches to, with a
concern × phase coverage matrix as proof (`ROADMAP.md`), and a second view
organized by concern (`CROSS_CUTTING.md`). Lesson: a roadmap where "safety"
is one line in one phase is a roadmap that ships without safety.

### 2. Three workers, none authoritative
The prototype had accumulated three versions of the agent worker with drifted
behavior. Nobody (including me) could say which was real. Consolidated to one
file and made it transport-only — everything the interviewer is *told* moved
to `app/llm/`, so there's exactly one place behavior lives.

### 3. Config was spread across inline os.getenv calls
Mixed-case env names (`LiveKit_*` vs `LIVEKIT_*`), fallbacks nobody remembered,
credentials read at import time. The fix that mattered: **lazy `require_*`
accessors** — the API boots and `/health` answers without any provider keys;
the code path that needs a credential fails at use time with a clear message.

### 4. The refactor no one asks for but everything depends on
Extracting the AI core (`prompts.py`, `extraction.py`, `interviewer.py`,
`feedback.py`, one `structured_completion` client) produced no visible feature.
But it's why Phase 1 could add injection isolation in one file, Phase 3 could
wrap guardrails around one function, and evals import the exact production
prompts. The highest-leverage work of the project was invisible in the demo.

### 5. Honest eval scoring from day one
Design decision in the runner: an errored eval case **fails the suite** rather
than being averaged away. A suite that scores 95% because half its cases
crashed is a lie; this was cheaper to get right at 10 lines than to retrofit.

## Deliberate shortcuts (with upgrade paths)

| Shortcut | Ceiling | Upgrade when |
|---|---|---|
| Cost telemetry uses list prices from config | Estimates, not billing data | Provider billing APIs, if ever needed |
| Cached prompt tokens billed at full input rate | Overestimates LLM cost | Only if cost reports drive real decisions |
| One extraction golden-set, keyword matching | Lenient scoring | Phase 4 full harness with judge model |
| Telemetry is log lines | Not queryable | Phase 4/6 exporters (Prometheus/Grafana) |

## What to improve next (with hindsight)

- **Auth before any public URL** → done in Phase 1.
- **Metrics summary only logs at clean shutdown** — a crashed session loses its
  usage summary; acceptable until real billing depends on it.
- **The evals runner calls the live LLM** — fine offline; CI gating (Phase 4)
  needs recorded fixtures or a spend budget.
