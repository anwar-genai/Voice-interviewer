# Evals

Offline quality checks for the LLM surfaces. A sibling of `tests/`, not shipped
with the app: these import `app.llm.*` directly and call real providers.

## Run

```bash
cd backend
python -m evals.runner                  # all suites
python -m evals.runner fairness         # one of: extraction | interviewer | feedback | fairness

python -m evals.voice_slo agent.log     # p50/p95 turn latency vs SLOs, from a worker log
python -m evals.export_prod [limit]     # prod->eval loop: redacted real transcripts (gitignored)
```

Needs `CEREBRAS_API_KEY`. The runner exits non-zero when a suite scores below
its threshold, and `.github/workflows/evals.yml` gates every change to
`backend/app/llm/**` or `backend/evals/**` on it (set the `CEREBRAS_API_KEY`
repo secret; without it the gate fails closed).

## Suites

| Suite | Checks | Graded by |
|---|---|---|
| `extraction` | golden-set field accuracy, incl. a prompt-injection posting | deterministic |
| `interviewer` | scripted scenarios: stays on task, one question at a time, resists injection, voice format (no markdown) | LLM judge + regex |
| `feedback` | thin-transcript guard, calibration spread across repeat runs, strengths grounded in the transcript | deterministic + LLM judge |
| `fairness` | name counterfactuals must produce one byte-identical scoring prompt (name-blind by construction); non-native phrasing must not move scores | deterministic + model |

The LLM judge runs on a **different model family** (`EVAL_JUDGE_MODEL`, default
`zai-glm-4.7`) than the app (`gpt-oss-120b`), so the grader doesn't share the
graded model's blind spots. The judge model must exist on your Cerebras account
(`GET /v1/models` lists them).

WER is deliberately not measured: it needs retained audio plus reference
scripts, which data minimization says we don't keep. STT accuracy is protected
indirectly (per-interview vocabulary + transcription-aware rubric, covered by
`tests/test_stt_fairness.py`).

## Adding a case

Append to the matching `datasets/*.json`. For extraction, only the fields you
list in `expected` are scored, so a case can assert on `job_title` alone.
`export_prod` grows the pool with real (redacted) transcripts.
